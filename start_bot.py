#!/usr/bin/env python3
"""
Скрипт запуска бота с обработкой ошибок и перезапуском
"""

import sys
import os
import logging
import traceback
from time import sleep

# Добавляем путь к проекту
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def setup_logging():
    """Настройка логирования"""
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'bot.log')),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

def main():
    """Основная функция запуска"""
    logger = setup_logging()
    
    logger.info("=" * 50)
    logger.info("Запуск бота 'Правда или Действие'")
    logger.info("=" * 50)
    
    max_retries = 10
    retry_delay = 30  # секунд
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Попытка запуска {attempt + 1}/{max_retries}")
            
            # Импортируем основной бот
            from bot import main as bot_main
            
            # Запускаем бота
            bot_main()
            
        except KeyboardInterrupt:
            logger.info("Бот остановлен пользователем")
            sys.exit(0)
            
        except Exception as e:
            logger.error(f"Ошибка при запуске бота: {str(e)}")
            logger.error(traceback.format_exc())
            
            if attempt < max_retries - 1:
                logger.info(f"Повторная попытка через {retry_delay} секунд...")
                sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 300)  # Увеличиваем задержку, но не более 5 минут
            else:
                logger.error("Достигнут максимум попыток перезапуска")
                sys.exit(1)

if __name__ == "__main__":
    main()