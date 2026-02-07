"""Проверка на SQLite базата данни"""
import sqlite3

conn = sqlite3.connect("cache.db")
cursor = conn.cursor()

# Виж всички записи
cursor.execute("SELECT locations, teams, created_at FROM results_cache")
rows = cursor.fetchall()

print("="*60)
print("📁 СЪДЪРЖАНИЕ НА cache.db")
print("="*60)

if rows:
    for row in rows:
        print(f"✅ {row[0]} локации, {row[1]} отбора - запазено на {row[2]}")
else:
    print("⚠️  Базата е празна")

print("="*60)
print(f"Общо записи: {len(rows)}")

conn.close()
