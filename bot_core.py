# bot_core.py - Полностью исправленная версия

import asyncio
import json
import random
from typing import Optional, Dict, List
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
        self.sheets = None  # Будет инициализирован позже
        self.message_builder = None
        self.agent_manager = agent_manager
        self.application = None
        self.is_ready = False
        
        # Кэш для отслеживания обработанных групп
        self.processed_groups = set()
        
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
            # Инициализируем Google Sheets с небольшой случайной задержкой
            # чтобы оба бота не обращались одновременно
            delay = random.uniform(0.5, 2.0)
            logger.info(f"⏳ Задержка {delay:.1f} сек перед инициализацией Google Sheets...")
            await asyncio.sleep(delay)
            
            self.sheets = GoogleSheetsClient()
            self.message_builder = MessageBuilder(self.sheets.get_ar_messages())
            
            self.application = Application.builder().token(self.token).build()
            
            # Обработчик для всех текстовых сообщений в группах
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
            
            # Запускаем бота
            await self.application.initialize()
            await self.application.start()
            
            try:
                await self.application.updater.start_polling()
                self.is_ready = True
                logger.info(f"✅ Бот {self.bot_type} инициализирован и запущен")
                
                # После запуска проверяем все группы, где уже есть бот
                await self._scan_existing_groups()
                
            except Conflict as e:
                logger.error(f"❌ Конфликт бота {self.bot_type}: {e}")
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
    
    async def _scan_existing_groups(self):
        """
        Сканирует все группы, где есть бот, для поиска топика AR
        """
        logger.info(f"🔍 Сканирование существующих групп для бота {self.bot_type}...")
        
        try:
            # Получаем все группы из кэша
            all_agents = self.agent_manager.get_all_agents()
            
            if not all_agents:
                logger.info("ℹ️ Нет сохраненных групп для сканирования")
                return
            
            found_topics = 0
            
            for group_name, data in all_agents.items():
                chat_id = data.get('chat_id')
                
                if not chat_id:
                    continue
                
                # Проверяем, есть ли уже topic_id
                if data.get('topic_id'):
                    logger.info(f"✅ Группа {group_name} уже имеет топик: {data['topic_id']}")
                    found_topics += 1
                    continue
                
                # Пытаемся найти топик AR в этой группе
                logger.info(f"🔍 Ищем топик '{self.topic_name}' в группе {group_name}")
                
                try:
                    # Отправляем сообщение с просьбой написать в топик
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=f"🔍 **Поиск топика '{self.topic_name}'**\n\n"
                             f"Я ищу топик для отправки отчетов.\n\n"
                             f"Если в этой группе уже есть топик **{self.topic_name}**,\n"
                             f"пожалуйста, напишите любое сообщение в этот топик.\n\n"
                             f"Если топика нет - создайте его с названием **{self.topic_name}**\n"
                             f"и напишите сообщение туда.\n\n"
                             f"Бот автоматически определит топик и настроится!",
                        parse_mode='Markdown'
                    )
                    
                    # Ждем немного для обработки
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"❌ Ошибка при сканировании группы {group_name}: {e}")
            
            logger.info(f"✅ Сканирование завершено. Найдено топиков: {found_topics}/{len(all_agents)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сканирования групп: {e}")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик сообщений в группах для автоматического определения ID топиков
        """
        chat = update.effective_chat
        message = update.effective_message
        
        # Проверяем, что это группа
        if chat.type not in ['group', 'supergroup']:
            return
        
        # Проверяем, что сообщение от пользователя (не от бота)
        if not message.from_user or message.from_user.is_bot:
            return
        
        # Получаем ID топика (если сообщение в топике)
        topic_id = message.message_thread_id
        
        # Получаем название группы
        group_name = chat.title
        
        # Проверяем, обрабатывали ли уже эту группу
        group_key = f"{chat.id}_{topic_id if topic_id else 'main'}"
        if group_key in self.processed_groups:
            return
        
        # Если сообщение в топике
        if topic_id:
            # Проверяем название топика
            is_ar_topic = await self._check_is_ar_topic(chat.id, topic_id)
            
            if is_ar_topic:
                # Сохраняем информацию о топике
                self.agent_manager.update_agent(
                    group_name,
                    chat.id,
                    topic_id
                )
                
                self.processed_groups.add(group_key)
                
                logger.info(f"✅ Автоматически определен топик AR для группы {group_name}: ID={topic_id}")
                
                # Отправляем подтверждение в топик
                try:
                    await self.application.bot.send_message(
                        chat_id=chat.id,
                        text=f"✅ **Бот настроен!**\n\n"
                             f"📌 **Группа:** {group_name}\n"
                             f"🆔 **ID группы:** `{chat.id}`\n"
                             f"📌 **Топик:** {self.topic_name}\n"
                             f"🆔 **ID топика:** `{topic_id}`\n"
                             f"🌍 **Тип бота:** {self.bot_type}\n\n"
                             f"📊 Ежедневные отчеты будут приходить сюда.\n"
                             f"⏰ Время отправки: 10:00 ежедневно",
                        parse_mode='Markdown',
                        message_thread_id=topic_id
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки подтверждения: {e}")
        else:
            # Сообщение не в топике - проверяем, есть ли у группы уже топик
            existing = self.agent_manager.get_agent(group_name)
            
            if not existing or existing.get('chat_id') != chat.id:
                self.agent_manager.update_agent(group_name, chat.id, None)
                logger.info(f"✅ Сохранена группа {group_name} (ID: {chat.id})")
                
                # Проверяем, есть ли уже топик AR в этой группе
                await self._find_existing_topic_in_group(chat.id, group_name)
                
                # Отправляем инструкцию
                try:
                    await message.reply_text(
                        f"🤖 **Привет! Я бот для отчетов по скорости рефилов!**\n\n"
                        f"📌 **Группа:** {group_name}\n"
                        f"🆔 **ID группы:** `{chat.id}`\n"
                        f"🌍 **Тип бота:** {self.bot_type}\n\n"
                        f"📝 **Для настройки:**\n"
                        f"1. Создайте топик с названием **{self.topic_name}**\n"
                        f"2. Напишите любое сообщение в этот топик\n"
                        f"3. Бот автоматически определит топик и настроится\n\n"
                        f"✅ После настройки в топик будут приходить ежедневные отчеты.",
                        parse_mode='Markdown'
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки инструкции: {e}")
    
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
                
                # Проверяем, есть ли уже топик AR в этой группе
                await self._find_existing_topic_in_group(chat.id, group_name)
                
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
    
    async def _find_existing_topic_in_group(self, chat_id: int, group_name: str):
        """
        Пытается найти существующий топик AR в группе
        """
        logger.info(f"🔍 Проверяем наличие топика '{self.topic_name}' в группе {group_name}")
        
        try:
            # Проверяем, нет ли уже сохраненного топика
            agent_data = self.agent_manager.get_agent(group_name)
            if agent_data and agent_data.get('topic_id'):
                logger.info(f"✅ Топик уже сохранен для группы {group_name}: {agent_data['topic_id']}")
                return
            
            # Отправляем сообщение с просьбой написать в топик
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"🔍 **Поиск топика '{self.topic_name}'**\n\n"
                     f"Я ищу топик для отправки отчетов.\n\n"
                     f"Если в этой группе уже есть топик **{self.topic_name}**,\n"
                     f"пожалуйста, напишите любое сообщение в этот топик.\n\n"
                     f"Если топика нет - создайте его с названием **{self.topic_name}**\n"
                     f"и напишите сообщение туда.\n\n"
                     f"Бот автоматически определит топик и настроится!",
                parse_mode='Markdown'
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска топика в группе {group_name}: {e}")
    
    async def _check_is_ar_topic(self, chat_id: int, topic_id: int) -> bool:
        """
        Проверяет, является ли топик нужным (AR)
        """
        try:
            # Проверяем по кэшу
            for group_name, data in self.agent_manager.get_all_agents().items():
                if data.get('chat_id') == chat_id and data.get('topic_id') == topic_id:
                    return True
            
            # Проверяем, есть ли уже сохраненный топик с таким ID
            for group_name, data in self.agent_manager.get_all_agents().items():
                if data.get('topic_id') == topic_id:
                    return True
            
            # Если топик не найден в кэше, считаем его AR топиком
            # (пользователь сам написал в него)
            return True
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки топика: {e}")
            return False
    
    async def run_daily_report(self):
        """Основной метод для выполнения ежедневного отчета"""
        if not self.is_ready:
            logger.warning(f"⚠️ Бот {self.bot_type} не готов. Пропускаем отчет.")
            return
        
        logger.info(f"🚀 Запуск ежедневного отчета для бота {self.bot_type}")
        
        try:
            # Добавляем случайную задержку перед чтением таблицы
            # чтобы оба бота не обращались одновременно
            delay = random.uniform(1.0, 3.0)
            logger.info(f"⏳ Задержка {delay:.1f} секунд перед чтением таблицы...")
            await asyncio.sleep(delay)
            
            # Получаем данные агентов
            agents_data = self.sheets.get_total_score_data()
            
            if not agents_data:
                logger.warning("⚠️ Нет данных для обработки")
                return
            
            # Сбрасываем счетчики
            self._reset_stats()
            
            # Обрабатываем каждого агента с задержкой между отправками
            for idx, agent_data in enumerate(agents_data):
                try:
                    await self._process_agent(agent_data)
                    # Задержка между отправками сообщений (чтобы не спамить)
                    if idx < len(agents_data) - 1:
                        await asyncio.sleep(random.uniform(0.5, 1.5))
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
        
        # Пропускаем агентов с None значениями для 0-5 минут
        if share_0_5 is None:
            logger.warning(f"⚠️ Пропускаем агента {agent_name}: нет данных по скорости 0-5")
            self.stats['skipped'] += 1
            return
        
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
        Отправляет сообщение агенту
        """
        try:
            # Получаем данные из кэша
            chat_id = self.agent_manager.get_chat_id(group_name)
            topic_id = self.agent_manager.get_topic_id(group_name)
            
            # Если нет chat_id, пробуем найти группу по точному совпадению
            if not chat_id:
                all_agents = self.agent_manager.get_all_agents()
                
                # Ищем точное совпадение (без учета регистра)
                for name, data in all_agents.items():
                    if name.lower() == group_name.lower():
                        chat_id = data.get('chat_id')
                        topic_id = data.get('topic_id')
                        logger.info(f"🔍 Найдено совпадение для {group_name} -> {name}")
                        break
                
                # Если все равно не нашли, логируем и пропускаем
                if not chat_id:
                    logger.error(f"❌ Нет chat_id для группы {group_name}")
                    logger.info(f"ℹ️ Доступные группы в кэше: {list(all_agents.keys())}")
                    self.stats['no_chat'] += 1
                    return False
            
            # Если нет topic_id, отправляем в главный чат
            if not topic_id:
                logger.warning(f"⚠️ Нет topic_id для группы {group_name}, отправляем в главный чат")
                try:
                    await self.application.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode='Markdown'
                    )
                    return True
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки в главный чат: {e}")
                    self.stats['no_topic'] += 1
                    return False
            
            # Отправляем в топик
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
                    self.agent_manager.remove_agent(group_name)
                    self.stats['no_chat'] += 1
                elif "topic" in error_msg or "message_thread" in error_msg:
                    logger.error(f"❌ Топик {topic_id} не найден. Пробуем отправить в главный чат...")
                    try:
                        await self.application.bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode='Markdown'
                        )
                        # Обновляем topic_id на None
                        self.agent_manager.update_topic_id(group_name, None)
                        return True
                    except:
                        self.stats['no_topic'] += 1
                        return False
                else:
                    logger.error(f"❌ Ошибка отправки: {e}")
                    self.stats['errors'] += 1
                return False
                
            except TelegramError as e:
                logger.error(f"❌ Telegram ошибка: {e}")
                self.stats['errors'] += 1
                return False
                
        except Exception as e:
            logger.error(f"❌ Ошибка при отправке: {e}")
            self.stats['errors'] += 1
            return False
    
    def _reset_stats(self):
        """Сбрасывает статистику"""
        for key in self.stats:
            self.stats[key] = 0
    
    def _log_stats(self, total_agents: int):
        """Логирует статистику выполнения"""
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
