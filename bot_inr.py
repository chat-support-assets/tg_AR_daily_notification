import asyncio
from bot_base import RefillBot
from config import BOT_INR_TOKEN
from logger_setup import logger


async def main():
    """Основная функция для запуска бота INR"""
    try:
        bot = RefillBot(
            token=BOT_INR_TOKEN,
            bot_type='INR'
        )
        
        await bot.run_daily_report()
        logger.info("✅ Отчет для INR успешно завершен")
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в боте INR: {e}")
        raise


if __name__ == '__main__':
    asyncio.run(main())
