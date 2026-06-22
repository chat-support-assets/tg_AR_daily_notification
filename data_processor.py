import re
from typing import List, Dict, Optional, Tuple
from dataclasses import asdict
from models import (
    AgentData, SpeedMessage, GeoMessages, 
    ProcessedData, GeoCode
)
from google_sheets import GoogleSheetsClient
from logger_setup import logger
from config import SPEED_RANGES, THRESHOLD_120_PLUS


class DataProcessor:
    """Обработка данных из Google Sheets"""
    
    def __init__(self):
        self.sheets = GoogleSheetsClient()
    
    def process_all_data(self) -> ProcessedData:
        """
        Главный метод - читает и обрабатывает все данные
        """
        
        # Читаем данные
        agents = self._read_total_score()
        messages = self._read_ar_text()
        
        # Группируем агентов по ГЕО
        agents_by_geo = self._group_agents_by_geo(agents)
        
        # Разделяем INR и OTHER
        inr_agents = agents_by_geo.get('INR', [])
        other_agents = []
        for geo, agent_list in agents_by_geo.items():
            if geo != 'INR':
                other_agents.extend(agent_list)
        
        # Создаем результат
        result = ProcessedData(
            agents_by_geo=agents_by_geo,
            geo_messages=messages,
            inr_agents=inr_agents,
            other_agents=other_agents
        )
        
        # Логируем статистику
        self._log_statistics(result)
        
        return result
    
    def _read_total_score(self) -> List[AgentData]:
        """
        Читает данные с листа Total score
        """
        
        sheet = self.sheets.get_worksheet('Total score')
        records = sheet.get_all_values()
        
        if not records:
            logger.warning("⚠️ Лист 'Total score' пуст!")
            return []
        
        agents = []
        
        # Пропускаем заголовок (строка 0)
        for i, row in enumerate(records[1:], start=1):
            if not row or not row[0]:
                continue
            
            agent_name = row[0].strip()
            
            # Пропускаем пустые строки
            if not agent_name or agent_name == 'Agent':
                continue
            
            # Парсим имя агента
            group_name, geo = self._parse_agent_name(agent_name)
            
            if not group_name or not geo:
                logger.warning(f"⚠️ Не удалось распарсить агента: {agent_name}")
                continue
            
            # Парсим проценты
            share_0_5 = self._parse_percentage(row[2]) if len(row) > 2 else None
            share_120 = self._parse_percentage(row[7]) if len(row) > 7 else None
            
            # Количество рефилов
            refill_count = 0
            if len(row) > 4:
                try:
                    refill_count = int(row[4].strip())
                except (ValueError, TypeError):
                    refill_count = 0
            
            agent = AgentData(
                name=agent_name,
                group_name=group_name,
                geo=geo,
                share_0_5=share_0_5,
                share_120=share_120,
                refill_count=refill_count
            )
            
            agents.append(agent)
        
        return agents
    
    def _read_ar_text(self) -> Dict[str, GeoMessages]:
        """
        Читает данные с листа AR_text
        Возвращает словарь {geo: GeoMessages}
        """
        
        sheet = self.sheets.get_worksheet('AR_text')
        records = sheet.get_all_values()
        
        if not records:
            logger.warning("⚠️ Лист 'AR_text' пуст!")
            return {}
        
        # Первая строка - заголовки с ГЕО (A-G)
        headers = records[0] if records else []
        
        # Строки 2-6 - данные по скоростям
        # Колонки A-G: ГЕО и диапазоны
        # Колонки H-L: сообщения (first, second, third, fourth, fifth)
        
        # Получаем список ГЕО из заголовков (колонки A-G)
        geos = []
        for col in range(8):  # A-H
            if col < len(headers) and headers[col]:
                geo = headers[col].strip().upper()
                if geo and len(geo) == 3:  # Трехбуквенный код
                    geos.append(geo)
        
        # Собираем сообщения для каждого ГЕО
        geo_messages = {}
        
        # Проходим по строкам с данными (строки 2-6)
        for row in records[1:6]:  # Максимум 5 строк
            if not row or len(row) < 12:
                continue
            
            # Определяем диапазон скорости (колонка A)
            speed_range = row[0].strip() if row[0] else ''
            
            if speed_range not in SPEED_RANGES:
                continue
            
            # Для каждого ГЕО берем сообщение из соответствующей колонки
            for idx, geo in enumerate(geos):
                if idx >= len(row):
                    continue
                
                # Сообщения находятся в колонках I-M (индексы 8-12)
                messages = {
                    'first': row[8].strip() if len(row) > 8 else '',
                    'second': row[9].strip() if len(row) > 9 else '',
                    'third': row[10].strip() if len(row) > 10 else '',
                    'fourth': row[11].strip() if len(row) > 11 else '',
                    'fifth': row[12].strip() if len(row) > 12 else ''
                }
                
                # Создаем SpeedMessage
                speed_msg = SpeedMessage(
                    speed_range=speed_range,
                    **messages
                )
                
                # Добавляем в словарь для ГЕО
                if geo not in geo_messages:
                    geo_messages[geo] = GeoMessages(
                        geo=geo,
                        messages={}
                    )
                
                geo_messages[geo].messages[speed_range] = speed_msg
        
        logger.info(f"✅ Загружено {len(geo_messages)} ГЕО с сообщениями")
        
        return geo_messages
    
    def _parse_agent_name(self, agent_name: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Парсит имя агента: Agent_testing_NPR -> ('testing', 'NPR')
        """
        if not agent_name:
            return None, None
        
        parts = agent_name.split('_')
        
        if len(parts) < 2:
            return None, None
        
        # ГЕО - последняя часть
        geo = parts[-1].upper()
        
        # Проверяем, что ГЕО из 3 букв
        if not re.match(r'^[A-Z]{3}$', geo):
            return None, None
        
        # Имя группы - все между первым и последним подчеркиванием
        if len(parts) > 2:
            group_name = '_'.join(parts[1:-1])
        else:
            group_name = parts[1]
        
        return group_name, geo
    
    def _parse_percentage(self, value: str) -> Optional[float]:
        """
        Парсит процент из строки
        """
        if not value:
            return None
        
        value = str(value).strip()
        
        # Если (Пусто) или пусто
        if value == '(Пусто)' or value == '':
            return None
        
        # Убираем %
        if value.endswith('%'):
            value = value[:-1]
        
        # Заменяем запятую на точку
        value = value.replace(',', '.')
        
        try:
            num = float(value)
            # Если число меньше 1, умножаем на 100
            if num <= 1:
                num = num * 100
            return round(num, 1)
        except (ValueError, TypeError):
            return None
    
    def _group_agents_by_geo(self, agents: List[AgentData]) -> Dict[str, List[AgentData]]:
        """
        Группирует агентов по ГЕО
        """
        grouped = {}
        
        for agent in agents:
            geo = agent.geo
            if geo not in grouped:
                grouped[geo] = []
            grouped[geo].append(agent)
        
        return grouped
    
    def _log_statistics(self, data: ProcessedData):
        """
        Логирует статистику по обработанным данным
        """
        logger.info(
            f"📊 Загружено: {len(data.inr_agents) + len(data.other_agents)} агентов, {len(data.geo_messages)} ГЕО, {len(data.inr_agents)} для INR"
        )
