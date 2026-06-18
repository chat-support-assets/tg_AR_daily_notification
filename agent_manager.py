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
        """
        Загружает данные из кэш-файла
        """
        if os.path.exists(self.cache_file):
            try:
                # Проверяем, не пустой ли файл
                if os.path.getsize(self.cache_file) == 0:
                    logger.warning(f"⚠️ Файл {self.cache_file} пустой. Создаем новый.")
                    return {}
                
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if not isinstance(data, dict):
                        logger.warning(f"⚠️ Файл {self.cache_file} содержит неверный формат. Создаем новый.")
                        return {}
                    
                    logger.info(f"✅ Загружено {len(data)} агентов из кэша")
                    return data
                    
            except json.JSONDecodeError as e:
                logger.error(f"❌ Ошибка парсинга JSON в {self.cache_file}: {e}")
                # Создаем резервную копию поврежденного файла
                backup_file = f"{self.cache_file}.backup"
                try:
                    os.rename(self.cache_file, backup_file)
                    logger.info(f"📦 Поврежденный файл переименован в {backup_file}")
                except:
                    pass
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
    
    def get_agent(self, group_name: str) -> Optional[Dict]:
        """Получает данные агента по имени группы"""
        return self.agents_data.get(group_name)
    
    def update_agent(self, group_name: str, chat_id: int, topic_id: Optional[int] = None):
        """Обновляет или создает данные агента"""
        if group_name not in self.agents_data:
            self.agents_data[group_name] = {
                'chat_id': chat_id,
                'topic_id': topic_id,
                'last_update': self._get_timestamp()
            }
        else:
            self.agents_data[group_name]['chat_id'] = chat_id
            if topic_id is not None:
                self.agents_data[group_name]['topic_id'] = topic_id
            self.agents_data[group_name]['last_update'] = self._get_timestamp()
        
        self.save_cache()
        logger.info(f"✅ Обновлены данные агента {group_name}: chat_id={chat_id}, topic_id={topic_id}")
    
    def update_topic_id(self, group_name: str, topic_id: int):
        """Обновляет только ID топика"""
        if group_name in self.agents_data:
            self.agents_data[group_name]['topic_id'] = topic_id
            self.agents_data[group_name]['last_update'] = self._get_timestamp()
            self.save_cache()
            logger.info(f"✅ Обновлен ID топика для {group_name}: {topic_id}")
        else:
            logger.warning(f"⚠️ Агент {group_name} не найден в кэше")
    
    def get_chat_id(self, group_name: str) -> Optional[int]:
        """Получает ID чата по имени группы"""
        agent = self.get_agent(group_name)
        return agent.get('chat_id') if agent else None
    
    def get_topic_id(self, group_name: str) -> Optional[int]:
        """Получает ID топика по имени группы"""
        agent = self.get_agent(group_name)
        return agent.get('topic_id') if agent else None
    
    def get_all_agents(self):
        """Возвращает всех агентов"""
        return self.agents_data
    
    def add_agent_manually(self, group_name: str, chat_id: int, topic_id: Optional[int] = None):
        """Добавляет агента вручную (для настройки)"""
        self.update_agent(group_name, chat_id, topic_id)
        logger.info(f"✅ Агент {group_name} добавлен вручную")
    
    def remove_agent(self, group_name: str) -> bool:
        """Удаляет агента из кэша"""
        if group_name in self.agents_data:
            del self.agents_data[group_name]
            self.save_cache()
            logger.info(f"🗑️ Агент {group_name} удален из кэша")
            return True
        return False
    
    @staticmethod
    def _get_timestamp():
        """Возвращает текущую временную метку"""
        from datetime import datetime
        return datetime.now().isoformat()


# Создаем глобальный менеджер агентов
agent_manager = AgentManager()
