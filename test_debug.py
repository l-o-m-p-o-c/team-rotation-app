"""Проверка за грешката"""
import requests

response = requests.post(
    "http://localhost:5000",
    data={"locations": 3, "teams": 6}
)

# Извличане на съобщението за грешка
content = response.text

# Намиране на error-message div
start = content.find('<div class="error-message">')
if start != -1:
    end = content.find('</div>', start)
    error_msg = content[start:end+6]
    # Премахване на HTML таговете
    import re
    error_text = re.sub('<.*?>', '', error_msg)
    print("ГРЕШКА:")
    print(error_text.strip())
else:
    print("Няма грешка или има резултат")
    # Проверка дали има резултат
    if "Въведени данни:" in content:
        print("Има успешен резултат!")
    else:
        print("Необяснима ситуация")
