import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta
import shutil
from config import LOGS_DIR, LOG_FILE, LOG_RETENTION_DAYS


def setup_logger(name=__name__):
    """
    Настройка логгера с ротацией файлов
    """
    # Создаем папку для логов если её нет
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
    
    # Полный путь к файлу лога
    log_path = os.path.join(LOGS_DIR, LOG_FILE)
    
    # Создаем логгер
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Очищаем старые обработчики если есть
    if logger.handlers:
        logger.handlers.clear()
    
    # Создаем форматтер
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Обработчик для ротации по дням
    file_handler = TimedRotatingFileHandler(
        log_path,
        when='midnight',
        interval=1,
        backupCount=LOG_RETENTION_DAYS
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    
    # Обработчик для вывода в консоль (для отладки)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Добавляем обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # Очищаем старые логи при запуске
    clean_old_logs()
    
    return logger


def clean_old_logs():
    """
    Удаляет логи старше LOG_RETENTION_DAYS дней
    """
    try:
        now = datetime.now()
        log_dir = LOGS_DIR
        
        if not os.path.exists(log_dir):
            return
        
        for filename in os.listdir(log_dir):
            if filename.startswith(LOG_FILE):
                file_path = os.path.join(log_dir, filename)
                
                # Проверяем дату создания файла
                file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                
                # Если файл старше LOG_RETENTION_DAYS дней - удаляем
                if (now - file_modified) > timedelta(days=LOG_RETENTION_DAYS):
                    os.remove(file_path)
                    print(f"🗑️ Удален старый лог: {filename}")
                    
    except Exception as e:
        print(f"⚠️ Ошибка при очистке логов: {e}")


# Создаем глобальный логгер
logger = setup_logger('RefillBot')
