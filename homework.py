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

RETRY_TIME = 300
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
    bot.send_message(TELEGRAM_CHAT_ID, message)


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
        logger.error(message)

    if response.status_code != HTTPStatus.OK:
        raise ValueError('Код ответа сервера не соответствует '
                         f'ожидаемому при запросе {ENDPOINT}')

    return response.json()


def check_response(response: Dict[str, Any]) -> List[Any]:
    """Проверка ответа от API."""
    key = 'homeworks'
    try:
        check = response[key]

    except KeyError as error:
        message1 = f'Пустой список: {error}'
        logger.error(message1)
        raise KeyError(message1)
    else:
        if not isinstance(check, list):
            error_msg = (
                f'Под ключом {key} в ответе API '
                f'содержится некорректный тип: {type(check)}'
            )
            logger.debug(error_msg)
            raise TypeError(error_msg)

    return check


def parse_status(homework: List[Any]) -> str:
    """Получение статуса из ответа."""
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']

    except KeyError as error:
        message = f'Недокументированный статус {error} домашней работы.'
        logger.error(message)
        raise KeyError(message)

    verdict = HOMEWORK_STATUSES[homework_status]
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
        message = f'Отсутствует обязательная переменная окружения: {error}'
        logger.critical(message)

    return flag


def main() -> None:
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    check_tokens()

    while True:
        try:
            response = get_api_answer(current_timestamp)
            check = check_response(response)
            send_message(bot, parse_status(check))
            logger.info('Бот успешно отправил сообщение.')
            current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            send_message(bot, message)
            time.sleep(RETRY_TIME)
        else:
            logger.info('Программа принудительно приостановлена.')
            break


if __name__ == '__main__':
    main()
