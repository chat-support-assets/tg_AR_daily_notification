import os
from dotenv import load_dotenv
load_dotenv()

from google_sheets_old import GoogleSheetsClient
from logger_setup import logger


def check_table():
    """Проверка структуры таблицы"""
    try:
        sheets = GoogleSheetsClient()
        sheet = sheets.spreadsheet.worksheet('Total score')
        
        # Получаем все данные
        records = sheet.get_all_values()
        
        print(f"\n📊 Всего строк: {len(records)}")
        print("\nПервые 5 строк:")
        for i, row in enumerate(records[:5]):
            print(f"  Строка {i}: {row}")
        
        print("\n📋 Структура колонок:")
        if records:
            headers = records[0]
            for i, header in enumerate(headers):
                print(f"  Колонка {chr(65+i)}: {header}")
        
        # Проверяем наличие данных
        print("\n🔍 Поиск данных агентов:")
        agents_found = 0
        
        for i, row in enumerate(records):
            # Пропускаем только заголовки (первая строка)
            if i == 0:
                continue
            
            if not row or not row[0]:
                continue
            
            agent_name = row[0].strip()
            
            # Проверяем, что это не пустая строка и не заголовок
            if agent_name and agent_name != 'Agent':
                agents_found += 1
                print(f"\n  ✅ Агент {agents_found}: {agent_name}")
                print(f"     Колонка C (Share 0-5): {row[2] if len(row) > 2 else 'Нет'}")
                print(f"     Колонка E (Refill Count): {row[4] if len(row) > 4 else 'Нет'}")
                print(f"     Колонка H (Share 120+): {row[7] if len(row) > 7 else 'Нет'}")
        
        if agents_found == 0:
            print("\n⚠️ Агенты не найдены! Проверьте:")
            print("  1. В колонке A должны быть имена агентов")
            print("  2. Первая строка должна быть заголовком")
            print("  3. В колонке C и H должны быть проценты")
        else:
            print(f"\n✅ Всего найдено агентов: {agents_found}")
        
        # Проверяем AR_text
        print("\n📝 Лист 'AR_text':")
        sheet_ar = sheets.spreadsheet.worksheet('AR_text')
        records_ar = sheet_ar.get_all_values()
        
        print(f"  Всего строк: {len(records_ar)}")
        
        if records_ar:
            print(f"  Заголовки: {records_ar[0]}")
        
        messages = []
        for row in records_ar[1:]:
            if row and row[0]:
                speed_range = row[0].strip()
                if speed_range in ['94+', '90-94', '85-90', '80-84.9', 'Ниже 80']:
                    messages.append(speed_range)
                    print(f"  ✅ Найдены сообщения для: {speed_range}")
                    if len(row) > 7:
                        print(f"     first: {row[7][:50]}...")
                        print(f"     second: {row[8][:50]}..." if len(row) > 8 else "")
        
        print(f"\n📨 Найдено сообщений для диапазонов: {len(messages)}")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    check_table()