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

# Расширенные признаки российских серверов
RU_IP_PREFIXES = [
    "5.3.", "5.101.", "5.255.", "31.148.", "31.177.", "37.9.", "37.140.", "37.230.",
    "45.8.", "45.67.", "45.82.", "45.86.", "45.91.", "45.136.", "45.144.", "46.17.",
    "46.39.", "46.148.", "46.229.", "62.109.", "77.40.", "77.220.", "77.222.", "78.29.",
    "79.104.", "79.132.", "79.137.", "80.66.", "81.19.", "81.177.", "82.146.", "82.202.",
    "83.69.", "83.222.", "84.201.", "85.192.", "85.236.", "87.236.", "87.250.", "89.108.",
    "89.111.", "89.169.", "89.188.", "89.208.", "89.253.", "90.156.", "91.103.", "91.142.",
    "91.189.", "91.201.", "91.217.", "91.218.", "91.219.", "92.241.", "92.255.", "93.157.",
    "93.170.", "93.180.", "94.103.", "94.139.", "94.142.", "94.232.", "95.163.", "95.181.",
    "95.213.", "95.214.", "95.215.", "109.194.", "109.195.", "109.238.", "109.252.",
    "128.140.", "130.193.", "141.8.", "146.120.", "151.252.", "176.99.", "176.112.",
    "176.118.", "178.154.", "178.210.", "178.248.", "178.250.", "185.5.", "185.26.",
    "185.43.", "185.60.", "185.71.", "185.86.", "185.125.", "185.137.", "185.165.",
    "185.170.", "185.178.", "185.189.", "185.200.", "185.215.", "188.68.", "188.93.",
    "188.114.", "188.120.", "188.123.", "188.162.", "188.165.", "188.170.", "188.191.",
    "188.225.", "188.242.", "193.0.", "193.32.", "193.124.", "193.232.", "194.58.",
    "194.67.", "194.85.", "194.87.", "194.135.", "195.2.", "195.20.", "195.208.",
    "195.211.", "195.239.", "212.109.", "212.193.", "213.108.", "213.180.", "217.12.",
    "217.106.", "217.107.", "217.112.", "217.118."
]

RU_SNI_KEYWORDS = [
    ".ru", "yandex", "vk.com", "mail.ru", "x5.ru", "rbc.ru", "sber.ru", "ozon.ru",
    "wildberries", "avito.ru", "gosuslugi", "tbank", "alfa", "mts", "beeline",
    "megafon", "tele2", "rt.ru", "rosbank", "sberbank", "ads.x5", "max.ru"
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

def has_ru_sni(link):
    lower = link.lower()
    return any(keyword in lower for keyword in RU_SNI_KEYWORDS)

def is_russian_config(link):
    ip = extract_ip(link)
    if ip and any(ip.startswith(prefix) for prefix in RU_IP_PREFIXES):
        return True
    if has_ru_sni(link):
        return True
    return False

print(f"[{datetime.now()}] Запуск СТРОГОГО разделения RU / World...")

# Полная очистка папок перед записью
for folder in [RU_FOLDER, WORLD_FOLDER]:
    if os.path.exists(folder):
        for file in os.listdir(folder):
            os.remove(os.path.join(folder, file))
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
    time.sleep(1.1)

merged = list(dict.fromkeys(merged))

ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

print(f"Всего конфигов: {len(merged)}")
print(f"→ Перемещено в RU: {len(ru_links)}")
print(f"→ Оставлено в World: {len(world_links)}")

# Сохраняем
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

print("✅ Готово. RU теперь должны быть чище.")