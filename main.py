import asyncio
import argparse
from bot_aiogram import RefillBot, run_inr_bot, run_other_bot
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from logger_setup import logger


async def run_report(bot_type: str = 'both'):
    """Запуск отчетов"""
    logger.info(f"📊 Запуск отчетов для {bot_type}...")
    
    if bot_type in ['inr', 'both']:
        bot = RefillBot(BOT_INR_TOKEN, 'INR')
        await bot.initialize()
        await bot.run_daily_report()
        await bot.shutdown()
        logger.info("✅ Отчет INR завершен")
    
    if bot_type in ['other', 'both']:
        bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
        await bot.initialize()
        await bot.run_daily_report()
        await bot.shutdown()
        logger.info("✅ Отчет OTHER завершен")
    
    logger.info("✅ Все отчеты завершены")


async def main():
    parser = argparse.ArgumentParser(description='Бот для отчетов по скорости рефилов')
    parser.add_argument('--report', action='store_true', help='Запустить отчет и завершить')
    parser.add_argument('--bot', choices=['inr', 'other', 'both'], default='both', help='Какой бот запустить')
    
    args = parser.parse_args()
    
    try:
        if args.report:
            await run_report(args.bot)
            return
        
        logger.info("🚀 Запуск ботов...")
        
        if args.bot == 'inr':
            await run_inr_bot()
        elif args.bot == 'other':
            await run_other_bot()
        else:
            # Запускаем обоих ботов параллельно
            await asyncio.gather(run_inr_bot(), run_other_bot())
            
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка...")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")


if __name__ == '__main__':
    asyncio.run(main())
