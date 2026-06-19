#!/usr/bin/env python
# check_bot.py - Проверка получения обновлений

import asyncio
from telegram import Bot
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from logger_setup import logger


async def check_bot(token, name):
    """Проверяет, получает ли бот обновления"""
    logger.info(f"🔍 Проверка бота {name}...")
    
    try:
        bot = Bot(token)
        
        # Проверяем, что бот существует
        me = await bot.get_me()
        logger.info(f"   ✅ Бот найден: @{me.username}")
        
        # Пытаемся получить обновления
        updates = await bot.get_updates(limit=10)
        
        if updates:
            logger.info(f"   ✅ Получено {len(updates)} обновлений")
            for update in updates[:3]:
                if update.message:
                    chat = update.message.chat
                    logger.info(f"      📩 Сообщение из {chat.title} (ID: {chat.id})")
                    logger.info(f"         Текст: {update.message.text}")
        else:
            logger.warning(f"   ⚠️ Нет обновлений. Бот не получает сообщения!")
            logger.warning(f"   Проверьте:")
            logger.warning(f"      1. Добавлен ли бот в группы")
            logger.warning(f"      2. Включен ли Privacy Mode")
            logger.warning(f"      3. Есть ли права администратора")
        
    except Exception as e:
        logger.error(f"   ❌ Ошибка: {e}")


async def main():
    logger.info("🧪 Проверка ботов...")
    await check_bot(BOT_INR_TOKEN, "INR")
    await asyncio.sleep(1)
    await check_bot(BOT_OTHER_TOKEN, "OTHER")


if __name__ == '__main__':
    asyncio.run(main())