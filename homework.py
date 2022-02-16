import json
import logging
import os
import sys
import requests
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus
from typing import Any, Dict, List


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


def send_message(bot: "telegram.Bot", message: str) -> None:
    """Отправка сообщений в бот."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)

    except telegram.TelegramError:
        message = 'Возникла ошибка при отправке сообщения.'
        raise telegram.TelegramError(message)


def get_api_answer(current_timestamp: int) -> List[Any]:
    """Получение ответа от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)

    except requests.RequestException as exception:
        message = (
            'Сбой в работе программы: '
            f'Эндпоинт {ENDPOINT} недоступен. Код ответа API: {exception}'
        )
        raise requests.RequestException(message)

    if response.status_code != HTTPStatus.OK:
        raise ValueError('Код ответа сервера не соответствует '
                         f'ожидаемому при запросе {ENDPOINT}.')

    try:
        return response.json()

    except json.decoder.JSONDecodeError:
        raise ValueError('Ответ сервера не в формате json.')


def check_response(response: Dict[str, Any]) -> List[Any]:
    """Проверка ответа от API."""
    result = []
    if type(response) is not dict:
        error_msg = (
            'Cодержится некорректный тип ответа от http-запроса: '
            f'{type(response)}.'
        )
        raise TypeError(error_msg)
    result = response.get('homeworks')
    if type(result) is not list:
        error_msg = (
            f'Некорректный тип: {type(result)} у списка "homeworks".'
        )
        raise TypeError(error_msg)
    return result


def parse_status(homework: Dict[str, Any]) -> str:
    """Получение статуса из ответа."""
    if len(homework) > 0:
        homework_name = homework.get('homework_name')
        homework_status = homework.get('status')
    try:
        verdict = HOMEWORK_STATUSES[homework_status]

    except KeyError as error:
        message = f'Недокументированный статус {error} в домашней работы.'
        raise KeyError(message)

    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens() -> bool:
    """Проверка на наличие токенов."""
    try:
        assert PRACTICUM_TOKEN
        assert TELEGRAM_TOKEN
        assert TELEGRAM_CHAT_ID
        flag = True

    except AssertionError as error:
        flag = False
        message = f'Отсутствует обязательная переменная окружения: {error}.'
        logger.critical(message)

    return flag


def main() -> None:
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    if check_tokens():
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                logger.log(10, f'Запрос с {ENDPOINT} получен.')
                logger.log(
                    10,
                    f'В запросе данные о {len(homeworks)} событиях.'
                )
                for homework in homeworks:
                    message = parse_status(homework)
                    logger.log(10, message)
                    send_message(bot, message)
                current_timestamp = response.get('current_date')
                time.sleep(RETRY_TIME)

            except Exception as error:
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                send_message(bot, message)
                time.sleep(RETRY_TIME)
            else:
                logger.info('Обновлений нет.')


if __name__ == '__main__':
    main()
