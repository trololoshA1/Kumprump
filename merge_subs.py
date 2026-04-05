import requests
import time
import base64
import os
import re
import ipaddress
from datetime import datetime

# ================== НАСТРОЙКИ ==================
INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000
TIMEOUT = 15
RETRIES = 3
DELAY = 1.2

# Папки для разделения
RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"

# GeoIP база (скачивается автоматически при первом запуске)
GEOIP_DB = "GeoLite2-Country.mmdb"
# ===============================================

def download_geoip_db():
    if os.path.exists(GEOIP_DB):
        return
    print("Скачиваем GeoLite2-Country базу...")
    url = "https://git.io/GeoLite2-Country.mmdb"
    r = requests.get(url, timeout=30)
    with open(GEOIP_DB, "wb") as f:
        f.write(r.content)
    print("GeoIP база скачана.")

try:
    import geoip2.database
    download_geoip_db()
    reader = geoip2.database.Reader(GEOIP_DB)
except:
    reader = None
    print("GeoIP не удалось загрузить, будет только парсинг IP без проверки страны.")

def extract_ip_from_link(link):
    """Вытаскиваем IP из конфига (vless, vmess, hysteria2, warp и т.д.)"""
    # Простой поиск IPv4
    ipv4 = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', link)
    if ipv4:
        ip = ipv4.group(1)
        try:
            ipaddress.ip_address(ip)
            return ip
        except:
            pass
    # Для Warp и некоторых других — можно расширить позже
    return None

def is_russian_ip(ip):
    if not reader or not ip:
        return False
    try:
        response = reader.country(ip)
        return response.country.iso_code == "RU"
    except:
        return False

def is_proxy_link(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return False
    return any(line.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://", "warp://", "hysteria2://", "hy2://", "tuic://"])

print(f"[{datetime.now()}] Запуск сбора и разделения подписок...")

os.makedirs(RU_FOLDER, exist_ok=True)
os.makedirs(WORLD_FOLDER, exist_ok=True)

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = []
total_ru = 0
total_world = 0

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] Обработка: {url[:90]}...")
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
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
            print(f"   Ошибка: {e}")
            time.sleep(2)
    time.sleep(DELAY)

merged = list(dict.fromkeys(merged))  # убираем дубли

print(f"\nВсего уникальных конфигов: {len(merged)}")

# Разделяем и сохраняем
ru_links = []
world_links = []

for link in merged:
    ip = extract_ip_from_link(link)
    if is_russian_ip(ip):
        ru_links.append(link)
        total_ru += 1
    else:
        world_links.append(link)
        total_world += 1

# Сохраняем RU
for i in range(0, len(ru_links), MAX_LINKS_PER_FILE):
    chunk = ru_links[i:i + MAX_LINKS_PER_FILE]
    part = (i // MAX_LINKS_PER_FILE) + 1
    path = os.path.join(RU_FOLDER, f"ru_part_{part}.txt")
    with open(path, "w", encoding="utf-8") as f:
        for l in chunk:
            f.write(l + "\n")
    print(f"→ RU: {path} — {len(chunk)} конфигов")

# Сохраняем World
for i in range(0, len(world_links), MAX_LINKS_PER_FILE):
    chunk = world_links[i:i + MAX_LINKS_PER_FILE]
    part = (i // MAX_LINKS_PER_FILE) + 1
    path = os.path.join(WORLD_FOLDER, f"world_part_{part}.txt")
    with open(path, "w", encoding="utf-8") as f:
        for l in chunk:
            f.write(l + "\n")
    print(f"→ World: {path} — {len(chunk)} конфигов")

print(f"\nГотово!")
print(f"Российских конфигов: {total_ru}")
print(f"Зарубежных: {total_world}")