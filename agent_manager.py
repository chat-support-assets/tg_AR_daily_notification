import json
import os
from typing import Dict, Optional
from logger_setup import logger
from config import AGENTS_CACHE_FILE
from datetime import datetime


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
        logger.info(f"   Chat ID: {chat_id}, Topic ID: {topic_id}")
    
    def update_topic_id(self, group_name: str, topic_id: Optional[int]):
        """Обновляет только ID топика"""
        if group_name in self.agents_data:
            self.agents_data[group_name]['topic_id'] = topic_id
            self.agents_data[group_name]['last_update'] = self._get_timestamp()
            self.save_cache()
            logger.info(f"✅ Обновлен ID топика для {group_name}: {topic_id}")
        else:
            logger.warning(f"⚠️ Агент {group_name} не найден в кэше")
    
    def get_agent(self, group_name: str) -> Optional[Dict]:
        """Получает данные агента по имени группы"""
        # Точное совпадение
        if group_name in self.agents_data:
            return self.agents_data[group_name]
        
        # Поиск без учета регистра
        for name, data in self.agents_data.items():
            if name.lower() == group_name.lower():
                return data
        
        return None
    
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
    
    def remove_agent(self, group_name: str) -> bool:
        """Удаляет агента из кэша"""
        if group_name in self.agents_data:
            del self.agents_data[group_name]
            self.save_cache()
            logger.info(f"🗑️ Агент {group_name} удален из кэша")
            return True
        
        # Поиск без учета регистра
        for name in list(self.agents_data.keys()):
            if name.lower() == group_name.lower():
                del self.agents_data[name]
                self.save_cache()
                logger.info(f"🗑️ Агент {name} удален из кэша")
                return True
        
        return False
    
    def print_agents(self):
        """Выводит всех агентов в читаемом виде"""
        if not self.agents_data:
            print("📭 Нет сохраненных агентов")
            return
        
        print("\n📋 Сохраненные агенты:")
        print("=" * 60)
        for name, data in self.agents_data.items():
            print(f"\n📌 {name}")
            print(f"   Chat ID: {data['chat_id']}")
            print(f"   Topic ID: {data.get('topic_id', 'Не задан')}")
            print(f"   Обновлен: {data.get('last_update', 'Неизвестно')}")
        print("=" * 60)
    
    @staticmethod
    def _get_timestamp():
        from datetime import datetime
        return datetime.now().isoformat()


# Создаем глобальный менеджер агентов
agent_manager = AgentManager()
