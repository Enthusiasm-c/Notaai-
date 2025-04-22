import os
import sys
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters, ConversationHandler

# Добавляем текущую директорию в пути поиска модулей
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

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

# Глобальный словарь для хранения данных пользователей
user_data = {}

# Путь к файлам с данными обучения
LEARNED_MAPPINGS_FILE = 'data/learned/item_mappings.csv'
UNIT_CONVERSIONS_FILE = 'data/learned/unit_conversions.csv'

# Инициализация данных обучения
learned_mappings = {}
unit_conversions = {}

# Создание директорий
def setup_directories():
    """Создает необходимые директории для работы приложения"""
    directories = [
        'logs',
        'logs/errors',
        'logs/errors/detailed',
        'logs/images',
        'logs/error_images',
        'data/invoices',
        'data/learned'
    ]
    for directory in directories:
        os.makedirs(directory, exist_ok=True)

# Настройка логирования
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

# Функция для логирования ошибок
def log_error(message, exc_info=None):
    """Логирование ошибок в отдельный файл и основной лог"""
    import traceback
    import datetime
    
    error_logger = logging.getLogger('error_logger')
    logger = logging.getLogger(__name__)
    
    error_logger.error(message, exc_info=exc_info)
    logger.error(message, exc_info=exc_info)
    
    # Добавляем трассировку стека в отдельный файл для более подробного анализа
    if exc_info:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        os.makedirs('logs/errors/detailed', exist_ok=True)
        with open(f'logs/errors/detailed/error_{timestamp}.log', 'w') as f:
            traceback.print_exception(type(exc_info), exc_info, exc_info.__traceback__, file=f)

# Импортируем явно функции из других модулей
def import_modules():
    """Импортирует все необходимые модули и функции"""
    global start, help_command, cancel, process_photo, handle_confirmation
    global handle_item_selection, handle_item_edit, handle_manual_item_entry
    global handle_manual_entry_callback, handle_conversion_entry, handle_conversion_callback
    global load_learned_mappings, load_unit_conversions
    
    # Пробуем импортировать модули стандартным способом
    try:
        from handlers.command_handlers import start, help_command, cancel
        from handlers.invoice_handlers import process_photo
        from handlers.confirmation_handlers import handle_confirmation
        from handlers.item_handlers import (
            handle_item_selection, handle_item_edit, handle_manual_item_entry,
            handle_manual_entry_callback, handle_conversion_entry, handle_conversion_callback
        )
        from data.learning import load_learned_mappings, load_unit_conversions
        
        return True
    except ImportError:
        # Если не получилось, пробуем напрямую импортировать из файлов
        import importlib.util
        
        def load_module(name, path):
            spec = importlib.util.spec_from_file_location(name, path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module
        
        try:
            command_handlers = load_module("command_handlers", os.path.join(current_dir, "handlers/command_handlers.py"))
            invoice_handlers = load_module("invoice_handlers", os.path.join(current_dir, "handlers/invoice_handlers.py"))
            confirmation_handlers = load_module("confirmation_handlers", os.path.join(current_dir, "handlers/confirmation_handlers.py"))
            item_handlers = load_module("item_handlers", os.path.join(current_dir, "handlers/item_handlers.py"))
            learning = load_module("learning", os.path.join(current_dir, "data/learning.py"))
            
            # Присваиваем функции из модулей
            start = command_handlers.start
            help_command = command_handlers.help_command
            cancel = command_handlers.cancel
            process_photo = invoice_handlers.process_photo
            handle_confirmation = confirmation_handlers.handle_confirmation
            handle_item_selection = item_handlers.handle_item_selection
            handle_item_edit = item_handlers.handle_item_edit
            handle_manual_item_entry = item_handlers.handle_manual_item_entry
            handle_manual_entry_callback = item_handlers.handle_manual_entry_callback
            handle_conversion_entry = item_handlers.handle_conversion_entry
            handle_conversion_callback = item_handlers.handle_conversion_callback
            load_learned_mappings = learning.load_learned_mappings
            load_unit_conversions = learning.load_unit_conversions
            
            return True
        except Exception as e:
            print(f"Failed to import modules: {e}")
            return False

def main():
    """Запуск бота"""
    try:
        # Загрузка переменных окружения
        load_dotenv()
        
        # Настройка логирования и создание директорий
        logger = setup_logging()
        setup_directories()
        
        # Импортируем все модули
        if not import_modules():
            logger.error("Failed to import required modules. Exiting.")
            return
        
        # Загружаем обученные данные
        load_learned_mappings()
        load_unit_conversions()
        
        # Создаем приложение
        token = os.getenv('TELEGRAM_TOKEN')
        if not token:
            logger.error("Telegram token not found in environment variables")
            return
            
        application = Application.builder().token(token).build()
        
        # Определяем обработчик разговора
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                CommandHandler("help", help_command),
                MessageHandler(filters.PHOTO, process_photo)
            ],
            states={
                WAIT_PHOTO: [
                    CommandHandler("start", start),
                    CommandHandler("help", help_command),
                    MessageHandler(filters.PHOTO, process_photo)
                ],
                CONFIRMATION: [
                    CallbackQueryHandler(handle_confirmation)
                ],
                SELECT_EDIT_ITEM: [
                    CallbackQueryHandler(handle_item_selection)
                ],
                EDIT_ITEM: [
                    CallbackQueryHandler(handle_item_edit)
                ],
                ADD_NEW_ITEM: [
                    CallbackQueryHandler(handle_manual_entry_callback),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_manual_item_entry)
                ],
                SET_CONVERSION: [
                    CallbackQueryHandler(handle_conversion_callback),
                    MessageHandler(filters.TEXT & ~filters.COMMAND, handle_conversion_entry)
                ],
                FINAL_CONFIRMATION: [
                    CallbackQueryHandler(handle_confirmation)
                ],
                CONFIRM_ADD_NEW: [
                    CallbackQueryHandler(handle_manual_entry_callback)
                ]
            },
            fallbacks=[CommandHandler("cancel", cancel)],
            name="invoice_conversation",
            persistent=False
        )
        
        # Добавляем обработчик разговора
        application.add_handler(conv_handler)
        
        # Запускаем бота
        logger.info("Starting bot")
        application.run_polling()
    
    except Exception as e:
        log_error(f"Critical error starting bot: {e}", exc_info=True)
        print(f"Error starting bot: {e}")

if __name__ == "__main__":
    main()
