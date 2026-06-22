import json
import os
from typing import Dict, Optional
from logger_setup import logger
from config import AGENTS_CACHE_FILE


class AgentManager:
    """Управление данными агентов: кэширование ID групп и топиков"""
    
    def __init__(self):
        self.cache_file = AGENTS_CACHE_FILE
        self.agents_data = self._load_cache()
    
    def _load_cache(self) -> Dict:
        """Загружает данные из кэш-файла"""
        if os.path.exists(self.cache_file):
            try:
                if os.path.getsize(self.cache_file) == 0:
                    logger.warning(f"⚠️ Файл {self.cache_file} пустой. Создаем новый.")
                    return {}
                
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        logger.warning(f"⚠️ Файл {self.cache_file} содержит неверный формат.")
                        return {}
                    
                    logger.info(f"✅ Загружено {len(data)} агентов из кэша")
                    return data
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON: {e}")
                return {}
                
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки кэша: {e}")
                return {}
        else:
            logger.info("ℹ️ Кэш-файл не найден, создаем новый")
            return {}
    
    def save_cache(self):
        """Сохраняет данные в кэш-файл"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.agents_data, f, ensure_ascii=False, indent=2)
            logger.info("✅ Кэш сохранен")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения кэша: {e}")
    
    def update_agent(self, group_name: str, chat_id: int, topic_id: Optional[int] = None):
        """Обновляет или создает данные агента"""
        if group_name not in self.agents_data:
            self.agents_data[group_name] = {
                'chat_id': chat_id,
                'topic_id': topic_id,
                'last_update': self._get_timestamp()
            }
            logger.info(f"➕ Добавлен новый агент: {group_name}")
        else:
            self.agents_data[group_name]['chat_id'] = chat_id
            if topic_id is not None:
                self.agents_data[group_name]['topic_id'] = topic_id
            self.agents_data[group_name]['last_update'] = self._get_timestamp()
            logger.info(f"🔄 Обновлен агент: {group_name}")
        
        self.save_cache()
    
    def get_chat_id(self, group_name: str) -> Optional[int]:
        """Получает ID чата по имени группы"""
        if group_name in self.agents_data:
            return self.agents_data[group_name].get('chat_id')
        
        for name, data in self.agents_data.items():
            if name.lower() == group_name.lower():
                return data.get('chat_id')
        
        return None
    
    def get_topic_id(self, group_name: str) -> Optional[int]:
        """Получает ID топика по имени группы"""
        if group_name in self.agents_data:
            return self.agents_data[group_name].get('topic_id')
        
        for name, data in self.agents_data.items():
            if name.lower() == group_name.lower():
                return data.get('topic_id')
        
        return None
    
    def get_all_agents(self):
        """Возвращает всех агентов"""
        return self.agents_data
    
    @staticmethod
    def _get_timestamp():
        from datetime import datetime
        return datetime.now().isoformat()


agent_manager = AgentManager()
