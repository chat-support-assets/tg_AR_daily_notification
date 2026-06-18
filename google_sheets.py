import gspread
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from config import SERVICE_ACCOUNT_FILE, SPREADSHEET_ID, SHEET_TOTAL_SCORE, SHEET_AR_TEXT
from logger_setup import logger
import os


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
            # или используем email из service_account.json
            impersonate_email = os.getenv('IMPERSONATE_EMAIL')
            
            if not impersonate_email:
                # Если не задан, пробуем взять из service_account.json
                import json
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
            
            # Если указан email для impersonate, подменяем
            if impersonate_email:
                creds = creds.with_subject(impersonate_email)
                logger.info(f"✅ Используем impersonate: {impersonate_email}")
            
            self.client = gspread.authorize(creds)
            
            # Проверяем доступ к таблице
            self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
            
            # Проверяем, что листы существуют
            self._check_sheets_exist()
            
            logger.info("✅ Успешное подключение к Google Sheets с impersonate")
            
        except FileNotFoundError as e:
            logger.error(f"❌ {e}")
            raise
        except ValueError as e:
            logger.error(f"❌ {e}")
            raise
        except GoogleAuthError as e:
            logger.error(f"❌ Ошибка аутентификации Google: {e}")
            logger.error("Проверьте service_account.json и права доступа")
            raise
        except gspread.exceptions.APIError as e:
            if "PERMISSION_DENIED" in str(e):
                logger.error("❌ Ошибка доступа к таблице!")
                logger.error(f"  - Проверьте ID таблицы: {SPREADSHEET_ID}")
                logger.error(f"  - Email для impersonate: {impersonate_email if impersonate_email else 'не указан'}")
                logger.error("  - Убедитесь, что аккаунт имеет доступ к таблице")
                logger.error("  - Добавьте email пользователя в список доступа к таблице")
            elif "NOT_FOUND" in str(e):
                logger.error(f"❌ Таблица с ID {SPREADSHEET_ID} не найдена!")
                logger.error("Проверьте правильность ID в .env файле")
            else:
                logger.error(f"❌ Ошибка API Google Sheets: {e}")
            raise
        except Exception as e:
            logger.error(f"❌ Ошибка подключения к Google Sheets: {e}")
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
            
            for row in records:
                if not row or not row[0]:
                    continue
                
                agent_name = row[0].strip()
                
                # Пропускаем заголовки
                if agent_name.startswith('Agent') or agent_name.startswith('Name'):
                    continue
                
                share_0_5 = self._parse_percentage(row[2]) if len(row) > 2 else None
                share_120 = self._parse_percentage(row[7]) if len(row) > 7 else None
                
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
