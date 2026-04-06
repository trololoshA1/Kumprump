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

# === Очень агрессивные признаки российских конфигов ===
RU_IP_PREFIXES = ["77.232.", "85.193.", "94.228.", "94.232.", "95.163.", "109.194.", "109.195.", "185.", "212.193.", "217.106.", "217.107.", "217.112.", "217.118.", "91.243.", "176.99.", "178.154.", "178.210.", "188.162.", "188.225."]

RU_KEYWORDS = [
    "RU-", "%5DRU-", "🇷🇺", "ru_part", "ads.x5.ru", "max.ru", "rbc.ru", "yandex", "vk.com", 
    "ozon.ru", "wildberries", "gosuslugi", "sber.ru", "tbank", "megafon", "mts", "beeline",
    "goodcardboard.shop", "convert24.ru", "trost-shield.ru", "ray-balance.space", "frostbot.ru"
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
    
    # 1. Проверка по IP
    ip = extract_ip(link)
    if ip and any(ip.startswith(p) for p in RU_IP_PREFIXES):
        return True
    
    # 2. Проверка по ключевым словам (включая закодированные RU-)
    if any(kw.lower() in lower for kw in RU_KEYWORDS):
        return True
    
    # 3. Проверка по российским SNI в конце строки (самая частая проблема)
    if re.search(r'RU-\d{4,5}', link) or "RU-" in link:
        return True
    
    return False

print(f"[{datetime.now()}] Запуск МАКСИМАЛЬНО АГРЕССИВНОГО разделения...")

# Полная очистка папок
for folder in [RU_FOLDER, WORLD_FOLDER]:
    if os.path.exists(folder):
        for f in os.listdir(folder):
            os.remove(os.path.join(folder, f))
    os.makedirs(folder, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = []
for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] Скачиваю...")
    for _ in range(3):
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
        except:
            time.sleep(2)
    time.sleep(1)

merged = list(dict.fromkeys(merged))

ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

print(f"Всего конфигов: {len(merged)}")
print(f"→ Перемещено в RU: {len(ru_links)}")
print(f"→ Оставлено в World: {len(world_links)}")

# Сохранение
for i in range(0, len(ru_links), MAX_LINKS_PER_FILE):
    chunk = ru_links[i:i + MAX_LINKS_PER_FILE]
    part = (i // MAX_LINKS_PER_FILE) + 1
    with open(f"{RU_FOLDER}/ru_part_{part}.txt", "w", encoding="utf-8") as f:
        for link in chunk:
            f.write(link + "\n")

for i in range(0, len(world_links), MAX_LINKS_PER_FILE):
    chunk = world_links[i:i + MAX_LINKS_PER_FILE]
    part = (i // MAX_LINKS_PER_FILE) + 1
    with open(f"{WORLD_FOLDER}/world_part_{part}.txt", "w", encoding="utf-8") as f:
        for link in chunk:
            f.write(link + "\n")

print("✅ Теперь RU должны быть максимально вычищены из world.")