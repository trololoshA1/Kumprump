import requests
import time
import base64
import os
from datetime import datetime

# ================== НАСТРОЙКИ ==================
INPUT_FILE = "links.txt"
SUBS_FOLDER = "subs"                    # папка, куда будут сохраняться части
MAX_LINKS_PER_FILE = 4000               # максимум 4000 ссылок в одном файле
TIMEOUT = 15
RETRIES = 3
DELAY = 1.2                             # пауза между запросами, чтобы не словить бан
# ===============================================

def is_proxy_link(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return False
    return any(line.startswith(p) for p in [
        "vless://", "vmess://", "trojan://", "ss://", 
        "warp://", "hysteria2://", "hy2://", "tuic://"
    ])

print(f"[{datetime.now()}] Запуск сбора подписок...")

# Создаём папку subs, если её нет
os.makedirs(SUBS_FOLDER, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = []
total_found = 0

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] Скачиваю: {url[:90]}...")
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text

            # Раскодируем base64, если подписка закодирована
            if "://" not in content[:300] and len(content) > 800:
                try:
                    content = base64.b64decode(content + "===").decode("utf-8", errors="ignore")
                except:
                    pass

            for line in content.splitlines():
                if is_proxy_link(line):
                    merged.append(line.strip())
                    total_found += 1
            break
        except Exception as e:
            print(f"   Ошибка попытка {attempt+1}: {e}")
            time.sleep(2)

    time.sleep(DELAY)

# Убираем дубли (сохраняем первый встреченный порядок)
merged = list(dict.fromkeys(merged))

print(f"\nСобрано {len(merged)} уникальных конфигов.")

# Разбиваем на файлы по 4000 штук и сохраняем в папку subs/
for i in range(0, len(merged), MAX_LINKS_PER_FILE):
    chunk = merged[i:i + MAX_LINKS_PER_FILE]
    part_num = (i // MAX_LINKS_PER_FILE) + 1
    filename = f"merged_part_{part_num}.txt"
    filepath = os.path.join(SUBS_FOLDER, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        for link in chunk:
            f.write(link + "\n")
    
    print(f"→ Создан {filepath} — {len(chunk)} конфигов")

print(f"\nГотово! Все части лежат в папке /{SUBS_FOLDER}/")
print("Теперь в клиенте добавляй все файлы из этой папки (raw-ссылки).")