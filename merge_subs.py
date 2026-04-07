import requests
import time
import base64
import os
import re
from datetime import datetime

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000

RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"

# Агрессивные признаки российских конфигов
RU_IP_PREFIXES = [
    "77.232.", "85.193.", "94.228.", "94.232.", "95.163.", "109.194.", "109.195.",
    "185.", "212.193.", "217.106.", "217.107.", "217.112.", "217.118.", "91.243.",
    "176.99.", "178.154.", "178.210.", "188.162.", "188.225."
]

RU_KEYWORDS = [
    "RU-", "%5DRU-", "🇷🇺", "ads.x5.ru", "max.ru", "rbc.ru", "yandex", "vk.com",
    "ozon.ru", "wildberries", "gosuslugi", "sber.ru", "tbank", "goodcardboard.shop",
    "convert24.ru", "trost-shield.ru", "ray-balance.space"
]

def is_proxy_link(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return False
    return any(line.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://", "warp://", "hysteria2://", "hy2://", "tuic://"])

def extract_ip(link):
    matches = re.findall(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', link)
    for m in matches:
        if m.startswith(("10.", "172.16.", "192.168.")):
            continue
        return m
    return None

def is_russian_config(link):
    lower = link.lower()
    ip = extract_ip(link)
    
    # Проверка по IP
    if ip and any(ip.startswith(p) for p in RU_IP_PREFIXES):
        return True
    
    # Проверка по ключевым словам и RU-меткам
    if any(kw.lower() in lower for kw in RU_KEYWORDS):
        return True
    if re.search(r'RU-\d{4,5}', link):
        return True
    
    return False

print(f"[{datetime.now()}] Запуск скрипта с очисткой папки subs...")

# ================== ПОЛНАЯ ОЧИСТКА ПАПКИ SUBS ==================
if os.path.exists("subs"):
    for root, dirs, files in os.walk("subs", topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            os.rmdir(os.path.join(root, name))
    print("✅ Папка subs полностью очищена")

# Создаём чистые папки
os.makedirs(RU_FOLDER, exist_ok=True)
os.makedirs(WORLD_FOLDER, exist_ok=True)

# ================== СБОР КОНФИГОВ ==================
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = []
for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] Скачиваю: {url[:80]}...")
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text

            if "://" not in content[:300] and len(content) > 800:
                try:
                    content = base64.b64decode(content + "===").decode("utf-8", errors="ignore")
                except:
                    pass

            for line in content.splitlines():
                if is_proxy_link(line):
                    merged.append(line.strip())
            break
        except Exception as e:
            if attempt == 2:
                print(f"   Не удалось скачать: {e}")
            time.sleep(2)
    time.sleep(1.1)

merged = list(dict.fromkeys(merged))  # удаляем дубли

ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

print(f"\nВсего конфигов: {len(merged)}")
print(f"→ Российских (RU): {len(ru_links)}")
print(f"→ Зарубежных (World): {len(world_links)}")

# ================== СОХРАНЕНИЕ ==================
for folder, links, prefix in [(RU_FOLDER, ru_links, "ru_part"), (WORLD_FOLDER, world_links, "world_part")]:
    for i in range(0, len(links), MAX_LINKS_PER_FILE):
        chunk = links[i:i + MAX_LINKS_PER_FILE]
        part = (i // MAX_LINKS_PER_FILE) + 1
        filepath = f"{folder}/{prefix}_{part}.txt"
        with open(filepath, "w", encoding="utf-8") as f:
            for link in chunk:
                f.write(link + "\n")
        print(f"→ Создан {filepath} — {len(chunk)} конфигов")

print(f"\n✅ Готово! Папки ru и world полностью обновлены и очищены от старого мусора.")