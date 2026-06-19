#!/usr/bin/env python
# test_bot.py - Тестовый бот для сохранения ID групп и топиков

import asyncio
import signal
from typing import Dict
from telegram import Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.error import Conflict, BadRequest
from config import BOT_INR_TOKEN, BOT_OTHER_TOKEN
from agent_manager import agent_manager
from logger_setup import logger
from models import GroupInfo
from datetime import datetime


class TestBot:
    """Тестовый бот для сохранения ID групп и топиков"""
    
    def __init__(self, token: str, bot_type: str):
        self.token = token
        self.bot_type = bot_type
        self.application = None
        self.running = True
        
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
    
    def signal_handler(self, signum, frame):
        logger.info(f"⏹️ Получен сигнал остановки для {self.bot_type}")
        self.running = False
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик сообщений - сохраняет chat_id, topic_id и название группы
        """
        chat = update.effective_chat
        message = update.effective_message
        
        # Проверяем, что это группа
        if chat.type not in ['group', 'supergroup']:
            try:
                await message.reply_text("ℹ️ Этот бот работает только в группах!")
            except:
                pass
            return
        
        # Проверяем, что сообщение от пользователя (не от бота)
        if not message.from_user or message.from_user.is_bot:
            return
        
        # Получаем данные
        group_name = chat.title
        chat_id = chat.id
        topic_id = message.message_thread_id  # None если не в топике
        user_name = message.from_user.full_name or message.from_user.username or "Пользователь"
        
        # Определяем, в топике сообщение или нет
        location = "ТОПИК" if topic_id else "ГРУППА"
        topic_info = f" (ID топика: {topic_id})" if topic_id else ""
        
        # Логируем
        logger.info(f"📩 [{self.bot_type}] Сообщение из {location}")
        logger.info(f"   Группа: {group_name}")
        logger.info(f"   Chat ID: {chat_id}")
        logger.info(f"   Topic ID: {topic_id}")
        logger.info(f"   От: {user_name}")
        logger.info(f"   Текст: {message.text[:50] if message.text else '...'}...")
        
        # Сохраняем в agent_manager
        agent_manager.update_agent(
            group_name=group_name,
            chat_id=chat_id,
            topic_id=topic_id
        )
        
        # Отвечаем (без Markdown, обычным текстом)
        try:
            response_lines = [
                "✅ Данные сохранены!",
                "",
                f"📌 Группа: {group_name}",
                f"🆔 ID группы: {chat_id}",
                f"🌍 Тип бота: {self.bot_type}"
            ]
            
            if topic_id:
                response_lines.append(f"📌 ID топика: {topic_id}")
                response_lines.append("📍 Место: Топик")
                response_lines.append("")
                response_lines.append("✅ Топик сохранен для отправки отчетов!")
            else:
                response_lines.append("")
                response_lines.append("📝 Создайте топик 'AR' и напишите в него сообщение,")
                response_lines.append("чтобы бот определил ID топика.")
                response_lines.append("")
                response_lines.append("📌 Текущий chat_id сохранен в agents.json")
            
            response_lines.append("")
            response_lines.append("📁 Проверьте файл agents.json")
            
            response_text = "\n".join(response_lines)
            
            await message.reply_text(response_text)
            
        except BadRequest as e:
            logger.error(f"❌ Ошибка отправки ответа (BadRequest): {e}")
            # Пробуем отправить простое сообщение без форматирования
            try:
                await message.reply_text("✅ Данные сохранены! Проверьте agents.json")
            except:
                pass
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ответа: {e}")
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик добавления бота в группу
        """
        chat = update.effective_chat
        message = update.effective_message
        
        if chat.type not in ['group', 'supergroup']:
            return
        
        for member in message.new_chat_members:
            if member.id == self.application.bot.id:
                group_name = chat.title
                chat_id = chat.id
                
                # Сохраняем группу
                agent_manager.update_agent(group_name, chat_id, None)
                
                logger.info(f"➕ [{self.bot_type}] Бот добавлен в группу: {group_name} (ID: {chat_id})")
                
                # Отправляем приветствие (без Markdown)
                try:
                    response_lines = [
                        f"🤖 Привет! Я тестовый бот для {self.bot_type}",
                        "",
                        f"📌 Группа: {group_name}",
                        f"🆔 ID группы: {chat_id}",
                        f"🌍 Тип бота: {self.bot_type}",
                        "",
                        "📝 Инструкция:",
                        "1. Напишите любое сообщение в группе",
                        "2. Создайте топик AR и напишите в него сообщение",
                        "3. Бот сохранит все ID в agents.json"
                    ]
                    
                    await message.reply_text("\n".join(response_lines))
                    
                except BadRequest as e:
                    logger.error(f"❌ Ошибка отправки приветствия (BadRequest): {e}")
                    try:
                        await message.reply_text(f"🤖 Привет! Я бот для {self.bot_type}. Данные сохранены.")
                    except:
                        pass
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки приветствия: {e}")
                
                break
    
    async def run(self):
        """Запуск бота"""
        try:
            logger.info(f"🚀 Запуск тестового бота {self.bot_type}...")
            
            self.application = Application.builder().token(self.token).build()
            
            # Обработчик текстовых сообщений
            self.application.add_handler(
                MessageHandler(
                    filters.TEXT & filters.ChatType.GROUP,
                    self.handle_message
                )
            )
            
            # Обработчик новых участников
            self.application.add_handler(
                MessageHandler(
                    filters.StatusUpdate.NEW_CHAT_MEMBERS,
                    self.handle_new_member
                )
            )
            
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()
            
            logger.info(f"✅ Тестовый бот {self.bot_type} запущен")
            logger.info("📌 Ожидание сообщений...")
            logger.info("   Напишите сообщение в группе или топике для сохранения ID")
            
            while self.running:
                await asyncio.sleep(1)
            
        except Conflict:
            logger.warning(f"⚠️ Бот {self.bot_type} уже запущен в другом месте")
            logger.info("   Пропускаем...")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска бота {self.bot_type}: {e}")
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Остановка бота"""
        if self.application:
            try:
                await self.application.updater.stop()
                await self.application.stop()
                await self.application.shutdown()
            except:
                pass
            logger.info(f"⏹️ Тестовый бот {self.bot_type} остановлен")


async def main():
    """Запуск обоих тестовых ботов"""
    logger.info("🧪 Запуск тестовых ботов для сохранения ID групп...")
    logger.info("=" * 60)
    logger.info("📌 Инструкция:")
    logger.info("   1. Добавьте ботов в группы")
    logger.info("   2. Напишите сообщение в группе")
    logger.info("   3. Создайте топик 'AR' и напишите в него")
    logger.info("   4. Боты сохранят все ID в agents.json")
    logger.info("=" * 60)
    
    # Создаем ботов
    bot_inr = TestBot(BOT_INR_TOKEN, 'INR')
    bot_other = TestBot(BOT_OTHER_TOKEN, 'OTHER')
    
    # Запускаем параллельно
    try:
        await asyncio.gather(
            bot_inr.run(),
            bot_other.run()
        )
    except KeyboardInterrupt:
        logger.info("⏹️ Остановка тестовых ботов...")
    finally:
        await bot_inr.shutdown()
        await bot_other.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
