import asyncio
import signal
import sys
import argparse
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot_core import RefillBot, run_daily_reports, shutdown_bots
from logger_setup import logger
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN


class BotManager:
    def __init__(self, manual_mode=False):
        self.scheduler = None
        self.running = True
        self.manual_mode = manual_mode
        self.bot_inr = None
        self.bot_other = None
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        logger.info(f"⏹️ Получен сигнал {signum}. Останавливаем ботов...")
        self.running = False
    
    async def run(self):
        try:
            logger.info("🚀 Запуск системы...")
            
            # Инициализируем ботов по отдельности
            try:
                self.bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
                await self.bot_inr.initialize()
                logger.info("✅ Бот INR запущен")
            except Exception:
                logger.warning("⚠️ Бот INR уже запущен в другом месте. Пропускаем...")
                self.bot_inr = None
            
            try:
                self.bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
                await self.bot_other.initialize()
                logger.info("✅ Бот OTHER запущен")
            except Exception:
                logger.warning("⚠️ Бот OTHER уже запущен в другом месте. Пропускаем...")
                self.bot_other = None
            
            # Проверяем, что хотя бы один бот запущен
            if not self.bot_inr and not self.bot_other:
                logger.error("❌ Ни один бот не может быть запущен!")
                return
            
            if self.manual_mode:
                logger.info("📊 Ручной режим: запуск отчетов...")
                
                # Запускаем отчеты только для активных ботов
                tasks = []
                if self.bot_inr:
                    tasks.append(self.bot_inr.run_daily_report())
                if self.bot_other:
                    tasks.append(self.bot_other.run_daily_report())
                
                if tasks:
                    await asyncio.gather(*tasks)
                    logger.info("✅ Отчеты выполнены. Боты продолжают работать.")
                else:
                    logger.warning("⚠️ Нет активных ботов для выполнения отчетов")
                
                logger.info("Нажмите Ctrl+C для остановки")
            else:
                self.scheduler = AsyncIOScheduler()
                
                # Запуск отчетов каждый день в 10:00
                self.scheduler.add_job(
                    self._run_reports,
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
    
    async def _run_reports(self):
        """Запуск отчетов для активных ботов"""
        logger.info(f"⏰ Запуск отчетов по расписанию в {datetime.now().strftime('%H:%M:%S')}")
        
        tasks = []
        if self.bot_inr and self.bot_inr.is_ready:
            tasks.append(self.bot_inr.run_daily_report())
        if self.bot_other and self.bot_other.is_ready:
            tasks.append(self.bot_other.run_daily_report())
        
        if tasks:
            await asyncio.gather(*tasks)
            logger.info("✅ Плановые отчеты завершены")
        else:
            logger.warning("⚠️ Нет активных ботов для выполнения отчетов")
    
    async def shutdown(self):
        logger.info("🔄 Остановка системы...")
        
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        
        if self.bot_inr:
            await self.bot_inr.shutdown()
        if self.bot_other:
            await self.bot_other.shutdown()
        
        logger.info("✅ Система полностью остановлена")


async def main():
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
        logger.info("🧪 Тестовый режим...")
        try:
            bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
            await bot_inr.initialize()
            await bot_inr.run_daily_report()
            await bot_inr.shutdown()
        except Exception:
            logger.warning("⚠️ Бот INR уже запущен. Пропускаем...")
        
        try:
            bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
            await bot_other.initialize()
            await bot_other.run_daily_report()
            await bot_other.shutdown()
        except Exception:
            logger.warning("⚠️ Бот OTHER уже запущен. Пропускаем...")
        
        logger.info("✅ Тестовый режим завершен")
        return
    
    manager = BotManager(manual_mode=args.manual)
    await manager.run()


if __name__ == '__main__':
    asyncio.run(main())
