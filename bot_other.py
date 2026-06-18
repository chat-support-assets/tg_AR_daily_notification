import asyncio
from bot_base import RefillBot
from config import BOT_OTHER_TOKEN
from logger_setup import logger


async def main():
    """Основная функция для запуска бота OTHER"""
    try:
        bot = RefillBot(
            token=BOT_OTHER_TOKEN,
            bot_type='OTHER'
        )
        
        await bot.run_daily_report()
        logger.info("✅ Отчет для OTHER успешно завершен")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в боте OTHER: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())
