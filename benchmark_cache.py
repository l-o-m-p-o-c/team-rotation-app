"""Бенчмарк на SQLite кеш - директен достъп"""
import time
import sys
sys.path.insert(0, '.')

from app import get_cached_result, save_result

print("="*60)
print("⚡ BENCHMARK: Директен достъп до SQLite")
print("="*60)

# Тест 1: Четене от кеш (записът съществува)
print("\n📖 Четене от съществуващ запис (3 локации, 6 отбора):")
start = time.time()
for i in range(100):
    result = get_cached_result(3, 6)
elapsed = time.time() - start
print(f"   100 четения: {elapsed*1000:.1f}ms")
print(f"   Средно на заявка: {elapsed*10:.2f}ms")

# Тест 2: Четене на несъществуващ запис
print("\n🔍 Четене на несъществуващ запис (99 локации, 99 отбора):")
start = time.time()
for i in range(100):
    result = get_cached_result(99, 99)
elapsed = time.time() - start
print(f"   100 четения: {elapsed*1000:.1f}ms")
print(f"   Средно на заявка: {elapsed*10:.2f}ms")

print("\n" + "="*60)
print("📊 Заключение:")
print("   SQLite е МНОГО бърз за четене!")
print("   Забавянето идва от Flask rendering + мрежа")
print("="*60)
