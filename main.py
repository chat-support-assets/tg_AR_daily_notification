#!/usr/bin/env python
# main.py - Точка входа с планировщиком (автоматический режим)

import asyncio
import signal
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bot_aiogram import RefillBot, run_inr_bot, run_other_bot
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from logger_setup import logger


# Глобальные переменные для ботов
bot_inr_instance = None
bot_other_instance = None
scheduler = None


async def run_report(bot_type: str = 'both'):
    """Запуск отчетов"""
    logger.info(f"📊 Запуск отчетов для {bot_type}...")
    
    results = []
    
    if bot_type in ['inr', 'both']:
        try:
            if bot_inr_instance and bot_inr_instance.is_ready:
                await bot_inr_instance.run_daily_report()
            else:
                bot = RefillBot(BOT_INR_TOKEN, 'INR')
                await bot.initialize()
                await bot.run_daily_report()
                await bot.shutdown()
            results.append(True)
        except Exception as e:
            logger.error(f"❌ Ошибка отчета INR: {e}")
            results.append(False)
    
    if bot_type in ['other', 'both']:
        try:
            if bot_other_instance and bot_other_instance.is_ready:
                await bot_other_instance.run_daily_report()
            else:
                bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
                await bot.initialize()
                await bot.run_daily_report()
                await bot.shutdown()
            results.append(True)
        except Exception as e:
            logger.error(f"❌ Ошибка отчета OTHER: {e}")
            results.append(False)
    
    if all(results):
        logger.info("✅ Все отчеты успешно выполнены!")
    else:
        logger.warning("⚠️ Некоторые отчеты завершились с ошибками")


async def scheduled_report():
    """Запуск отчета по расписанию"""
    logger.info(f"⏰ Плановый запуск отчетов в {datetime.now().strftime('%H:%M:%S')}")
    await run_report('both')


async def shutdown(signum=None, frame=None):
    """Graceful shutdown"""
    logger.info("⏹️ Получен сигнал остановки. Завершаем работу...")
    
    # Останавливаем планировщик
    if scheduler:
        scheduler.shutdown()
        logger.info("✅ Планировщик остановлен")
    
    # Останавливаем ботов
    if bot_inr_instance:
        await bot_inr_instance.shutdown()
    if bot_other_instance:
        await bot_other_instance.shutdown()
    
    logger.info("✅ Система полностью остановлена")


async def main():
    """Основная функция"""
    global bot_inr_instance, bot_other_instance, scheduler
    
    logger.info("🚀 Запуск системы...")
    logger.info("📅 Ежедневные отчеты будут отправляться в 12:00")
    logger.info("Нажмите Ctrl+C для остановки")
    
    # Создаем планировщик
    scheduler = AsyncIOScheduler()
    
    # Добавляем задание на каждый день в 12:00
    scheduler.add_job(
        scheduled_report,
        CronTrigger(hour=12, minute=0),
        id='daily_report',
        replace_existing=True
    )
    
    # Запускаем планировщик
    scheduler.start()
    logger.info("✅ Планировщик запущен")
    
    # Инициализируем и запускаем ботов
    bot_inr_instance = RefillBot(BOT_INR_TOKEN, 'INR')
    bot_other_instance = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
    
    # Запускаем ботов параллельно
    tasks = [
        asyncio.create_task(bot_inr_instance.run()),
        asyncio.create_task(bot_other_instance.run())
    ]
    
    # Настройка обработки сигналов
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown()))
    
    # Ждем завершения
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("⏹️ Задачи отменены")
        for task in tasks:
            task.cancel()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        await shutdown()


if __name__ == '__main__':
    asyncio.run(main())
