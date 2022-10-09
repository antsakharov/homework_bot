import os
import sys
import time
import json
import logging
import copy
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
    if not isinstance(response, dict):
        message = 'Response не является словарем'
        logger.error(message)
        raise TypeError(message)
    if "homeworks" not in response:
        message = 'Ключ homeworks не в response'
        logger.error(message)
        raise KeyError(message)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        message = 'Перечень не является списком'
        logger.error(message)
        raise exceptions.HomeWorkIsNotList(message)
    if not homeworks:
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
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Токены отсутствуют')
        raise NameError('Отсутствуют обязательные переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    last_homework = ''
    last_message = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            logger.info(response)
            homework = check_response(response)
            logger.info(homework)
            if homework != last_homework:
                if len(homework) > 0:
                    last_homework = homework
                    message = parse_status(homework[0])
                    if last_message != message:
                        send_message(bot, message)
                        last_message = copy.copy(message)
                else:
                    message = 'Передан пустой список homework'
                    logger.error(message)
                    raise ValueError(message)
            current_timestamp = response.get('current_date')
            logger.info(message)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if last_message != message:
                send_message(bot, message)
                last_message = copy.copy(message)
            logger.critical(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
