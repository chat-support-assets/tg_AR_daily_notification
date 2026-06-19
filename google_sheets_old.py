import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from config import SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, SHEET_TOTAL_SCORE, SHEET_AR_TEXT
from logger_setup import logger
import os
import json


class GoogleSheetsClient:
    def __init__(self):
        """Инициализация подключения к Google Sheets с impersonate"""
        try:
            # Проверяем наличие файла с ключом
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                raise FileNotFoundError(f"❌ Файл {SERVICE_ACCOUNT_FILE} не найден!")
            
            # Проверяем, что файл не пустой
            if os.path.getsize(SERVICE_ACCOUNT_FILE) == 0:
                raise ValueError(f"❌ Файл {SERVICE_ACCOUNT_FILE} пустой!")
            
            # Читаем email для impersonate из переменной окружения
            impersonate_email = os.getenv('IMPERSONATE_EMAIL')
            
            if not impersonate_email:
                with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                    data = json.load(f)
                    impersonate_email = data.get('client_email')
                    logger.info(f"📧 Используем email из service_account.json: {impersonate_email}")
            else:
                logger.info(f"📧 Используем email из .env: {impersonate_email}")
            
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            
            # Создаем учетные данные с impersonate
            creds = Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, 
                scopes=scopes
            )
            
            if impersonate_email:
                creds = creds.with_subject(impersonate_email)
                logger.info(f"✅ Используем impersonate: {impersonate_email}")
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
            self._check_sheets_exist()
            
            logger.info("✅ Успешное подключение к Google Sheets с impersonate")
            
        except Exception as e:
            logger.error(f"❌ Ошибка подключения: {e}")
            raise

    def _check_sheets_exist(self):
        """Проверяет существование нужных листов"""
        try:
            sheets = self.spreadsheet.worksheets()
            sheet_names = [sheet.title for sheet in sheets]
            
            if SHEET_TOTAL_SCORE not in sheet_names:
                logger.warning(f"⚠️ Лист '{SHEET_TOTAL_SCORE}' не найден!")
            else:
                logger.info(f"✅ Лист '{SHEET_TOTAL_SCORE}' найден")
            
            if SHEET_AR_TEXT not in sheet_names:
                logger.warning(f"⚠️ Лист '{SHEET_AR_TEXT}' не найден!")
            else:
                logger.info(f"✅ Лист '{SHEET_AR_TEXT}' найден")
                
        except Exception as e:
            logger.error(f"❌ Ошибка проверки листов: {e}")

    def get_total_score_data(self):
        """Получение данных с листа Total score"""
        try:
            sheet = self.spreadsheet.worksheet(SHEET_TOTAL_SCORE)
            records = sheet.get_all_values()
            
            if not records:
                logger.warning(f"⚠️ Лист '{SHEET_TOTAL_SCORE}' пуст!")
                return []
            
            agents_data = []
            
            # Пропускаем первую строку с заголовками
            for i, row in enumerate(records):
                if i == 0:  # Пропускаем заголовки
                    continue
                
                if not row or not row[0]:
                    continue
                
                agent_name = row[0].strip()
                
                # Проверяем, что это не пустая строка
                if not agent_name or agent_name == 'Agent':
                    continue
                
                # Парсим проценты
                share_0_5 = self._parse_percentage(row[2]) if len(row) > 2 else None
                
                # Для 120+ - если значение "(Пусто)" или пусто, то None
                share_120 = None
                if len(row) > 7:
                    value = row[7].strip()
                    if value and value != '(Пусто)' and value != '':
                        share_120 = self._parse_percentage(value)
                
                # Добавляем агента даже если share_0_5 None (для отладки)
                agents_data.append({
                    'agent_name': agent_name,
                    'share_0_5': share_0_5,
                    'share_120': share_120,  # Может быть None если нет данных
                    'refill_count': row[4] if len(row) > 4 else '0'
                })
            
            logger.info(f"✅ Загружено {len(agents_data)} агентов с листа Total score")
            
            # Логируем первых 5 агентов для отладки
            if agents_data:
                logger.info("📋 Первые 5 агентов:")
                for agent in agents_data[:5]:
                    share_0_5_str = f"{agent['share_0_5']}%" if agent['share_0_5'] is not None else "Нет данных"
                    share_120_str = f"{agent['share_120']}%" if agent['share_120'] is not None else "Нет данных"
                    logger.info(f"  - {agent['agent_name']}: 0-5={share_0_5_str}, 120+={share_120_str}")
            
            return agents_data
            
        except Exception as e:
            logger.error(f"❌ Ошибка чтения листа Total score: {e}")
            return []

    def get_ar_messages(self):
        """Получение всех текстов сообщений с листа AR_text"""
        try:
            sheet = self.spreadsheet.worksheet(SHEET_AR_TEXT)
            records = sheet.get_all_values()
            
            if not records:
                logger.warning(f"⚠️ Лист '{SHEET_AR_TEXT}' пуст!")
                return {}
            
            all_messages = {}
            
            for row in records[1:]:  # Пропускаем заголовок
                if not row or len(row) < 12:
                    continue
                
                speed_range = row[0].strip()
                
                if speed_range not in ['94+', '90-94', '85-90', '80-84.9', 'Ниже 80']:
                    continue
                
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
        """Парсит процент из строки или числа"""
        if not value:
            return None
        
        if isinstance(value, str):
            value = value.strip()
            # Убираем знак процента
            if value.endswith('%'):
                value = value[:-1]
            # Заменяем запятую на точку
            value = value.replace(',', '.')
            # Убираем пробелы
            value = value.strip()
        
        try:
            num = float(value)
            # Если число меньше 1 (например, 0.94), умножаем на 100
            if num <= 1:
                num = num * 100
            return round(num, 1)
        except (ValueError, TypeError):
            return None
