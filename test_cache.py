"""
Тест за SQLite кеш функционалност
"""
import requests
import time

BASE_URL = "http://localhost:5000"

def test_cache():
    print("="*60)
    print("🧪 ТЕСТ НА SQLite КЕШ ФУНКЦИОНАЛНОСТ")
    print("="*60)
    
    # Тест 1: Първо изчисление (трябва да е бавно)
    print("\n1️⃣ ПЪРВИ ОПИТ: 3 локации, 6 отбора")
    print("   Очаквано: Изчисление от solver (~2-5 секунди)")
    
    start = time.time()
    response1 = requests.post(BASE_URL, data={"locations": 3, "teams": 6})
    elapsed1 = time.time() - start
    
    if "⚡ Резултатът е зареден от кеша" in response1.text:
        print(f"   ⚠️  От кеш (неочаквано): {elapsed1:.2f}s")
    else:
        print(f"   ✅ Изчислено: {elapsed1:.2f}s")
    
    # Тест 2: Втори опит със същите данни (трябва да е моментално от кеш)
    print("\n2️⃣ ВТОРИ ОПИТ: 3 локации, 6 отбора (същите данни)")
    print("   Очаквано: Зареждане от кеш (<0.1 секунди)")
    
    start = time.time()
    response2 = requests.post(BASE_URL, data={"locations": 3, "teams": 6})
    elapsed2 = time.time() - start
    
    if "⚡ Резултатът е зареден от кеша" in response2.text:
        print(f"   ✅ От кеш: {elapsed2:.2f}s")
        print(f"   🚀 Подобрение: {elapsed1/elapsed2:.0f}x по-бързо!")
    else:
        print(f"   ❌ НЕ е от кеш (грешка): {elapsed2:.2f}s")
    
    # Тест 3: Различни данни (трябва да изчисли отново)
    print("\n3️⃣ ТРЕТИ ОПИТ: 5 локации, 10 отбора (нови данни)")
    print("   Очаквано: Изчисление от solver")
    
    start = time.time()
    response3 = requests.post(BASE_URL, data={"locations": 5, "teams": 10})
    elapsed3 = time.time() - start
    
    if "⚡ Резултатът е зареден от кеша" in response3.text:
        print(f"   ⚠️  От кеш (неочаквано): {elapsed3:.2f}s")
    else:
        print(f"   ✅ Изчислено: {elapsed3:.2f}s")
    
    # Тест 4: Повторение на третия опит (от кеш)
    print("\n4️⃣ ЧЕТВЪРТИ ОПИТ: 5 локации, 10 отбора (повторение)")
    print("   Очаквано: Зареждане от кеш")
    
    start = time.time()
    response4 = requests.post(BASE_URL, data={"locations": 5, "teams": 10})
    elapsed4 = time.time() - start
    
    if "⚡ Резултатът е зареден от кеша" in response4.text:
        print(f"   ✅ От кеш: {elapsed4:.2f}s")
        print(f"   🚀 Подобрение: {elapsed3/elapsed4:.0f}x по-бързо!")
    else:
        print(f"   ❌ НЕ е от кеш (грешка): {elapsed4:.2f}s")
    
    # Обобщение
    print("\n" + "="*60)
    print("📊 ОБОБЩЕНИЕ")
    print("="*60)
    
    cache_working = (
        "⚡ Резултатът е зареден от кеша" in response2.text and
        "⚡ Резултатът е зареден от кеша" in response4.text
    )
    
    if cache_working:
        print("✅ SQLite кешът работи ПЕРФЕКТНО!")
        print(f"   • Първо изчисление: {elapsed1:.2f}s")
        print(f"   • От кеш: {elapsed2:.2f}s ({elapsed1/elapsed2:.0f}x по-бързо)")
    else:
        print("❌ SQLite кешът НЕ работи правилно")
    
    print("="*60 + "\n")

if __name__ == "__main__":
    time.sleep(1)  # Изчакване сървърът да стартира
    test_cache()
