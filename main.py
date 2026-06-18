#!/usr/bin/env python
# main.py - с последовательной работой ботов

import asyncio
import signal
import sys
import argparse
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot_core import RefillBot
from logger_setup import logger
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from datetime import datetime
import time


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
            await self._init_bots()
            
            # Проверяем, что хотя бы один бот запущен
            if not self.bot_inr and not self.bot_other:
                logger.error("❌ Ни один бот не может быть запущен!")
                return
            
            if self.manual_mode:
                logger.info("📊 Ручной режим: запуск отчетов последовательно...")
                await self._run_reports_sequential()
                logger.info("✅ Отчеты выполнены. Боты продолжают работать.")
                logger.info("Нажмите Ctrl+C для остановки")
            else:
                # Автоматический режим с планировщиком
                self.scheduler = AsyncIOScheduler()
                
                self.scheduler.add_job(
                    self._run_reports_sequential,
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
    
    async def _init_bots(self):
        """Инициализация ботов по отдельности"""
        try:
            self.bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
            await self.bot_inr.initialize()
            logger.info("✅ Бот INR запущен")
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("⚠️ Бот INR уже запущен в другом месте. Пропускаем...")
                self.bot_inr = None
            else:
                logger.error(f"❌ Ошибка запуска бота INR: {e}")
                self.bot_inr = None
        
        # Небольшая задержка между инициализациями
        await asyncio.sleep(2)
        
        try:
            self.bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
            await self.bot_other.initialize()
            logger.info("✅ Бот OTHER запущен")
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("⚠️ Бот OTHER уже запущен в другом месте. Пропускаем...")
                self.bot_other = None
            else:
                logger.error(f"❌ Ошибка запуска бота OTHER: {e}")
                self.bot_other = None
    
    async def _run_reports_sequential(self):
        """
        Запуск отчетов последовательно (сначала INR, потом OTHER)
        с задержкой между ними
        """
        logger.info(f"⏰ Запуск отчетов по расписанию в {datetime.now().strftime('%H:%M:%S')}")
        
        try:
            # Сначала запускаем INR бота
            if self.bot_inr and self.bot_inr.is_ready:
                logger.info("📊 Запуск отчета для INR бота...")
                await self.bot_inr.run_daily_report()
                logger.info("✅ Отчет INR завершен")
                
                # Задержка между отчетами (чтобы не перегружать Google Sheets)
                logger.info("⏳ Ожидание 5 секунд перед следующим отчетом...")
                await asyncio.sleep(5)
            else:
                logger.warning("⚠️ INR бот не готов или не активен")
            
            # Затем запускаем OTHER бота
            if self.bot_other and self.bot_other.is_ready:
                logger.info("📊 Запуск отчета для OTHER бота...")
                await self.bot_other.run_daily_report()
                logger.info("✅ Отчет OTHER завершен")
            else:
                logger.warning("⚠️ OTHER бот не готов или не активен")
            
            logger.info("✅ Все отчеты успешно выполнены!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка при выполнении отчетов: {e}")
    
    async def shutdown(self):
        logger.info("🔄 Остановка системы...")
        
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        
        # Останавливаем ботов по очереди
        if self.bot_inr:
            await self.bot_inr.shutdown()
            await asyncio.sleep(1)
        
        if self.bot_other:
            await self.bot_other.shutdown()
            await asyncio.sleep(1)
        
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
        
        # Тестируем ботов последовательно
        try:
            bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
            await bot_inr.initialize()
            await bot_inr.run_daily_report()
            await bot_inr.shutdown()
            logger.info("✅ Тест INR завершен")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при тесте INR: {e}")
        
        try:
            bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
            await bot_other.initialize()
            await bot_other.run_daily_report()
            await bot_other.shutdown()
            logger.info("✅ Тест OTHER завершен")
        except Exception as e:
            logger.warning(f"⚠️ Ошибка при тесте OTHER: {e}")
        
        logger.info("✅ Тестовый режим завершен")
        return
    
    manager = BotManager(manual_mode=args.manual)
    await manager.run()


if __name__ == '__main__':
    asyncio.run(main())
