"""
Тестове за v1-simple версията
"""
import requests
import time

BASE_URL = "http://localhost:5000"

def test_case(name, locations, teams, should_succeed=True):
    """Изпълнява един тест"""
    print(f"\n{'='*60}")
    print(f"🧪 Тест: {name}")
    print(f"   Локации: {locations}, Отбори: {teams}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            BASE_URL,
            data={"locations": locations, "teams": teams},
            timeout=180
        )
        
        if response.status_code != 200:
            print(f"❌ HTTP грешка: {response.status_code}")
            return False
        
        content = response.text
        
        # Проверка за грешки - по-точна
        has_error = '<div class="error-message">' in content
        
        if should_succeed and has_error:
            # Извличане на съобщението за грешка
            if "трябва да бъде четно число" in content:
                print("❌ FAIL: Получена грешка за нечетен брой отбори")
            elif "не може да е повече от двойния брой локации" in content:
                print("❌ FAIL: Получена грешка за твърде много отбори")
            else:
                print("❌ FAIL: Получена неочаквана грешка")
            return False
        elif not should_succeed and not has_error:
            print("❌ FAIL: Очаквахме грешка, но не получихме такава")
            return False
        elif not should_succeed and has_error:
            if "четно число" in content:
                print("✅ PASS: Валидация за нечетен брой работи правилно")
            elif "двойния брой локации" in content:
                print("✅ PASS: Валидация за твърде много отбори работи правилно")
            else:
                print("✅ PASS: Получена очаквана грешка")
            return True
        else:
            # Проверка за успешен резултат
            if "Въведени данни:" in content:
                # Извличане на брой рундове
                rounds_count = content.count("<tr>") - 1  # -1 за header row
                print(f"✅ PASS: Генериран график с {rounds_count} рунда")
                
                # Проверка за почиващи отбори (не трябва да има)
                if "Почиващи" in content:
                    print("⚠️  WARNING: Има колона 'Почиващи' (не трябва)")
                
                # Проверка за повторения
                if "Няма повтарящи се двубои 🎉" in content:
                    print("   → Няма повторения - отлично!")
                elif "Повтарящи се двубои" in content:
                    print("   → Има някои повторения")
                
                return True
            else:
                print("❌ FAIL: Липсва резултат в отговора")
                return False
                
    except requests.exceptions.Timeout:
        print("❌ TIMEOUT: Заявката отне твърде много време (>180s)")
        return False
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")
        return False

def main():
    print("""
╔════════════════════════════════════════════════════════════╗
║          ТЕСТОВЕ ЗА v1-simple ВЕРСИЯ                       ║
╚════════════════════════════════════════════════════════════╝
""")
    
    # Изчакване сървърът да стартира
    print("⏳ Проверка дали сървърът работи...")
    time.sleep(1)
    
    try:
        requests.get(BASE_URL, timeout=5)
        print("✅ Сървърът е достъпен\n")
    except:
        print("❌ Сървърът НЕ работи на http://localhost:5000")
        print("   Моля, стартирай 'python app.py' първо")
        return
    
    results = []
    
    # Тест 1: Базов работещ случай
    results.append(test_case(
        "Базов тест (3 локации, 6 отбора)",
        locations=3,
        teams=6,
        should_succeed=True
    ))
    
    # Тест 2: Валидация - нечетен брой отбори
    results.append(test_case(
        "Валидация: Нечетен брой отбори",
        locations=2,
        teams=5,
        should_succeed=False
    ))
    
    # Тест 3: Валидация - твърде много отбори
    results.append(test_case(
        "Валидация: Твърде много отбори (6 > 2×2)",
        locations=2,
        teams=6,
        should_succeed=False
    ))
    
    # Тест 4: Граничен случай
    results.append(test_case(
        "Граничен случай (3 локации, 4 отбора)",
        locations=3,
        teams=4,
        should_succeed=True
    ))
    
    # Тест 5: Максимален капацитет
    results.append(test_case(
        "Максимален капацитет (5 локации, 10 отбора)",
        locations=5,
        teams=10,
        should_succeed=True
    ))
    
    # Тест 6: Минимален случай
    results.append(test_case(
        "Минимален случай (1 локация, 2 отбора)",
        locations=1,
        teams=2,
        should_succeed=True
    ))
    
    # Обобщение
    print(f"\n{'='*60}")
    print("📊 ОБОБЩЕНИЕ НА ТЕСТОВЕТЕ")
    print(f"{'='*60}")
    passed = sum(results)
    total = len(results)
    print(f"✅ Успешни: {passed}/{total}")
    print(f"❌ Неуспешни: {total - passed}/{total}")
    
    if passed == total:
        print("\n🎉 ВСИЧКИ ТЕСТОВЕ ПРЕМИНАХА УСПЕШНО!")
    else:
        print(f"\n⚠️  {total - passed} теста не преминаха")
    
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
