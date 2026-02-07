"""Проверка за теста 3 локации, 4 отбора"""
import requests
import re

response = requests.post(
    "http://localhost:5000",
    data={"locations": 3, "teams": 4}
)

content = response.text

# Проверка за грешка
if '<div class="error-message">' in content:
    start = content.find('<div class="error-message">')
    end = content.find('</div>', start)
    error_msg = content[start:end]
    error_text = re.sub('<.*?>', '', error_msg)
    print("ГРЕШКА:")
    print(error_text.strip())
elif "Въведени данни:" in content:
    print("✅ УСПЕХ: Има резултат")
    # Проверка за повторения
    if "Няма повтарящи се двубои" in content:
        print("   → Няма повторения")
    else:
        print("   → Има повторения")
else:
    print("⚠️  Непознат отговор")
