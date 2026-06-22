import gspread
import json
import os
from google.oauth2.service_account import Credentials
from google.auth.exceptions import GoogleAuthError
from config import (
    SERVICE_ACCOUNT_FILE, 
    SPREADSHEET_ID, 
    SHEET_TOTAL_SCORE, 
    SHEET_AR_TEXT,
    IMPERSONATE_EMAIL
)
from logger_setup import logger


class GoogleSheetsClient:
    """Клиент для работы с Google Sheets через impersonate"""
    
    def __init__(self):
        self.client = None
        self.spreadsheet = None
        self._authenticate()
    
    def _authenticate(self):
        """Аутентификация через сервисный аккаунт с impersonate"""
        try:
            # Проверяем наличие файла
            if not os.path.exists(SERVICE_ACCOUNT_FILE):
                raise FileNotFoundError(f"❌ Файл {SERVICE_ACCOUNT_FILE} не найден!")
            
            if os.path.getsize(SERVICE_ACCOUNT_FILE) == 0:
                raise ValueError(f"❌ Файл {SERVICE_ACCOUNT_FILE} пустой!")
            
            # Читаем email для impersonate
            if not IMPERSONATE_EMAIL:
                with open(SERVICE_ACCOUNT_FILE, 'r') as f:
                    data = json.load(f)
                    impersonate_email = data.get('client_email')
            else:
                impersonate_email = IMPERSONATE_EMAIL
            
            # Создаем учетные данные
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            creds = Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, 
                scopes=scopes
            )
            
            # Добавляем impersonate
            if impersonate_email:
                creds = creds.with_subject(impersonate_email)
            
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(SPREADSHEET_ID)
            
            logger.info("✅ Успешное подключение к Google Sheets")
            
        except Exception as e:
            logger.error(f"❌ Ошибка аутентификации: {e}")
            raise
    
    def get_worksheet(self, sheet_name: str):
        """Получить лист по имени"""
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except Exception as e:
            logger.error(f"❌ Ошибка получения листа {sheet_name}: {e}")
            raise
