import asyncio
from datetime import datetime
from typing import Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ChatMemberUpdated, ChatPermissions
from aiogram.exceptions import TelegramBadRequest

from config import (
    BOT_INR_TOKEN, BOT_OTHER_TOKEN,
    TOPIC_NAME, THRESHOLD_120_PLUS
)
from agent_manager import agent_manager
from data_processor import DataProcessor
from models import AgentData, ProcessedData
from logger_setup import logger


class RefillBot:
    """Бот на aiogram для отправки отчетов и прослушивания"""
    
    def __init__(self, token: str, bot_type: str):
        self.token = token
        self.bot_type = bot_type
        self.bot: Optional[Bot] = None
        self.dp: Optional[Dispatcher] = None
        self.is_ready = False
        self.data_processor = DataProcessor()
        self.agent_manager = agent_manager
        
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
            logger.info(f"🚀 Инициализация бота {self.bot_type}...")
            
            self.bot = Bot(token=self.token)
            self.dp = Dispatcher()
            
            # Регистрируем обработчики
            @self.dp.message()
            async def handle_message(message: Message):
                await self._handle_message(message)
            
            @self.dp.my_chat_member()
            async def handle_my_chat_member(update: types.ChatMemberUpdated):
                await self._handle_my_chat_member(update)
            
            # Запускаем бота
            await self.dp.start_polling(self.bot)
            
            self.is_ready = True
            logger.info(f"✅ Бот {self.bot_type} инициализирован и запущен")
            
            # Получаем информацию о боте
            me = await self.bot.get_me()
            logger.info(f"   Бот: @{me.username} (ID: {me.id}")
            
            # После запуска проверяем все группы
            await self._scan_existing_groups()
            
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации бота {self.bot_type}: {e}")
            raise
    
    async def _handle_message(self, message: Message):
        """Обработчик сообщений"""
        # Проверяем, что это группа
        if not message.chat or message.chat.type not in ['group', 'supergroup']:
            return
        
        # Проверяем, что сообщение от пользователя (не от бота)
        if message.from_user and message.from_user.is_bot:
            return
        
        # Проверяем, что сообщение текстовое
        if not message.text:
            return
        
        chat = message.chat
        chat_id = chat.id
        chat_title = chat.title or f"Группа {chat_id}"
        
        # Получаем ID топика
        topic_id = message.message_thread_id
        
        # Если сообщение не в топике, проверяем, есть ли топик AR в этой группе
        if not topic_id:
            # Проверяем, есть ли сохраненный topic_id для этой группы
            saved_topic_id = self.agent_manager.get_topic_id(chat_title)
            if saved_topic_id:
                topic_id = saved_topic_id
            else:
                # Пытаемся найти топик AR
                topic_id = await self._find_ar_topic(chat_id)
                if topic_id:
                    logger.info(f"🔍 Найден топик AR в группе {chat_title}: {topic_id}")
                else:
                    # Отправляем инструкцию
                    await message.answer(
                        f"📝 Создайте топик '{TOPIC_NAME}' и напишите в него сообщение,\n"
                        f"чтобы бот определил ID топика для отправки отчетов."
                    )
        
        # Сохраняем информацию
        self.agent_manager.update_agent(chat_title, chat_id, topic_id)
        
        logger.info(f"📩 [{self.bot_type}] Сообщение из группы {chat_title}")
        logger.info(f"   Chat ID: {chat_id}")
        logger.info(f"   Topic ID: {topic_id}")
        logger.info(f"   Текст: {message.text[:50]}...")
        
        # Отвечаем
        try:
            response = (
                f"✅ Данные сохранены!\n\n"
                f"📌 Группа: {chat_title}\n"
                f"🆔 ID группы: {chat_id}\n"
                f"🌍 Тип бота: {self.bot_type}\n"
            )
            
            if topic_id:
                response += f"📌 ID топика: {topic_id}\n✅ Топик сохранен!"
            else:
                response += f"\n📝 Создайте топик '{TOPIC_NAME}' и напишите в него,\nчтобы бот определил ID топика."
            
            await message.answer(response)
            
        except Exception as e:
            logger.error(f"❌ Ошибка отправки ответа: {e}")
    
    async def _handle_my_chat_member(self, update: types.ChatMemberUpdated):
        """Обработчик добавления бота в группу"""
        chat = update.chat
        new_status = update.new_chat_member.status
        
        # Проверяем, что бота добавили в группу
        if new_status in ['member', 'administrator']:
            chat_id = chat.id
            chat_title = chat.title or f"Группа {chat_id}"
            
            # Сохраняем группу
            self.agent_manager.update_agent(chat_title, chat_id, None)
            
            logger.info(f"➕ [{self.bot_type}] Бот добавлен в группу: {chat_title} (ID: {chat_id})")
            
            # Пытаемся найти топик AR
            topic_id = await self._find_ar_topic(chat_id)
            if topic_id:
                self.agent_manager.update_topic_id(chat_title, topic_id)
                logger.info(f"✅ Найден топик AR в группе {chat_title}: {topic_id}")
            else:
                # Отправляем приветствие с инструкцией
                try:
                    await self.bot.send_message(
                        chat_id,
                        f"🤖 Привет! Я бот для отчетов по скорости рефилов!\n\n"
                        f"📌 Группа: {chat_title}\n"
                        f"🆔 ID группы: {chat_id}\n"
                        f"🌍 Тип бота: {self.bot_type}\n\n"
                        f"📝 Инструкция:\n"
                        f"1. Создайте топик '{TOPIC_NAME}'\n"
                        f"2. Напишите любое сообщение в этот топик\n"
                        f"3. Бот автоматически определит топик"
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка отправки приветствия: {e}")
    
    async def _find_ar_topic(self, chat_id: int) -> Optional[int]:
        """Находит топик AR в группе"""
        try:
            # Пытаемся найти топик через отправку сообщения
            # В aiogram нет прямого метода для получения списка топиков
            # Поэтому используем обходной путь: проверяем через отправку
            
            # Пытаемся отправить сообщение в топик с ID 1 (если существует)
            # Это не идеально, но работает для проверки
            try:
                # Пробуем отправить в топик с ID 1
                await self.bot.send_message(
                    chat_id=chat_id,
                    text="🔍 Проверка топика...",
                    message_thread_id=1
                )
                # Если успешно - значит топик с ID 1 существует
                # Но нам нужен именно AR, поэтому проверяем дальше
            except:
                pass
            
            # В aiogram нет API для получения списка топиков
            # Поэтому просим пользователя написать в топик
            
            # Отправляем сообщение с просьбой
            await self.bot.send_message(
                chat_id,
                f"🔍 Для настройки топика '{TOPIC_NAME}':\n"
                f"1. Создайте топик '{TOPIC_NAME}'\n"
                f"2. Напишите любое сообщение в этот топик\n"
                f"3. Бот автоматически определит ID топика"
            )
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска топика AR: {e}")
            return None
    
    async def _scan_existing_groups(self):
        """Сканирует существующие группы для поиска топиков AR"""
        logger.info(f"🔍 Сканирование существующих групп для бота {self.bot_type}...")
        
        try:
            agents = self.agent_manager.get_all_agents()
            
            if not agents:
                logger.info("ℹ️ Нет сохраненных групп для сканирования")
                return
            
            found = 0
            for group_name, data in agents.items():
                chat_id = data.get('chat_id')
                if not chat_id:
                    continue
                
                # Проверяем, есть ли уже topic_id
                if data.get('topic_id'):
                    logger.info(f"✅ Группа {group_name} уже имеет топик: {data['topic_id']}")
                    found += 1
                    continue
                
                # Пытаемся найти топик AR
                topic_id = await self._find_ar_topic(chat_id)
                if topic_id:
                    self.agent_manager.update_topic_id(group_name, topic_id)
                    logger.info(f"✅ Найден топик AR в группе {group_name}: {topic_id}")
                    found += 1
            
            logger.info(f"✅ Сканирование завершено. Найдено топиков: {found}/{len(agents)}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка сканирования групп: {e}")
    
    async def run_daily_report(self):
        """Отправка ежедневных отчетов"""
        if not self.is_ready:
            logger.warning(f"⚠️ Бот {self.bot_type} не готов")
            return
        
        logger.info(f"🚀 Запуск отчета для бота {self.bot_type}")
        
        try:
            data = self.data_processor.process_all_data()
            
            if self.bot_type == 'INR':
                agents = data.inr_agents
            else:
                agents = data.other_agents
            
            if not agents:
                logger.warning(f"⚠️ Нет агентов для бота {self.bot_type}")
                return
            
            logger.info(f"📊 Найдено {len(agents)} агентов для {self.bot_type}")
            
            self._reset_stats()
            
            for agent in agents:
                await self._send_agent_report(agent, data)
            
            self._log_stats(len(agents))
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения отчета: {e}")
    
    async def _send_agent_report(self, agent: AgentData, data: ProcessedData):
        """Отправляет отчет для одного агента"""
        group_name = agent.group_name
        
        chat_id = self.agent_manager.get_chat_id(group_name)
        topic_id = self.agent_manager.get_topic_id(group_name)
        
        if not chat_id:
            logger.error(f"❌ Нет chat_id для группы {group_name}")
            self.stats['no_chat'] += 1
            return
        
        message = self._build_message(agent, data)
        
        try:
            if topic_id:
                await self.bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    message_thread_id=topic_id
                )
            else:
                await self.bot.send_message(chat_id=chat_id, text=message)
            
            self.stats['processed'] += 1
            logger.info(f"✅ Отправлено агенту {agent.name} в группу {group_name}")
            
        except TelegramBadRequest as e:
            logger.error(f"❌ Ошибка отправки агенту {agent.name}: {e}")
            self.stats['errors'] += 1
        except Exception as e:
            logger.error(f"❌ Ошибка отправки агенту {agent.name}: {e}")
            self.stats['errors'] += 1
    
    def _build_message(self, agent: AgentData, data: ProcessedData) -> str:
        """Строит сообщение для агента"""
        geo = agent.geo
        share_0_5 = agent.share_0_5 or 0
        share_120 = agent.share_120
        
        geo_msgs = data.geo_messages.get(geo)
        speed_range = self._get_speed_range(share_0_5)
        
        speed_message = None
        if geo_msgs and speed_range in geo_msgs.messages:
            speed_message = geo_msgs.messages[speed_range].get_random_message()
        
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
        
        if share_120 is not None and share_120 >= THRESHOLD_120_PLUS:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ Скорость после 120 минут: {share_120}%"
            ])
        elif share_120 is not None:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ Скорость после 120 минут: {share_120}%",
                f"ℹ️ Показатель ниже порогового значения ({THRESHOLD_120_PLUS}%)"
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
        for key in self.stats:
            self.stats[key] = 0
    
    def _log_stats(self, total_agents: int):
        logger.info(f"""
        📊 Статистика отчета ({self.bot_type}):
        ─────────────────────────────
        ✅ Обработано:   {self.stats['processed']}
        ❌ Ошибок:       {self.stats['errors']}
        📭 Нет чата:     {self.stats['no_chat']}
        📌 Нет топика:   {self.stats['no_topic']}
        ─────────────────────────────
        📌 Всего агентов: {total_agents}
        """)
    
    async def run(self):
        await self.initialize()
        logger.info(f"✅ Бот {self.bot_type} работает")
    
    async def shutdown(self):
        if self.bot:
            await self.bot.session.close()
            logger.info(f"⏹️ Бот {self.bot_type} остановлен")


async def run_inr_bot():
    bot = RefillBot(BOT_INR_TOKEN, 'INR')
    await bot.run()


async def run_other_bot():
    bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
    await bot.run()
