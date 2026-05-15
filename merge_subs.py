import requests
import time
import base64
import os
import re
from datetime import datetime

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000

# ===================== ПАПКИ =====================
RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

print(f"[{datetime.now()}] 🚀 Запуск мержа (регионы + типы)...")

# Создаём все папки
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)
    print(f"✅ Создана: {folder}")

types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]
for t in types:
    path = f"{TYPE_FOLDER}/{t}"
    os.makedirs(path, exist_ok=True)
    print(f"✅ Создана папка типа: {path}")

# ===================== ФУНКЦИИ =====================
def is_proxy_link(line: str) -> bool:
    if not line or line.startswith('#'):
        return False
    lower = line.strip().lower()
    return any(lower.startswith(p) for p in [
        "vless://", "vmess://", "trojan://", "ss://", 
        "hysteria2://", "hy2://", "tuic://"
    ])

def get_proxy_type(link: str) -> str:
    lower = link.lower()
    if lower.startswith("vless://"): return "vless"
    if lower.startswith("vmess://"): return "vmess"
    if lower.startswith("trojan://"): return "trojan"
    if lower.startswith(("hysteria2://", "hy2://")): return "hysteria2"
    if lower.startswith("ss://"): return "shadowsocks"
    if lower.startswith("tuic://"): return "tuic"
    return "other"

def is_russian_config(link: str) -> bool:
    lower = link.lower()
    # По IP и ключевым словам
    ru_keywords = ["ru-", "🇷🇺", "russia", "moscow", "spb", "yandex", "vk.com", "ozon", "wildberries", "sber"]
    ru_ip_start = ["185.", "77.232.", "94.228.", "212.193.", "217.106.", "31.172.", "45.8.", "46.19."]
    
    if any(kw in lower for kw in ru_keywords):
        return True
    if any(link.startswith(ip) for ip in ru_ip_start if re.search(r'@' + ip, link)):
        return True
    return False

# ===================== СКАЧИВАНИЕ =====================
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

print(f"Найдено {len(urls)} ссылок в links.txt\n")

merged = []
seen = set()

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] ↓ {url[:75]}")
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text

            if "://" not in content[:120]:
                try:
                    content = base64.b64decode(content + "==").decode("utf-8", errors="ignore")
                except:
                    pass

            added = 0
            for line in content.splitlines():
                line = line.strip()
                if is_proxy_link(line):
                    fp = line[:120]  # дедупликация
                    if fp not in seen:
                        seen.add(fp)
                        merged.append(line)
                        added +=