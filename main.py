#!/usr/bin/env python
# main.py - Точка входа с оптимизацией

import asyncio
import argparse
import signal
from bot_aiogram import RefillBot, run_inr_bot, run_other_bot
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from logger_setup import logger


async def run_report(bot_type: str = 'both'):
    """Запуск отчетов"""
    logger.info(f"📊 Запуск отчетов для {bot_type}...")
    
    results = []
    
    if bot_type in ['inr', 'both']:
        try:
            bot = RefillBot(BOT_INR_TOKEN, 'INR')
            await bot.initialize()
            await bot.run_daily_report()
            await bot.shutdown()
            logger.info("✅ Отчет INR завершен")
            results.append(True)
        except Exception as e:
            logger.error(f"❌ Ошибка отчета INR: {e}")
            results.append(False)
    
    if bot_type in ['other', 'both']:
        try:
            bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
            await bot.initialize()
            await bot.run_daily_report()
            await bot.shutdown()
            logger.info("✅ Отчет OTHER завершен")
            results.append(True)
        except Exception as e:
            logger.error(f"❌ Ошибка отчета OTHER: {e}")
            results.append(False)
    
    if all(results):
        logger.info("✅ Все отчеты успешно выполнены!")
    else:
        logger.warning("⚠️ Некоторые отчеты завершились с ошибками")


async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Бот для отчетов по скорости рефилов')
    parser.add_argument('--report', action='store_true', help='Запустить отчет и завершить')
    parser.add_argument('--bot', choices=['inr', 'other', 'both'], default='both', help='Какой бот запустить')
    
    args = parser.parse_args()
    
    # Настройка обработки сигналов
    loop = asyncio.get_event_loop()
    
    try:
        if args.report:
            await run_report(args.bot)
            return
        
        logger.info("🚀 Запуск ботов...")
        logger.info("   INR бот: обрабатывает агентов с ГЕО INR")
        logger.info("   OTHER бот: обрабатывает всех остальных агентов")
        logger.info("   Нажмите Ctrl+C для остановки")
        logger.info("")
        
        # Запускаем ботов
        if args.bot == 'inr':
            await run_inr_bot()
        elif args.bot == 'other':
            await run_other_bot()
        else:
            # Запускаем обоих ботов параллельно
            tasks = [
                asyncio.create_task(run_inr_bot()),
                asyncio.create_task(run_other_bot())
            ]
            
            # Ждем завершения или прерывания
            try:
                await asyncio.gather(*tasks)
            except asyncio.CancelledError:
                logger.info("⏹️ Задачи отменены")
                for task in tasks:
                    task.cancel()
            
    except KeyboardInterrupt:
        logger.info("⏹️ Получен сигнал остановки")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
    finally:
        # Закрываем все открытые сессии
        logger.info("🔄 Завершение работы...")


if __name__ == '__main__':
    asyncio.run(main())
