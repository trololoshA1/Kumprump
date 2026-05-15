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
TYPE_FOLDER = "subs/type"

print(f"[{datetime.now()}] 🚀 Запуск мержа с чанками по {MAX_LINKS_PER_FILE}...")

# Создание папок
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]
for t in types:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# Очистка ссылок от мусора
def clean_url(url: str) -> str:
    url = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', url.strip())
    return url.strip('"\' \t\n')

def is_proxy_link(line: str) -> bool:
    if not line or line.startswith('#'):
        return False
    lower = line.lower()
    return any(lower.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://", "hysteria2://", "hy2://", "tuic://"])

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
    keywords = ["ru-", "🇷🇺", "russia", "moscow", "spb", "yandex", "vk.com", "ozon", "wildberries"]
    ips = ["185.", "77.232.", "94.228.", "212.193.", "217.106."]
    return any(k in lower for k in keywords) or any(ip in link for ip in ips)

# Чтение и очистка links.txt
with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
    urls = [clean_url(line) for line in f if clean_url(line) and not clean_url(line).startswith("#")]

print(f"Найдено {len(urls)} чистых ссылок\n")

merged = []
seen = set()

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] ↓ {url[:70]}...")
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text

            if "://" not in content[:150]:
                try:
                    content = base64.b64decode(content + "==").decode("utf-8", errors="ignore")
                except:
                    pass

            added = 0
            for line in content.splitlines():
                line = line.strip()
                if is_proxy_link(line):
                    fp = line[:100]
                    if fp not in seen:
                        seen.add(fp)
                        merged.append(line)
                        added += 1
            print(f"   + {added} новых")
            break
        except Exception as e:
            print(f"   Ошибка {attempt+1}/3: {e}")
            time.sleep(2)
    time.sleep(1.2)

print(f"\nУникальных конфигов: {len(merged)}")

# Разделение
ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

type_links = {t: [] for t in types}
for link in merged:
    type_links[get_proxy_type(link)].append(link)

print(f"RU: {len(ru_links)} | World: {len(world_links)}")
for t, lst in type_links.items():
    print(f"   {t}: {len(lst)}")

# Сохранение с чанками
def save_chunks(links, folder, prefix, base64_encode=False):
    if not links:
        return
    for i in range(0, len(links), MAX_LINKS_PER_FILE):
        chunk = links[i:i + MAX_LINKS_PER_FILE]
        part = i // MAX_LINKS_PER_FILE + 1
        filename = f"{folder}/{prefix}_{part}.txt"
        
        if base64_encode:
            data = "\n".join(chunk)
            b64 = base64.b64encode(data.encode("utf-8")).decode("utf-8")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(b64)
        else:
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(chunk) + "\n")

# Сохраняем
save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")

for t, links in type_links.items():
    save_chunks(links, f"{TYPE_FOLDER}/{t}", t)
    save_chunks(links, f"{TYPE_FOLDER}/{t}", f"{t}_b64", base64_encode=True)

with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print("\n🎉 ГОТОВО! Чанки по 4000 + все папки должны быть.")