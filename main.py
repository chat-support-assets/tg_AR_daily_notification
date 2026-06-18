#!/usr/bin/env python
# main.py - Исправленная версия без конфликтов

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
import random


class BotManager:
    def __init__(self, manual_mode=False, listen_mode=False):
        self.scheduler = None
        self.running = True
        self.manual_mode = manual_mode
        self.listen_mode = listen_mode
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
            
            if self.listen_mode:
                # РЕЖИМ ПРОСЛУШИВАНИЯ - только слушаем сообщения
                await self._run_listeners()
                return
            
            # Инициализируем ботов по отдельности
            await self._init_bots()
            
            if not self.bot_inr and not self.bot_other:
                logger.error("❌ Ни один бот не может быть запущен!")
                return
            
            if self.manual_mode:
                logger.info("📊 Ручной режим: запуск отчетов последовательно...")
                await self._run_reports_sequential()
                logger.info("✅ Отчеты выполнены. Боты продолжают работать.")
                logger.info("Нажмите Ctrl+C для остановки")
            else:
                self.scheduler = AsyncIOScheduler()
                self.scheduler.add_job(
                    self._run_reports_sequential,
                    CronTrigger(hour=10, minute=0),
                    id='daily_refill_report'
                )
                logger.info("⏰ Планировщик запущен. Боты будут выполнять отчеты ежедневно в 10:00")
                self.scheduler.start()
            
            while self.running:
                await asyncio.sleep(1)
            
        except KeyboardInterrupt:
            logger.info("⏹️ Получен сигнал остановки")
        except Exception as e:
            logger.error(f"❌ Критическая ошибка: {e}")
            raise
        finally:
            await self.shutdown()
    
    async def _run_listeners(self):
        """Запуск только прослушивания (без отчетов)"""
        logger.info("🔊 Режим прослушивания...")
        logger.info("Боты будут слушать сообщения и определять ID групп и топиков")
        logger.info("Напишите сообщение в группах, чтобы бот определил ID")
        logger.info("Для остановки нажмите Ctrl+C")
        
        # Инициализируем ботов
        await self._init_bots()
        
        if not self.bot_inr and not self.bot_other:
            logger.error("❌ Ни один бот не может быть запущен!")
            return
        
        # Просто держим ботов активными
        while self.running:
            await asyncio.sleep(1)
    
    async def _init_bots(self):
        """Инициализация ботов по отдельности"""
        try:
            self.bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
            await self.bot_inr.initialize()
            logger.info("✅ Бот INR запущен")
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("⚠️ Бот INR уже запущен. Пропускаем...")
                self.bot_inr = None
            else:
                logger.error(f"❌ Ошибка запуска бота INR: {e}")
                self.bot_inr = None
        
        await asyncio.sleep(2)
        
        try:
            self.bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
            await self.bot_other.initialize()
            logger.info("✅ Бот OTHER запущен")
        except Exception as e:
            if "Conflict" in str(e):
                logger.warning("⚠️ Бот OTHER уже запущен. Пропускаем...")
                self.bot_other = None
            else:
                logger.error(f"❌ Ошибка запуска бота OTHER: {e}")
                self.bot_other = None
    
    async def _run_reports_sequential(self):
        """Запуск отчетов последовательно"""
        logger.info(f"⏰ Запуск отчетов в {datetime.now().strftime('%H:%M:%S')}")
        
        if self.bot_inr and self.bot_inr.is_ready:
            logger.info("📊 Запуск отчета для INR бота...")
            await self.bot_inr.run_daily_report()
            logger.info("✅ Отчет INR завершен")
            await asyncio.sleep(5)
        else:
            logger.warning("⚠️ INR бот не готов")
        
        if self.bot_other and self.bot_other.is_ready:
            logger.info("📊 Запуск отчета для OTHER бота...")
            await self.bot_other.run_daily_report()
            logger.info("✅ Отчет OTHER завершен")
        else:
            logger.warning("⚠️ OTHER бот не готов")
        
        logger.info("✅ Все отчеты выполнены!")
    
    async def shutdown(self):
        logger.info("🔄 Остановка системы...")
        
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("✅ Планировщик остановлен")
        
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
        '--listen',
        action='store_true',
        help='Запустить в режиме прослушивания (только определение групп)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Тестовый режим (выполнить отчет и завершить)'
    )
    
    args = parser.parse_args()
    
    if args.test:
        logger.info("🧪 Тестовый режим...")
        # ... тестовый код ...
        return
    
    manager = BotManager(manual_mode=args.manual, listen_mode=args.listen)
    await manager.run()


if __name__ == '__main__':
    asyncio.run(main())
