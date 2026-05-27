import requests
import time
import base64
import os
import re
import shutil
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== НАСТРОЙКИ ====================
MAX_WORKERS = 12          # Количество одновременных скачиваний
MAX_LINKS_PER_FILE = 4000
MAX_HYSTERIA2_SIZE_MB = 90

INPUT_FILE = "links.txt"
RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

# Логи
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s',
    handlers=[
        logging.FileHandler("merge_log.txt", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

print(f"[{datetime.now()}] 🚀 Kumprump запущен")

# ==================== СОЗДАЁМ ПАПКИ ====================
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]
for t in types:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# ==================== ОЧИСТКА (кроме hysteria2) ====================
def clear_folder(folder_path):
    if not os.path.exists(folder_path):
        return
    for item in os.listdir(folder_path):
        item_path = os.path.join(folder_path, item)
        try:
            if os.path.isfile(item_path):
                os.remove(item_path)
            elif os.path.isdir(item_path):
                shutil.rmtree(item_path)
        except:
            pass

logger.info("🧹 Очищаем все папки кроме hysteria2...")
clear_folder(RU_FOLDER)
clear_folder(WORLD_FOLDER)

for t in types:
    if t != "hysteria2":
        clear_folder(f"{TYPE_FOLDER}/{t}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ====================
def clean_url(url):
    return url.strip().strip('"\' \t\n')

def is_proxy_link(line):
    if not line or line.startswith('#'):
        return False
    lower = line.lower()
    return any(lower.startswith(p) for p in ["vless://", "vmess://", "trojan://", "ss://", "hysteria2://", "hy2://", "tuic://"])

def get_proxy_type(link):
    lower = link.lower()
    if lower.startswith(("hysteria2://", "hy2://")): return "hysteria2"
    if lower.startswith("vless://"): return "vless"
    if lower.startswith("vmess://"): return "vmess"
    if lower.startswith("trojan://"): return "trojan"
    if lower.startswith("ss://"): return "shadowsocks"
    if lower.startswith("tuic://"): return "tuic"
    return "other"

def is_russian_config(link):
    lower = link.lower()
    keywords = ["ru-", "🇷🇺", "russia", "moscow", "spb"]
    return any(k in lower for k in keywords)

def get_fingerprint(link):
    if "hysteria2://" in link or "hy2://" in link:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(link)
            return f"hy2:{parsed.username}@{parsed.hostname}:{parsed.port}"
        except:
            pass
    return link[:150]

def decode_base64_if_needed(content):
    content = content.strip()
    if "://" in content[:300]:
        return content
    try:
        return base64.b64decode(content + "==").decode("utf-8", errors="ignore")
    except:
        try:
            return base64.urlsafe_b64decode(content + "==").decode("utf-8", errors="ignore")
        except:
            return content

# ==================== ЗАГРУЗКА СТАРЫХ HYSTERIA2 ====================
def load_existing_hysteria2():
    folder = f"{TYPE_FOLDER}/hysteria2"
    configs = []
    seen = set()
    if not os.path.exists(folder):
        return configs
    for file in sorted(os.listdir(folder)):
        if not file.endswith(".txt"):
            continue
        try:
            with open(f"{folder}/{file}", "r", encoding="utf-8", errors="ignore") as f:
                content = decode_base64_if_needed(f.read())
                for line in content.splitlines():
                    line = line.strip()
                    if line and ("hysteria2://" in line.lower() or "hy2://" in line.lower()):
                        fp = get_fingerprint(line)
                        if fp not in seen:
                            seen.add(fp)
                            configs.append(line)
        except:
            continue
    return configs

# ==================== СКАЧИВАНИЕ ОДНОЙ ССЫЛКИ ====================
def fetch_one_url(url):
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return url, decode_base64_if_needed(r.text)
        except:
            time.sleep(2)
    return url, None

# ===================== ГЛАВНЫЙ ЗАПУСК =====================
with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
    urls = [clean_url(line) for line in f if clean_url(line) and not clean_url(line).startswith("#")]

logger.info(f"Найдено {len(urls)} ссылок. Начинаем скачивание...")

merged = []
seen = set()

# Параллельное скачивание
with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    future_to_url = {executor.submit(fetch_one_url, url): url for url in urls}
    
    for future in as_completed(future_to_url):
        url, content = future.result()
        if content:
            added = 0
            for line in content.splitlines():
                line = line.strip()
                if is_proxy_link(line):
                    fp = get_fingerprint(line)
                    if fp not in seen:
                        seen.add(fp)
                        merged.append(line)
                        added += 1
            if added > 0:
                logger.info(f"+ {added} конфигов из {url[:70]}...")

print(f"\nВсего уникальных конфигов: {len(merged)}")

# ==================== HYSTERIA2 (накопление) ====================
old_hy = load_existing_hysteria2()
new_hy = [link for link in merged if get_proxy_type(link) == "hysteria2"]
all_hysteria2 = old_hy + [x for x in new_hy if get_fingerprint(x) not in [get_fingerprint(y) for y in old_hy]]

# ==================== СОХРАНЕНИЕ ====================
def save_chunks(links, folder, prefix, max_per_file=MAX_LINKS_PER_FILE, max_size_mb=None):
    if not links:
        return
    current = []
    part = 1
    for link in links:
        current.append(link)
        if len(current) >= max_per_file:
            filename = f"{folder}/{prefix}_{part}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(current) + "\n")
            current = []
            part += 1
    if current:
        filename = f"{folder}/{prefix}_{part}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(current) + "\n")

ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")
save_chunks(all_hysteria2, f"{TYPE_FOLDER}/hysteria2", "hysteria2", max_size_mb=MAX_HYSTERIA2_SIZE_MB)

for t in types:
    if t == "hysteria2":
        continue
    links = [link for link in merged if get_proxy_type(link) == t]
    if links:
        save_chunks(links, f"{TYPE_FOLDER}/{t}", t)

# Общий файл
with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

logger.info("🎉 Скрипт успешно завершён!")
print("🎉 Готово! Hysteria2 копится, остальное — только свежее.")