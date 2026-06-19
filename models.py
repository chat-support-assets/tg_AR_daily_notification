from dataclasses import dataclass
from typing import Optional, Dict, List
from enum import Enum
from datetime import datetime


class GeoCode(str, Enum):
    """Коды ГЕО"""
    INR = 'INR'
    NPR = 'NPR'
    TND = 'TND'
    PKR = 'PKR'
    BDT = 'BDT'
    MAD = 'MAD'
    LKR = 'LKR'
    EGP = 'EGP'


@dataclass
class AgentData:
    """Данные агента"""
    name: str              # Полное имя агента
    group_name: str        # Имя группы (без префикса)
    geo: str               # Код ГЕО
    share_0_5: Optional[float]   # Процент до 5 минут
    share_120: Optional[float]   # Процент после 120 минут
    refill_count: int      # Количество рефилов


@dataclass
class GroupInfo:
    """Информация о группе"""
    group_name: str
    chat_id: int
    topic_id: Optional[int] = None
    last_update: str = datetime.now().isoformat()


@dataclass
class SpeedMessage:
    """Сообщение для конкретной скорости"""
    speed_range: str       # '94+', '90-94', и т.д.
    first: str
    second: str
    third: str
    fourth: str
    fifth: str
    
    def get_random_message(self) -> str:
        """Возвращает случайное сообщение из 5 вариантов"""
        import random
        messages = [self.first, self.second, self.third, self.fourth, self.fifth]
        return random.choice([m for m in messages if m])


@dataclass
class GeoMessages:
    """Все сообщения для одного ГЕО"""
    geo: str
    messages: Dict[str, SpeedMessage]  # {speed_range: SpeedMessage}
    
    def get_message_for_speed(self, speed_range: str) -> Optional[SpeedMessage]:
        """Получить сообщение для конкретной скорости"""
        return self.messages.get(speed_range)
    
    def get_random_message_for_speed(self, speed_range: str) -> Optional[str]:
        """Получить случайное сообщение для конкретной скорости"""
        msg = self.messages.get(speed_range)
        if msg:
            return msg.get_random_message()
        return None


@dataclass
class ProcessedData:
    """Обработанные данные"""
    agents_by_geo: Dict[str, List[AgentData]]  # {geo: [AgentData]}
    geo_messages: Dict[str, GeoMessages]       # {geo: GeoMessages}
    inr_agents: List[AgentData]                # Агенты с ГЕО INR
    other_agents: List[AgentData]              # Агенты с другими ГЕО
