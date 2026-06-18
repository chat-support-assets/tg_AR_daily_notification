import asyncio
import json
from typing import Optional, Dict
from datetime import datetime
from telegram import Bot, Update
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from telegram.error import TelegramError, BadRequest, Conflict
from google_sheets import GoogleSheetsClient
from message_handler import AgentParser, MessageBuilder, should_process_agent
from agent_manager import agent_manager
from logger_setup import logger
from config import TOPIC_NAME, BOT_INR_TOKEN, BOT_OTHER_TOKEN


class RefillBot:
    """Основной бот для отчетов и прослушивания"""
    
    def __init__(self, token: str, bot_type: str):
        self.token = token
        self.bot_type = bot_type
        self.topic_name = TOPIC_NAME
        self.sheets = GoogleSheetsClient()
        self.message_builder = MessageBuilder(self.sheets.get_ar_messages())
        self.agent_manager = agent_manager
        self.application = None
        self.is_ready = False
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'no_chat': 0,
            'no_topic': 0
        }
    
    async def initialize(self):
        """Инициализация бота с обработчиками"""
        try:
            self.application = Application.builder().token(self.token).build()
            
            # Обработчик для всех сообщений в группах
            self.application.add_handler(
                MessageHandler(
                    filters.TEXT & filters.ChatType.GROUP,
                    self.handle_message
                )
            )
            
            # Обработчик для новых участников группы
            self.application.add_handler(
                MessageHandler(
                    filters.StatusUpdate.NEW_CHAT_MEMBERS,
                    self.handle_new_member
                )
            )
            
            # Запускаем бота с обработкой конфликтов
            await self.application.initialize()
            await self.application.start()
            
            # Пытаемся запустить polling с обработкой конфликтов
            try:
                await self.application.updater.start_polling()
                self.is_ready = True
                logger.info(f"✅ Бот {self.bot_type} инициализирован и запущен")
            except Conflict as e:
                logger.error(f"❌ Конфликт бота {self.bot_type}: {e}")
                logger.info(f"ℹ️ Возможно бот {self.bot_type} уже запущен в другом месте")
                self.is_ready = False
                raise
            
        except Conflict as e:
            logger.error(f"❌ Бот {self.bot_type} не может быть запущен из-за конфликта")
            self.is_ready = False
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота {self.bot_type}: {e}")
            self.is_ready = False
            raise
        
        return self.application

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик сообщений в группах для автоматического определения ID топиков
        """
        chat = update.effective_chat
        message = update.effective_message
        
        # Проверяем, что это группа
        if chat.type not in ['group', 'supergroup']:
            return
        
        # Получаем ID топика (если сообщение в топике)
        topic_id = message.message_thread_id
        
        # Если сообщение в топике
        if topic_id:
            group_name = chat.title
            
            # Проверяем, есть ли уже этот агент в кэше
            agent_data = self.agent_manager.get_agent(group_name)
            
            # Если агента нет или изменился topic_id
            if not agent_data or agent_data.get('topic_id') != topic_id:
                # Пытаемся получить название топика
                topic_name = await self._get_topic_name(chat.id, topic_id)
                
                # Если это наш топик (AR)
                if topic_name and topic_name.upper() == self.topic_name.upper():
                    # Сохраняем информацию о топике
                    self.agent_manager.update_agent(
                        group_name,
                        chat.id,
                        topic_id
                    )
                    
                    logger.info(f"✅ Автоматически определен топик AR для группы {group_name}: ID={topic_id}")
                    
                    # Отправляем подтверждение в топик (тихо, без ответа)
                    try:
                        await self.application.bot.send_message(
                            chat_id=chat.id,
                            text=f"✅ **Бот настроен!**\n\n"
                                 f"📌 Топик: {self.topic_name}\n"
                                 f"🆔 ID топика: `{topic_id}`\n"
                                 f"🌍 Тип бота: {self.bot_type}\n\n"
                                 f"Ежедневные отчеты будут приходить сюда.",
                            parse_mode='Markdown',
                            message_thread_id=topic_id
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки подтверждения: {e}")
    
    async def handle_new_member(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик добавления бота в группу
        """
        chat = update.effective_chat
        message = update.effective_message
        
        # Проверяем, что это группа
        if chat.type not in ['group', 'supergroup']:
            return
        
        # Проверяем, добавили ли нашего бота
        for member in message.new_chat_members:
            if member.id == self.application.bot.id:
                # Бота добавили в группу
                group_name = chat.title
                
                # Сохраняем базовую информацию о группе
                self.agent_manager.update_agent(group_name, chat.id, None)
                
                logger.info(f"➕ Бот {self.bot_type} добавлен в группу {group_name} (ID: {chat.id})")
                
                # Отправляем приветственное сообщение
                try:
                    await message.reply_text(
                        f"🤖 **Привет! Я бот для отчетов по скорости рефилов!**\n\n"
                        f"📌 **Группа:** {group_name}\n"
                        f"🆔 **ID группы:** `{chat.id}`\n"
                        f"🌍 **Тип бота:** {self.bot_type}\n\n"
                        f"📝 **Инструкция:**\n"
                        f"1. Создайте топик с названием **{self.topic_name}**\n"
                        f"2. Напишите любое сообщение в этот топик\n"
                        f"3. Бот автоматически определит топик и настроится\n\n"
                        f"✅ После настройки в топик будут приходить ежедневные отчеты.",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки приветствия: {e}")
                
                break
    
    async def _get_topic_name(self, chat_id: int, topic_id: int) -> Optional[str]:
        """
        Получает название топика по ID (если возможно)
        """
        try:
            # В текущей версии python-telegram-bot нет прямого метода
            # Пытаемся получить название из кэша
            for group_name, data in self.agent_manager.get_all_agents().items():
                if data.get('chat_id') == chat_id and data.get('topic_id') == topic_id:
                    return self.topic_name
            
            # Если не нашли, проверяем через отправку тестового сообщения
            # Это не даст название, но подтвердит существование топика
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text="🔍 Проверка топика...",
                    message_thread_id=topic_id
                )
                return self.topic_name
            except:
                return None
                
        except Exception as e:
            logger.error(f"❌ Ошибка получения названия топика: {e}")
            return None
    
    async def run_daily_report(self):
        """
        Основной метод для выполнения ежедневного отчета
        """
        if not self.is_ready:
            logger.warning(f"⚠️ Бот {self.bot_type} не готов. Пропускаем отчет.")
            return
        
        logger.info(f"🚀 Запуск ежедневного отчета для бота {self.bot_type}")
        
        try:
            # Получаем данные агентов
            agents_data = self.sheets.get_total_score_data()
            
            if not agents_data:
                logger.warning("⚠️ Нет данных для обработки")
                return
            
            # Сбрасываем счетчики
            self._reset_stats()
            
            # Обрабатываем каждого агента
            for agent_data in agents_data:
                try:
                    await self._process_agent(agent_data)
                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке агента {agent_data.get('agent_name', 'Unknown')}: {e}")
                    self.stats['errors'] += 1
            
            # Выводим статистику
            self._log_stats(len(agents_data))
            
        except Exception as e:
            logger.error(f"❌ Критическая ошибка при выполнении отчета: {e}")
    
    async def _process_agent(self, agent_data: dict):
        """
        Обрабатывает одного агента
        """
        agent_name = agent_data['agent_name']
        share_0_5 = agent_data['share_0_5']
        share_120 = agent_data['share_120']
        refill_count = agent_data['refill_count']
        
        # Строим сообщение
        message, group_name, geo = self.message_builder.build_message(
            agent_name, share_0_5, share_120, refill_count
        )
        
        if not message or not group_name or not geo:
            logger.warning(f"⚠️ Не удалось обработать агента: {agent_name}")
            self.stats['skipped'] += 1
            return
        
        # Проверяем, подходит ли агент под нашего бота
        if not should_process_agent(geo, self.bot_type):
            logger.info(f"⏭️ Пропускаем агента {agent_name} (ГЕО: {geo})")
            self.stats['skipped'] += 1
            return
        
        # Отправляем сообщение
        success = await self._send_to_agent(group_name, message)
        
        if success:
            self.stats['processed'] += 1
            logger.info(f"✅ Отправлено сообщение агенту {agent_name} в группу {group_name}")
        else:
            self.stats['errors'] += 1
            logger.error(f"❌ Не удалось отправить сообщение агенту {agent_name}")
    
    async def _send_to_agent(self, group_name: str, message: str) -> bool:
        """
        Отправляет сообщение агенту с полной обработкой ошибок
        """
        try:
            # Получаем данные из кэша
            chat_id = self.agent_manager.get_chat_id(group_name)
            topic_id = self.agent_manager.get_topic_id(group_name)
            
            # Проверяем наличие chat_id
            if not chat_id:
                logger.error(f"❌ Нет chat_id для группы {group_name}")
                self.stats['no_chat'] += 1
                return False
            
            # Проверяем наличие topic_id
            if not topic_id:
                logger.error(f"❌ Нет topic_id для группы {group_name}")
                self.stats['no_topic'] += 1
                return False
            
            # Пытаемся отправить сообщение
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    parse_mode='Markdown',
                    message_thread_id=topic_id
                )
                return True
                
            except BadRequest as e:
                error_msg = str(e).lower()
                
                if "chat not found" in error_msg:
                    logger.error(f"❌ Чат {chat_id} не найден. Удаляем из кэша.")
                    # Удаляем из кэша
                    agents = self.agent_manager.get_all_agents()
                    if group_name in agents:
                        del agents[group_name]
                        self.agent_manager.save_cache()
                        
                elif "topic" in error_msg or "message_thread" in error_msg:
                    logger.error(f"❌ Топик {topic_id} не найден. Пытаемся найти новый...")
                    # Пытаемся найти новый топик
                    found = await self._find_and_update_topic(chat_id, group_name)
                    if found:
                        # Повторяем отправку
                        return await self._send_to_agent(group_name, message)
                else:
                    logger.error(f"❌ Ошибка отправки: {e}")
                    
                return False
                
            except TelegramError as e:
                logger.error(f"❌ Telegram ошибка: {e}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке: {e}")
            return False
    
    async def _find_and_update_topic(self, chat_id: int, group_name: str) -> bool:
        """
        Ищет и обновляет ID топика
        """
        try:
            # Проверяем, есть ли сохраненный топик
            current_topic = self.agent_manager.get_topic_id(group_name)
            
            # Пытаемся отправить тестовое сообщение в разные возможные топики
            # В текущей версии мы не можем получить список топиков
            # Поэтому предлагаем пользователю написать в топик заново
            
            # Отправляем сообщение в главный чат с инструкцией
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=f"⚠️ **Топик не найден!**\n\n"
                         f"Пожалуйста, создайте топик **{self.topic_name}**\n"
                         f"или напишите сообщение в существующий топик.\n\n"
                         f"Бот автоматически определит топик после вашего сообщения.",
                    parse_mode='Markdown'
                )
            except:
                pass
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска топика: {e}")
            return False
    
    def _reset_stats(self):
        """Сбрасывает статистику"""
        for key in self.stats:
            self.stats[key] = 0
    
    def _log_stats(self, total_agents: int):
        """
        Логирует статистику выполнения
        """
        logger.info(f"""
        📊 Статистика отчета ({self.bot_type}):
        ─────────────────────────────
        ✅ Обработано:   {self.stats['processed']}
        ⏭️ Пропущено:    {self.stats['skipped']}
        ❌ Ошибок:       {self.stats['errors']}
        📭 Нет чата:     {self.stats['no_chat']}
        📌 Нет топика:   {self.stats['no_topic']}
        ─────────────────────────────
        📌 Всего агентов: {total_agents}
        """)
    
    async def shutdown(self):
        """Останавливает бота"""
        if self.application:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            logger.info(f"⏹️ Бот {self.bot_type} остановлен")


# Глобальные экземпляры ботов
bot_inr = None
bot_other = None


async def initialize_bots():
    """Инициализация обоих ботов"""
    global bot_inr, bot_other
    
    bot_inr = RefillBot(BOT_INR_TOKEN, 'INR')
    bot_other = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
    
    await bot_inr.initialize()
    await bot_other.initialize()
    
    logger.info("✅ Оба бота инициализированы и запущены")


async def run_daily_reports():
    """Запуск ежедневных отчетов для обоих ботов"""
    global bot_inr, bot_other
    
    if bot_inr and bot_other:
        await asyncio.gather(
            bot_inr.run_daily_report(),
            bot_other.run_daily_report()
        )
    else:
        logger.error("❌ Боты не инициализированы")


async def shutdown_bots():
    """Остановка обоих ботов"""
    global bot_inr, bot_other
    
    if bot_inr:
        await bot_inr.shutdown()
    if bot_other:
        await bot_other.shutdown()
