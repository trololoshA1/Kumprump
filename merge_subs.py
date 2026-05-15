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

print(f"[{datetime.now()}] 🚀 Запуск...")

# Создаём папки
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]
for t in types:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# ===================== ОЧИСТКА ССЫЛОК =====================
def clean_url(url: str) -> str:
    # Убираем невидимые символы, BOM, нулевые ширины и т.д.
    url = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', url.strip())
    url = url.strip('"\' \t\n')
    return url

# ===================== ФУНКЦИИ =====================
def is_proxy_link(line: str) -> bool:
    line = line.strip()
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
    keywords = ["ru-", "🇷🇺", "russia", "moscow", "yandex", "vk.com", "ozon"]
    return any(k in lower for k in keywords)

# ===================== ЧТЕНИЕ И ОЧИСТКА =====================
with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
    raw_urls = f.readlines()

urls = []
for line in raw_urls:
    cleaned = clean_url(line)
    if cleaned and not cleaned.startswith('#'):
        urls.append(cleaned)

print(f"Найдено {len(urls)} ссылок после очистки\n")

# ===================== ОСНОВНОЙ ЦИКЛ =====================
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
            print(f"   + {added} конфигов")
            break
        except Exception as e:
            print(f"   Ошибка {attempt+1}/3: {e}")
            time.sleep(2)
    time.sleep(1.2)

print(f"\nУникальных конфигов: {len(merged)}")

# Разделение и сохранение (оставил как было)
ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

type_links = {t: [] for t in types}
for link in merged:
    type_links[get_proxy_type(link)].append(link)

# Сохранение (упрощённо)
def save_chunks(links, folder, prefix):
    if not links: return
    with open(f"{folder}/{prefix}_1.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(links))

save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")

for t, links in type_links.items():
    save_chunks(links, f"{TYPE_FOLDER}/{t}", t)

with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print("🎉 Готово!")