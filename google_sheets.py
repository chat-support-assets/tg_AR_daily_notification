import gspread
from google.oauth2.service_account import Credentials
from config import SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, SHEET_TOTAL_SCORE, SHEET_AR_TEXT
from logger_setup import logger


class GoogleSheetsClient:
    def __init__(self):
        """Инициализация подключения к Google Sheets"""
        try:
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, 
                scopes=scopes
            )
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
            logger.info("✅ Успешное подключение к Google Sheets")
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
            raise

    def get_total_score_data(self):
        """
        Получение данных с листа Total score
        Возвращает список словарей с данными агентов
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_TOTAL_SCORE)
            records = sheet.get_all_values()
            
            agents_data = []
            
            for row in records:
                # Пропускаем пустые строки и заголовки
                if not row or not row[0] or row[0].startswith('Agent'):
                    continue
                
                agent_name = row[0].strip()
                
                # Проверяем, что это строка с агентом
                if not agent_name or agent_name.startswith('Agent'):
                    continue
                
                # Парсим проценты
                share_0_5 = self._parse_percentage(row[2]) if len(row) > 2 else None
                share_120 = self._parse_percentage(row[7]) if len(row) > 7 else None
                
                # Проверяем, что оба показателя есть
                if share_0_5 is not None and share_120 is not None:
                    agents_data.append({
                        'agent_name': agent_name,
                        'share_0_5': share_0_5,
                        'share_120': share_120,
                        'refill_count': row[4] if len(row) > 4 else '0'
                    })
            
            logger.info(f"✅ Загружено {len(agents_data)} агентов с листа Total score")
            return agents_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка чтения листа Total score: {e}")
            return []

    def get_ar_messages(self):
        """
        Получение всех текстов сообщений с листа AR_text
        Возвращает словарь: {speed_range: {'first': text, 'second': text, ...}}
        """
        try:
            sheet = self.spreadsheet.worksheet(SHEET_AR_TEXT)
            records = sheet.get_all_values()
            
            # Словарь для всех сообщений по диапазонам
            all_messages = {}
            
            # Строки 2-6 (индексы 1-5) содержат сообщения
            # Столбцы: A=диапазон, H=first, I=second, J=third, K=fourth, L=fifth
            for row in records[1:]:  # Пропускаем заголовок
                if not row or len(row) < 12:
                    continue
                
                speed_range = row[0].strip()
                
                # Проверяем, что это диапазон скорости
                if speed_range not in ['94+', '90-94', '85-90', '80-84.9', 'Ниже 80']:
                    continue
                
                # Загружаем все 5 вариантов сообщений
                all_messages[speed_range] = {
                    'first': row[7].strip() if len(row) > 7 else '',
                    'second': row[8].strip() if len(row) > 8 else '',
                    'third': row[9].strip() if len(row) > 9 else '',
                    'fourth': row[10].strip() if len(row) > 10 else '',
                    'fifth': row[11].strip() if len(row) > 11 else ''
                }
            
            logger.info(f"✅ Загружено {len(all_messages)} шаблонов сообщений")
            return all_messages
            
        except Exception as e:
            logger.error(f"❌ Ошибка чтения листа AR_text: {e}")
            return {}

    @staticmethod
    def _parse_percentage(value):
        """
        Парсит процент из строки или числа
        """
        if not value:
            return None
        
        if isinstance(value, str):
            value = value.strip()
            if value.endswith('%'):
                value = value[:-1]
            value = value.replace(',', '.')
        
        try:
            num = float(value)
            if num <= 1:
                num = num * 100
            return round(num, 1)
        except (ValueError, TypeError):
            return None
