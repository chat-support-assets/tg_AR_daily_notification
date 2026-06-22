import asyncio
from datetime import datetime
from typing import Optional
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message
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
        self.running = True
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
            
            self.is_ready = True
            logger.info(f"✅ Бот {self.bot_type} инициализирован")
            
            # Получаем информацию о боте
            me = await self.bot.get_me()
            logger.info(f"   Бот: @{me.username} (ID: {me.id})")
            
            return self.dp
            
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
        
        # Если сообщение не в топике, проверяем сохраненный topic_id
        if not topic_id:
            saved_topic_id = self.agent_manager.get_topic_id(chat_title)
            if saved_topic_id:
                topic_id = saved_topic_id
        
        # Сохраняем информацию (используем полное название группы)
        self.agent_manager.update_agent(chat_title, chat_id, topic_id)
        
        logger.info(f"📩 [{self.bot_type}] Сообщение из группы {chat_title}")
        logger.info(f"   Chat ID: {chat_id}")
        logger.info(f"   Topic ID: {topic_id}")
        
        # Отвечаем только если это первое сообщение в топике
        if topic_id and not self.agent_manager.get_topic_id(chat_title):
            try:
                await message.answer(
                    f"✅ Топик '{TOPIC_NAME}' найден!\n"
                    f"📌 ID топика: {topic_id}\n"
                    f"📊 Отчеты будут приходить сюда."
                )
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
            
            # Отправляем приветствие
            try:
                await self.bot.send_message(
                    chat_id,
                    f"🤖 Привет! Я бот для отчетов по скорости рефилов!\n\n"
                    f"📌 Группа: {chat_title}\n"
                    f"🆔 ID группы: {chat_id}\n"
                    f"🌍 Тип бота: {self.bot_type}\n\n"
                    f"📝 Для настройки:\n"
                    f"1. Создайте топик '{TOPIC_NAME}'\n"
                    f"2. Напишите любое сообщение в этот топик\n"
                    f"3. Бот автоматически определит топик для отчетов"
                )
            except Exception as e:
                logger.error(f"❌ Ошибка отправки приветствия: {e}")
    
    async def run_daily_report(self):
        """Отправка ежедневных отчетов"""
        if not self.is_ready:
            logger.warning(f"⚠️ Бот {self.bot_type} не готов")
            return
        
        logger.info(f"🚀 Запуск отчета для бота {self.bot_type}")
        
        try:
            # Получаем данные из таблицы
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
            
            self._reset_stats()
            
            # Отправляем отчеты каждому агенту
            for agent in agents:
                await self._send_agent_report(agent, data)
                # Небольшая задержка между отправками
                await asyncio.sleep(1)
            
            self._log_stats(len(agents))
            
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения отчета: {e}")
    
    async def _send_agent_report(self, agent: AgentData, data: ProcessedData):
        """Отправляет отчет для одного агента"""
        # Используем ПОЛНОЕ имя агента как ключ для поиска в кэше
        agent_full_name = agent.name
        
        # Пробуем найти по полному имени
        chat_id = self.agent_manager.get_chat_id(agent_full_name)
        topic_id = self.agent_manager.get_topic_id(agent_full_name)
        
        # Если не нашли по полному имени, пробуем по group_name
        if not chat_id:
            group_name = agent.group_name
            chat_id = self.agent_manager.get_chat_id(group_name)
            topic_id = self.agent_manager.get_topic_id(group_name)
            
            if chat_id:
                logger.info(f"🔍 Найден chat_id для {agent_full_name} по group_name: {group_name}")
                # Обновляем кэш, используя полное имя
                self.agent_manager.update_agent(agent_full_name, chat_id, topic_id)
        
        if not chat_id:
            logger.warning(f"⚠️ Нет chat_id для агента {agent_full_name}")
            self.stats['no_chat'] += 1
            return
        
        if not topic_id:
            logger.warning(f"⚠️ Нет topic_id для агента {agent_full_name}")
            self.stats['no_topic'] += 1
            return
        
        # Строим сообщение
        message = self._build_message(agent, data)
        
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=message,
                message_thread_id=topic_id
            )
            self.stats['processed'] += 1
            logger.info(f"✅ Отправлено агенту {agent.name} (ГЕО: {agent.geo})")
            
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
            f"📢 Daily Refill Speed ​​Report",
            "",
            f"🤖 Agent: {agent.name}",
            f"🌍 GEO: {geo}",
            f"📊 Refill amount: {agent.refill_count}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"⏱️ Speed ​​up to 5 minutes: {share_0_5}%",
        ]
        
        if speed_message:
            lines.append(speed_message)
        else:
            lines.append(f"Your speed: {share_0_5}%")
        
        if share_120 is not None and share_120 >= THRESHOLD_120_PLUS:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ Speed ​​120-min+: {share_120}%",
                "Currently within limit. Always keep it below 2.5%."
            ])
        
        lines.extend([
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📅 Report for {datetime.now().strftime('%d.%m.%Y')}"
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
        """Запуск бота (бесконечное прослушивание)"""
        await self.initialize()
        logger.info(f"✅ Бот {self.bot_type} запущен и слушает сообщения")
        
        # Запускаем polling
        await self.dp.start_polling(self.bot)
    
    async def shutdown(self):
        """Остановка бота"""
        if self.bot:
            await self.bot.session.close()
            logger.info(f"⏹️ Бот {self.bot_type} остановлен")


async def run_inr_bot():
    """Запуск INR бота с обработкой ошибок"""
    bot = RefillBot(BOT_INR_TOKEN, 'INR')
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка INR бота: {e}")
        await bot.shutdown()


async def run_other_bot():
    """Запуск OTHER бота с обработкой ошибок"""
    bot = RefillBot(BOT_OTHER_TOKEN, 'OTHER')
    try:
        await bot.run()
    except Exception as e:
        logger.error(f"❌ Критическая ошибка OTHER бота: {e}")
        await bot.shutdown()
