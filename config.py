import os
import logging
import datetime

# Состояния диалога
WAIT_PHOTO = 0           # Ожидание фото накладной
CONFIRMATION = 1         # Ожидание подтверждения
EDIT_ITEM = 2            # Редактирование неопознанного товара
ADD_NEW_ITEM = 3         # Добавление нового товара
SET_CONVERSION = 4       # Настройка конвертации единиц измерения
EDIT_SPECIFIC_ITEM = 5   # Редактирование конкретной позиции
FINAL_CONFIRMATION = 6   # Финальное подтверждение перед отправкой
SELECT_EDIT_ITEM = 7     # Выбор позиции для редактирования
PREVIOUS_STEP = 8        # Возврат к предыдущему шагу
CONFIRM_ADD_NEW = 9      # Подтверждение добавления нового товара

# Пути к файлам данных
LEARNED_MAPPINGS_FILE = 'data/learned/item_mappings.csv'
UNIT_CONVERSIONS_FILE = 'data/learned/unit_conversions.csv'

# Директории для хранения данных
DIRECTORIES = [
    'logs',
    'logs/errors',
    'logs/errors/detailed',
    'logs/images',
    'logs/error_images',
    'data/invoices',
    'data/learned'
]

def setup_directories():
    """Создает необходимые директории для работы приложения"""
    for directory in DIRECTORIES:
        os.makedirs(directory, exist_ok=True)

def setup_logging():
    """Настройка логирования"""
    # Настройка основного логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('logs/nota_bot.log'),
            logging.StreamHandler()
        ]
    )

    # Создание отдельного логгера для ошибок
    error_logger = logging.getLogger('error_logger')
    error_logger.setLevel(logging.ERROR)
    error_handler = logging.FileHandler('logs/errors/error_log.log')
    error_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s\n%(pathname)s:%(lineno)d\n%(funcName)s\n\n%(exc_info)s\n\n'))
    error_logger.addHandler(error_handler)
    
    # Получаем основной логгер
    logger = logging.getLogger(__name__)
    
    return logger

# Глобальный словарь для хранения данных накладных пользователей
user_data = {}
