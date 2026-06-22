#!/usr/bin/env python
# main.py - Точка входа

import asyncio
import sys
import argparse
from bot_telethon import RefillBot
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from logger_setup import logger


async def run_inr_bot():
    """Запуск INR бота"""
    bot = RefillBot(BOT_INR_TOKEN, 'INR')
    await bot.run()


async def run_other_bot():
    """Запуск OTHER бота"""
    bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
    await bot.run()


async def run_report(bot_type: str = 'both'):
    """Запуск отчетов"""
    logger.info(f"📊 Запуск отчетов для {bot_type}...")
    
    if bot_type in ['inr', 'both']:
        bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
        await bot_inr.initialize()
        await bot_inr.run_daily_report()
        await bot_inr.shutdown()
        logger.info("✅ Отчет INR завершен")
    
    if bot_type in ['other', 'both']:
        bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
        await bot_other.initialize()
        await bot_other.run_daily_report()
        await bot_other.shutdown()
        logger.info("✅ Отчет OTHER завершен")
    
    logger.info("✅ Все отчеты завершены")


async def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Бот для отчетов по скорости рефилов')
    parser.add_argument(
        '--report',
        action='store_true',
        help='Запустить отчет и завершить'
    )
    parser.add_argument(
        '--bot',
        choices=['inr', 'other', 'both'],
        default='both',
        help='Какой бот запустить'
    )
    
    args = parser.parse_args()
    
    try:
        if args.report:
            await run_report(args.bot)
            return
        
        # Обычный режим - слушаем сообщения
        logger.info("🚀 Запуск ботов...")
        
        if args.bot == 'inr':
            await run_inr_bot()
        elif args.bot == 'other':
            await run_other_bot()
        else:
            # Запускаем обоих ботов параллельно
            await asyncio.gather(
                run_inr_bot(),
                run_other_bot()
            )
            
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка ботов...")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    asyncio.run(main())
