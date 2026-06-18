import re
from typing import Tuple, Optional
from logger_setup import logger
from config import SPEED_RANGES, THRESHOLD_120_PLUS
import random


class AgentParser:
    @staticmethod
    def parse_agent_name(agent_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Парсит имя агента и возвращает группу и ГЕО
        """
        if not agent_name:
            return None, None
        
        # Разбиваем по нижнему подчеркиванию
        parts = agent_name.split('_')
        
        if len(parts) < 3:
            logger.warning(f"⚠️ Неверный формат имени агента: {agent_name}")
            return None, None
        
        # ГЕО - всегда последняя часть (3 буквы)
        geo = parts[-1].upper()
        
        # Проверяем, что ГЕО состоит из 3 букв
        if not re.match(r'^[A-Z]{3}$', geo):
            logger.warning(f"⚠️ Неверный формат ГЕО: {geo} в агенте {agent_name}")
            return None, None
        
        # Группа - все между первым и последним подчеркиванием
        # Пропускаем первый элемент (Agent или CORP и т.д.)
        group_parts = parts[1:-1]
        group_name = '_'.join(group_parts) if group_parts else parts[1]
        
        return group_name, geo

    @staticmethod
    def get_speed_range(percentage: float) -> str:
        """
        Определяет диапазон скорости по проценту
        """
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


class MessageBuilder:
    """Построение сообщений для отправки"""
    
    def __init__(self, messages_dict):
        """
        :param messages_dict: словарь с сообщениями из AR_text
        """
        self.messages = messages_dict
        # Счетчик для циклического перебора типов сообщений
        self.message_types = ['first', 'second', 'third', 'fourth', 'fifth']
        self.type_index = 0
        
        # Кэш для хранения последнего использованного типа для каждого агента
        self.agent_last_type = {}
    
    def build_message(self, agent_name: str, share_0_5: float, share_120: float, refill_count: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Строит полное сообщение для агента
        Возвращает (message, group_name, geo)
        """
        # Парсим имя
        group_name, geo = AgentParser.parse_agent_name(agent_name)
        
        if not group_name or not geo:
            return None, None, None
        
        # Определяем диапазоны
        range_0_5 = AgentParser.get_speed_range(share_0_5)
        
        # Получаем текст для 0-5 минут (всегда отправляем)
        text_0_5 = self._get_message_for_agent(group_name, range_0_5)
        
        # Формируем сообщение
        message_lines = [
            f"📢 **Ежедневный отчет по скорости рефилов**",
            "",
            f"🤖 **Агент:** {agent_name}",
            f"🌍 **ГЕО:** {geo}",
            f"📊 **Количество рефилов:** {refill_count}",
            "",
            "━━━━━━━━━━━━━━━━━━━━━",
            f"⏱️ **Скорость до 5 минут: {share_0_5}%**",
            text_0_5 if text_0_5 else f"Ваша скорость: {share_0_5}%",
            "",
        ]
        
        # Добавляем информацию о 120+ минутах, только если процент >= порога
        if share_120 >= THRESHOLD_120_PLUS:
            range_120 = AgentParser.get_speed_range(share_120)
            text_120 = self._get_message_for_agent(group_name, range_120, force_next=False)
            
            message_lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ **Скорость после 120 минут: {share_120}%**",
                text_120 if text_120 else f"Ваша скорость: {share_120}%",
                "",
            ])
        else:
            message_lines.extend([
                "━━━━━━━━━━━━━━━━━━━━━",
                f"⏱️ **Скорость после 120 минут: {share_120}%**",
                "ℹ️ Показатель ниже порогового значения (2.5%)",
                "",
            ])
        
        message_lines.extend([
            "━━━━━━━━━━━━━━━━━━━━━",
            f"📅 Отчет за {self._get_current_date()}"
        ])
        
        full_message = "\n".join(message_lines)
        
        return full_message, group_name, geo
    
    def _get_message_for_agent(self, agent_name: str, speed_range: str, force_next: bool = True) -> str:
        """
        Получает сообщение для агента, циклически перебирая типы
        """
        if speed_range not in self.messages:
            return ""
        
        # Получаем список доступных сообщений для этого диапазона
        available_messages = self.messages[speed_range]
        
        # Проверяем, есть ли у агента сохраненный индекс
        if agent_name not in self.agent_last_type:
            # Если нет - начинаем с первого
            self.agent_last_type[agent_name] = 0
        elif force_next:
            # Переходим к следующему типу
            self.agent_last_type[agent_name] = (self.agent_last_type[agent_name] + 1) % len(self.message_types)
        
        # Получаем индекс типа
        type_index = self.agent_last_type[agent_name]
        message_type = self.message_types[type_index]
        
        # Возвращаем сообщение
        return available_messages.get(message_type, "")
    
    def reset_agent_counter(self, agent_name: str):
        """
        Сбрасывает счетчик для агента (можно использовать при ошибках)
        """
        if agent_name in self.agent_last_type:
            del self.agent_last_type[agent_name]
    
    @staticmethod
    def _get_current_date() -> str:
        """Возвращает текущую дату"""
        from datetime import datetime
        return datetime.now().strftime('%d.%m.%Y')


def should_process_agent(geo: str, bot_type: str) -> bool:
    """
    Определяет, должен ли бот обрабатывать этого агента
    """
    if bot_type == 'INR':
        return geo == 'INR'
    else:  # OTHER
        return geo != 'INR'
