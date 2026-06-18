import asyncio
from bot_base import RefillBot
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from logger_setup import logger


async def run_listener(token: str, bot_type: str):
    """
    Запускает бота в режиме прослушивания
    """
    bot = RefillBot(token, bot_type)
    await bot.initialize()
    await bot.setup_topic_listener()


async def main():
    """Запускает обоих ботов в режиме прослушивания"""
    try:
        logger.info("🚀 Запуск ботов в режиме прослушивания...")
        
        # Запускаем обоих ботов
        await asyncio.gather(
            run_listener(BOT_INR_TOKEN, 'INR'),
            run_listener(BOT_OTHER_TOKEN, 'OTHER')
        )
        
    except KeyboardInterrupt:
        logger.info("⏹️ Боты остановлены пользователем")
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске: {e}")


if __name__ == '__main__':
    asyncio.run(main())
