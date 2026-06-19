#!/usr/bin/env python
# test_processor.py - Тест обработки данных из таблиц

import json
from data_processor import DataProcessor
from logger_setup import logger


def test_processor():
    """Тестирование обработки данных"""
    logger.info("🧪 Запуск теста обработки данных...")
    
    try:
        processor = DataProcessor()
        data = processor.process_all_data()
        
        print("\n" + "="*60)
        print("📊 РЕЗУЛЬТАТЫ ОБРАБОТКИ")
        print("="*60)
        
        # Агенты по ГЕО
        print("\n📌 АГЕНТЫ ПО ГЕО:")
        for geo, agents in data.agents_by_geo.items():
            print(f"\n  {geo} ({len(agents)} агентов):")
            for agent in agents[:3]:  # Показываем первых 3
                print(f"    - {agent.name}")
                print(f"      Группа: {agent.group_name}")
                print(f"      0-5 мин: {agent.share_0_5}%")
                print(f"      120+ мин: {agent.share_120}%")
                print(f"      Рефилов: {agent.refill_count}")
        
        # Сообщения
        print("\n" + "="*60)
        print("📝 СООБЩЕНИЯ ПО ГЕО:")
        for geo, gm in data.geo_messages.items():
            print(f"\n  {geo}:")
            for speed_range, msg in gm.messages.items():
                print(f"    {speed_range}:")
                print(f"      first: {msg.first[:50]}...")
                print(f"      second: {msg.second[:50]}...")
                print(f"      third: {msg.third[:50]}...")
                print(f"      fourth: {msg.fourth[:50]}...")
                print(f"      fifth: {msg.fifth[:50]}...")
                print(f"      random: {msg.get_random_message()[:50]}...")
        
        # Разделение INR и OTHER
        print("\n" + "="*60)
        print("🔄 РАЗДЕЛЕНИЕ ПО БОТАМ:")
        print(f"\n  🤖 INR бот: {len(data.inr_agents)} агентов")
        for agent in data.inr_agents[:3]:
            print(f"    - {agent.name} ({agent.share_0_5}%)")
        
        print(f"\n  🤖 OTHER бот: {len(data.other_agents)} агентов")
        for agent in data.other_agents[:3]:
            print(f"    - {agent.name} ({agent.share_0_5}%)")
        
        print("\n" + "="*60)
        print("✅ Тест завершен успешно!")
        
        # Сохраняем результат в JSON для отладки
        # with open('processed_data.json', 'w', encoding='utf-8') as f:
        #     json.dump(data, f, default=str, indent=2, ensure_ascii=False)
        # print("\n📁 Данные сохранены в processed_data.json")
        
    except Exception as e:
        logger.error(f"❌ Ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    test_processor()
