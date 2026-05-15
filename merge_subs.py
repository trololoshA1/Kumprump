import requests
import time
import base64
import os
import re
from datetime import datetime
from urllib.parse import urlparse

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000

RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def is_proxy_link(line: str) -> bool:
    if not line or line.startswith("#"):
        return False
    lower = line.lower()
    return any(lower.startswith(p) for p in [
        "vless://", "vmess://", "trojan://", "ss://", 
        "hysteria2://", "hy2://", "tuic://"
    ])


def extract_ip(link: str) -> str:
    """Простое извлечение IP"""
    try:
        match = re.search(r'@([\d.]+):', link)
        if match:
            return match.group(1)
        # IPv6
        match = re.search(r'@(\[[0-9a-fA-F:]+\]):', link)
        if match:
            return match.group(1)
    except:
        pass
    return ""


def get_proxy_fingerprint(link: str) -> str:
    """Дедупликация"""
    link = link.strip()
    try:
        if link.startswith("vmess://"):
            return link[:200]  # vmess часто длинные
        parsed = urlparse(link.replace("vmess://", "http://").replace("vless://", "http://"))
        host = parsed.hostname or parsed.netloc.split(':')[0]
        port = parsed.port or ""
        user = parsed.username or ""
        key = f"{parsed.scheme}://{user}@{host}:{port}"
        return key.lower()
    except:
        return link.lower()


def get_proxy_type(link: str) -> str:
    lower = link.lower()
    if lower.startswith("vless://"): return "vless"
    elif lower.startswith("vmess://"): return "vmess"
    elif lower.startswith("trojan://"): return "trojan"
    elif lower.startswith(("hysteria2://", "hy2://")): return "hysteria2"
    elif lower.startswith("ss://"): return "shadowsocks"
    elif lower.startswith("tuic://"): return "tuic"
    else: return "other"


def is_russian_config(link: str) -> bool:
    lower = link.lower()
    ip = extract_ip(link)
    
    RU_IP_PREFIXES = ["31.172.", "45.8.", "45.67.", "46.19.", "46.151.", "62.141.", "77.232.", "79.137.", "80.66.", "80.76.", "80.85.", "82.146.", "85.142.", "85.192.", "87.226.", "89.113.", "91.103.", "92.38.", "92.50.", "94.19.", "94.142.", "95.31.", "95.54.", "95.181.", "176.59.", "178.176.", "178.210.", "185.12.", "185.43.", "185.71.", "185.137.", "185.149.", "185.165.", "185.170.", "185.182.", "188.68.", "188.191.", "193.32.", "194.28.", "195.9.", "195.82.", "212.109.", "217.12.", "217.106."]
    
    RU_KEYWORDS = ["ru", "moscow", "spb", "saintpetersburg", "rostov", "novosibirsk", "ekb", "yandex", "vk.com", "mail.ru", "ozon", "wildberries"]
    
    if ip:
        if any(ip.startswith(p) for p in RU_IP_PREFIXES):
            return True
    if any(kw in lower for kw in RU_KEYWORDS):
        return True
    if re.search(r'RU-\d', link, re.I):
        return True
    return False


# ==================== ОСНОВНОЙ КОД ====================
print(f"[{datetime.now()}] Запуск мержа с дедупликацией и типами...")

# Создаём папки
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

for t in ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# Читаем ссылки
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = []
seen = set()

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] Скачиваем: {url[:70]}...")
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text.strip()

            # Попытка декодировать base64
            if "://" not in content[:100]:
                try:
                    decoded = base64.b64decode(content + "==").decode("utf-8", errors="ignore")
                    content = decoded
                except:
                    pass

            for line in content.splitlines():
                line = line.strip()
                if not is_proxy_link(line):
                    continue
                fp = get_proxy_fingerprint(line)
                if fp not in seen:
                    seen.add(fp)
                    merged.append(line)
            break
        except Exception as e:
            print(f"   Попытка {attempt+1} ошибка: {e}")
            time.sleep(3)
    time.sleep(1)

print(f"\nУникальных конфигов после дедупликации: {len(merged)}")

# Разделяем
ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

type_links = {"vless": [], "vmess": [], "trojan": [], "hysteria2": [], 
              "shadowsocks": [], "tuic": [], "other": []}

for link in merged:
    t = get_proxy_type(link)
    type_links[t].append(link)

print(f"RU: {len(ru_links)} | World: {len(world_links)}")
for t, lst in type_links.items():
    print(f"  {t}: {len(lst)}")

# Сохранение
def save_chunks(links, folder, prefix, base64_encode=False):
    if not links:
        return
    for i in range(0, len(links), MAX_LINKS_PER_FILE):
        chunk = links[i:i+MAX_LINKS_PER_FILE]
        part = i // MAX_LINKS_PER_FILE + 1
        filename = f"{folder}/{prefix}_{part}.txt"
        
        if base64_encode:
            data = "\n".join(chunk)
            encoded = base64.b64encode(data.encode("utf-8")).decode("utf-8")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(encoded)
        else:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(chunk))

save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")

for t, links in type_links.items():
    save_chunks(links, f"{TYPE_FOLDER}/{t}", t)
    save_chunks(links, f"{TYPE_FOLDER}/{t}", f"{t}_b64", base64_encode=True)

# Общий файл
with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print("\n✅ Всё успешно завершено!")
print(f"Общее количество уникальных прокси: {len(merged)}")