import os
import sys
import time
import json
import logging
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv


import exceptions


load_dotenv()


PRACTICUM_TOKEN = os.getenv('YA_TOKEN')
TELEGRAM_TOKEN = os.getenv('TG_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TG_CHAT_ID')


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
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
fileHandler = logging.FileHandler('homework.log', encoding='UTF-8')
fileHandler.setFormatter(formatter)
logger.addHandler(fileHandler)
streamHandler = logging.StreamHandler(sys.stdout)
streamHandler.setFormatter(formatter)
logger.addHandler(streamHandler)


def send_message(bot, message):
    """Функция отправки сообщений в Телеграм."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.TelegramError as error:
        logger.error(
            f'Ошибка при отправке сообщения: {error}')
    else:
        logger.info('Сообщение отправлено')


def get_api_answer(current_timestamp):
    """Функция отправляет запрос к API."""
    timestamp = current_timestamp
    params = {'from_date': timestamp}
    try:
        homework_statuses = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception as error:
        message = f'Запрос к API не отправлен: {error}'
        logger.error(message)
        raise exceptions.RequestError(message)
    if homework_statuses.status_code != HTTPStatus.OK:
        messagest = 'Код ответа не 200'
        logger.error(messagest)
        raise exceptions.NegativeApiStatus(messagest)
    try:
        return homework_statuses.json()
    except json.decoder.JSONDecodeError:
        messagejs = 'Ошибка JSON'
        logger.error(messagejs)
        raise ValueError(messagejs)


def check_response(response):
    """Проверяет ответ API на корректность."""
    homeworks = response['homeworks']
    if not isinstance(response, dict):
        message = 'Отсутсвует ключ homeworks'
        logger.error(message)
        raise KeyError(message)
    if not isinstance(homeworks, list):
        message = 'Перечень не является списком'
        logger.error(message)
        raise exceptions.HomeWorkIsNotList(message)
    if len(homeworks) == 0:
        message = 'Вы ничего не отправляли на ревью'
        logger.error(message)
        raise ValueError(message)
    return homeworks


def parse_status(homework):
    """Функция извлекает статус домашней работы."""
    if not isinstance(homework, dict):
        message = 'Перечень не является словарем'
        logger.error(message)
        raise exceptions.HomeWorkIsNotDict(message)
    if 'homework_name' not in homework:
        message = 'Нет ключа homework_name в API'
        logger.error(message)
        raise KeyError(message)
    if 'status' not in homework:
        message = 'Нет ключа "status" в API'
        logger.error(message)
        raise exceptions.HomewokrStatusError(message)
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception(f'Неизвестный статус работы: {homework_status}')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Функция проверки доступности переменных окружения."""
    if (
        PRACTICUM_TOKEN is None
        or TELEGRAM_TOKEN is None
        or TELEGRAM_CHAT_ID is None
    ):
        return False
    return True


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Токены отсутствуют')
        raise NameError('Отсутствуют обязательные переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_homework = 0
    errors = True
    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.info(response)
            homework = check_response(response)
            logger.info(homework)
            if homework != last_homework:
                last_homework = homework
                message = parse_status(homework[0])
                send_message(bot, message)
            current_timestamp = response.get('current_date')
            logger.info(message)
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if errors:
                errors = False
                send_message(bot, message)
            logger.critical(message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
