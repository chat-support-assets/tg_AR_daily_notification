#!/usr/bin/env python
# bot_telethon.py - Боты на Telethon (только боты)

import asyncio
from typing import Optional
from datetime import datetime
from telethon import TelegramClient, events
from telethon.tl.types import Message

from config import (
    BOT_INR_TOKEN, BOT_OTHER_TOKEN,
    TOPIC_NAME
)
from agent_manager import agent_manager
from data_processor import DataProcessor
from models import AgentData, ProcessedData
from logger_setup import logger


class RefillBot:
    """Бот на Telethon для отправки отчетов и прослушивания"""
    
    def __init__(self, token: str, bot_type: str):
        self.token = token
        self.bot_type = bot_type
        self.client = None
        self.is_ready = False
        self.data_processor = DataProcessor()
        self.agent_manager = agent_manager
        
        # Кэш для отслеживания обработанных групп
        self.processed_groups = set()
        
        # Статистика
        self.stats = {
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'no_chat': 0,
            'no_topic': 0
        }
    
    async def initialize(self):
        """Инициализация бота"""
        try:
            # Создаем клиента Telethon для бота
            # Для бота API ID и Hash не нужны, передаем 0 и пустую строку
            self.client = TelegramClient(
                f'bot_{self.bot_type}',
                api_id=1,  # Должно быть число, не 0
                api_hash=''  # Пустая строка для ботов
            )
            
            # Авторизуемся как бот
            await self.client.start(bot_token=self.token)
            
            self.is_ready = True
            logger.info(f"✅ Бот {self.bot_type} инициализирован")
            
            # Получаем информацию о боте
            me = await self.client.get_me()
            logger.info(f"   Бот: @{me.username} (ID: {me.id})")
            
            # Регистрируем обработчики
            @self.client.on(events.NewMessage)
            async def handle_message(event):
                await self._handle_message(event)
            
            @self.client.on(events.ChatAction)
            async def handle_chat_action(event):
                await self._handle_chat_action(event)
            
            logger.info(f"✅ Бот {self.bot_type} запущен и слушает сообщения")
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота {self.bot_type}: {e}")
            raise
    
    async def _handle_message(self, event):
        """
        Обработчик сообщений
        """
        # Проверяем, что это группа
        if not event.is_group:
            return
        
        # Проверяем, что сообщение от пользователя (не от бота)
        if event.message.sender_id == self.client.uid:
            return
        
        # Проверяем, что сообщение текстовое
        if not event.message.text:
            return
        
        # Получаем данные о чате
        chat = await event.get_chat()
        chat_id = chat.id
        chat_title = chat.title
        
        # Получаем ID топика (если есть)
        # В Telethon для ботов ID топика хранится в reply_to.reply_to_top_id
        topic_id = None
        if event.message.reply_to:
            # Для сообщений в топиках (форумах)
            if hasattr(event.message.reply_to, 'reply_to_top_id'):
                topic_id = event.message.reply_to.reply_to_top_id
            # Если это просто ответ на сообщение
            elif hasattr(event.message.reply_to, 'reply_to_msg_id'):
                topic_id = event.message.reply_to.reply_to_msg_id
        
        # Проверяем, есть ли у нас уже эта группа
        group_name = chat_title
        
        # Сохраняем информацию
        self.agent_manager.update_agent(
            group_name=group_name,
            chat_id=chat_id,
            topic_id=topic_id
        )
        
        logger.info(f"📩 [{self.bot_type}] Сообщение из группы {group_name}")
        logger.info(f"   Chat ID: {chat_id}")
        logger.info(f"   Topic ID: {topic_id}")
        
        # Отвечаем
        try:
            response = (
                f"✅ Данные сохранены!\n\n"
                f"📌 Группа: {group_name}\n"
                f"🆔 ID группы: {chat_id}\n"
                f"🌍 Тип бота: {self.bot_type}\n"
            )
            
            if topic_id:
                response += f"📌 ID топика: {topic_id}\n"
                response += f"✅ Топик сохранен!"
            else:
                response += f"\n📝 Создайте топик '{TOPIC_NAME}' и напишите в него,\n"
                response += f"чтобы бот определил ID топика."
            
            await event.reply(response)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ответа: {e}")
    
    async def _handle_chat_action(self, event):
        """
        Обработчик добавления бота в группу
        """
        if event.user_added:
            for user in event.user_added:
                if user.id == self.client.uid:
                    # Бота добавили в группу
                    chat = await event.get_chat()
                    chat_id = chat.id
                    chat_title = chat.title
                    
                    # Сохраняем группу
                    self.agent_manager.update_agent(chat_title, chat_id, None)
                    
                    logger.info(f"➕ [{self.bot_type}] Бот добавлен в группу: {chat_title} (ID: {chat_id})")
                    
                    try:
                        await event.reply(
                            f"🤖 Привет! Я бот для отчетов по скорости рефилов!\n\n"
                            f"📌 Группа: {chat_title}\n"
                            f"🆔 ID группы: {chat_id}\n"
                            f"🌍 Тип бота: {self.bot_type}\n\n"
                            f"📝 Инструкция:\n"
                            f"1. Создайте топик '{TOPIC_NAME}'\n"
                            f"2. Напишите любое сообщение в этот топик\n"
                            f"3. Бот автоматически определит топик и настроится"
                        )
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки приветствия: {e}")
                    
                    break
    
    async def run_daily_report(self):
        """
        Отправка ежедневных отчетов
        """
        if not self.is_ready:
            logger.warning(f"⚠️ Бот {self.bot_type} не готов")
            return
        
        logger.info(f"🚀 Запуск отчета для бота {self.bot_type}")
        
        try:
            # Получаем данные
            data = self.data_processor.process_all_data()
            
            # Выбираем агентов для этого бота
            if self.bot_type == 'INR':
                agents = data.inr_agents
            else:
                agents = data.other_agents
            
            if not agents:
                logger.warning(f"⚠️ Нет агентов для бота {self.bot_type}")
                return
            
            logger.info(f"📊 Найдено {len(agents)} агентов для {self.bot_type}")
            
            # Сбрасываем статистику
            self._reset_stats()
            
            # Обрабатываем каждого агента
            for agent in agents:
                await self._send_agent_report(agent, data)
            
            # Выводим статистику
            self._log_stats(len(agents))
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения отчета: {e}")
    
    async def _send_agent_report(self, agent: AgentData, data: ProcessedData):
        """
        Отправляет отчет для одного агента
        """
        group_name = agent.group_name
        
        # Получаем chat_id и topic_id из кэша
        chat_id = self.agent_manager.get_chat_id(group_name)
        topic_id = self.agent_manager.get_topic_id(group_name)
        
        if not chat_id:
            logger.error(f"❌ Нет chat_id для группы {group_name}")
            self.stats['no_chat'] += 1
            return
        
        # Строим сообщение
        message = self._build_message(agent, data)
        
        try:
            # Отправляем сообщение
            if topic_id:
                # Отправляем в топик
                await self.client.send_message(
                    chat_id,
                    message,
                    reply_to=topic_id  # Для отправки в топик
                )
            else:
                # Отправляем в главный чат
                await self.client.send_message(chat_id, message)
            
            self.stats['processed'] += 1
            logger.info(f"✅ Отправлено сообщение агенту {agent.name} в группу {group_name}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки агенту {agent.name}: {e}")
            self.stats['errors'] += 1
    
    def _build_message(self, agent: AgentData, data: ProcessedData) -> str:
        """
        Строит сообщение для агента
        """
        geo = agent.geo
        share_0_5 = agent.share_0_5 or 0
        share_120 = agent.share_120
        
        # Получаем сообщения для этого ГЕО
        geo_msgs = data.geo_messages.get(geo)
        
        # Определяем диапазон скорости
        speed_range = self._get_speed_range(share_0_5)
        
        # Получаем случайное сообщение
        speed_message = None
        if geo_msgs and speed_range in geo_msgs.messages:
            speed_message = geo_msgs.messages[speed_range].get_random_message()
        
        # Строим сообщение
        lines = [
            f"📢 Ежедневный отчет по скорости рефилов",
            "",
            f"🤖 Агент: {agent.name}",
            f"🌍 ГЕО: {geo}",
            f"📊 Количество рефилов: {agent.refill_count}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"⏱️ Скорость до 5 минут: {share_0_5}%",
        ]
        
        if speed_message:
            lines.append(speed_message)
        else:
            lines.append(f"Ваша скорость: {share_0_5}%")
        
        # Добавляем информацию о 120+ если есть
        if share_120 is not None and share_120 >= 2.5:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ Скорость после 120 минут: {share_120}%",
                f"Ваша скорость после 120 минут: {share_120}%"
            ])
        elif share_120 is not None:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ Скорость после 120 минут: {share_120}%",
                f"ℹ️ Показатель ниже порогового значения (2.5%)"
            ])
        else:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ Скорость после 120 минут: Нет данных",
                "ℹ️ У агента нет выплат, выполненных после 120 минут"
            ])
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📅 Отчет за {datetime.now().strftime('%d.%m.%Y')}"
        ])
        
        return "\n".join(lines)
    
    def _get_speed_range(self, percentage: float) -> str:
        """Определяет диапазон скорости"""
        from config import SPEED_RANGES
        
        if percentage is None:
            return 'Ниже 80'
        
        for range_name, (min_val, max_val) in SPEED_RANGES.items():
            if range_name == 'Ниже 80':
                if percentage < 80:
                    return range_name
            elif min_val <= percentage < max_val:
                return range_name
            elif range_name == '94+' and percentage >= 94:
                return range_name
        
        return 'Ниже 80'
    
    def _reset_stats(self):
        """Сбрасывает статистику"""
        for key in self.stats:
            self.stats[key] = 0
    
    def _log_stats(self, total_agents: int):
        """Логирует статистику"""
        logger.info(f"""
        📊 Статистика отчета ({self.bot_type}):
        ─────────────────────────────
        ✅ Обработано:   {self.stats['processed']}
        ⏭️ Пропущено:    {self.stats['skipped']}
        ❌ Ошибок:       {self.stats['errors']}
        📭 Нет чата:     {self.stats['no_chat']}
        ─────────────────────────────
        📌 Всего агентов: {total_agents}
        """)
    
    async def run(self):
        """Запуск бота (бесконечное прослушивание)"""
        await self.initialize()
        logger.info(f"✅ Бот {self.bot_type} работает")
        await self.client.run_until_disconnected()
    
    async def shutdown(self):
        """Остановка бота"""
        if self.client:
            await self.client.disconnect()
            logger.info(f"⏹️ Бот {self.bot_type} остановлен")


# Функции для запуска
async def run_inr_bot():
    """Запуск INR бота"""
    bot = RefillBot(BOT_INR_TOKEN, 'INR')
    await bot.run()


async def run_other_bot():
    """Запуск OTHER бота"""
    bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
    await bot.run()
