import asyncio
import signal
import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot_core import initialize_bots, run_daily_reports, shutdown_bots
from logger_setup import logger


class BotManager:
    """Менеджер для управления ботами и расписанием"""
    
    def __init__(self, manual_mode=False):
        self.scheduler = None
        self.running = True
        self.manual_mode = manual_mode
        
        # Настройка обработчиков сигналов
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        """Обработчик сигналов для graceful shutdown"""
        logger.info(f"⏹️ Получен сигнал {signum}. Останавливаем ботов...")
        self.running = False
    
    async def run(self):
        """Основной метод запуска"""
        try:
            logger.info("🚀 Запуск системы...")
            
            # Инициализация ботов
            await initialize_bots()
            
            if self.manual_mode:
                # Ручной режим - сразу запускаем отчеты
                logger.info("📊 Ручной режим: запуск отчетов...")
                await run_daily_reports()
                logger.info("✅ Отчеты выполнены. Боты продолжают работать.")
                logger.info("Нажмите Ctrl+C для остановки")
            else:
                # Автоматический режим - настраиваем планировщик
                self.scheduler = AsyncIOScheduler()
                
                # Запуск отчетов каждый день в 10:00
                self.scheduler.add_job(
                    run_daily_reports,
                    CronTrigger(hour=10, minute=0),
                    id='daily_refill_report'
                )
                
                logger.info("⏰ Планировщик запущен. Боты будут выполнять отчеты ежедневно в 10:00")
                logger.info("Боты также слушают сообщения для автоматической настройки")
                logger.info("Для остановки нажмите Ctrl+C")
                
                self.scheduler.start()
            
            # Держим систему активной
            while self.running:
                await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown системы"""
        logger.info("🔄 Остановка системы...")
        
        # Останавливаем планировщик
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        
        # Останавливаем ботов
        await shutdown_bots()
        
        logger.info("✅ Система полностью остановлена")


async def main():
    """Точка входа с поддержкой аргументов командной строки"""
    parser = argparse.ArgumentParser(description='Бот для отчетов по скорости рефилов')
    parser.add_argument(
        '--manual',
        action='store_true',
        help='Запустить в ручном режиме (сразу выполнить отчет)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Тестовый режим (выполнить отчет и завершить работу)'
    )
    
    args = parser.parse_args()
    
    if args.test:
        # Тестовый режим - выполняем отчет и выходим
        logger.info("🧪 Тестовый режим...")
        await initialize_bots()
        await run_daily_reports()
        await shutdown_bots()
        logger.info("✅ Тестовый режим завершен")
        return
    
    # Основной режим
    manager = BotManager(manual_mode=args.manual)
    await manager.run()


if __name__ == '__main__':
    asyncio.run(main())
