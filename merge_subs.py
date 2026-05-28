import requests
import time
import base64
import os
import re
import shutil
import logging
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==================== НАСТРОЙКИ ====================
MAX_WORKERS = 12
MAX_LINKS_PER_FILE = 4000

INPUT_FILE = "links.txt"
RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"
HYST_FOLDER = f"{TYPE_FOLDER}/hysteria2"

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

print(f"[{datetime.now()}] 🚀 Builder запущен")

# ==================== ПАПКИ ====================
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
        path = os.path.join(folder_path, item)
        try:
            if os.path.isfile(path):
                os.remove(path)
            else:
                shutil.rmtree(path)
        except:
            pass

logger.info("🧹 Очищаем папки (кроме hysteria2)...")
clear_folder(RU_FOLDER)
clear_folder(WORLD_FOLDER)

for t in types:
    if t != "hysteria2":
        clear_folder(f"{TYPE_FOLDER}/{t}")

# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
def clean_url(url):
    return url.strip().strip('"\' \t\n')

def is_proxy_link(line):
    if not line or line.startswith('#'):
        return False
    lower = line.lower()
    return any(lower.startswith(p) for p in [
        "vless://", "vmess://", "trojan://", "ss://",
        "hysteria2://", "hy2://", "tuic://"
    ])

def get_proxy_type(link):
    l = link.lower()
    if l.startswith(("hysteria2://", "hy2://")): return "hysteria2"
    if l.startswith("vless://"): return "vless"
    if l.startswith("vmess://"): return "vmess"
    if l.startswith("trojan://"): return "trojan"
    if l.startswith("ss://"): return "shadowsocks"
    if l.startswith("tuic://"): return "tuic"
    return "other"

RU_PATTERN = re.compile(r"(ru[-_]|🇷🇺|russia|moscow|moskva|spb|piter)", re.I)

def is_russian_config(link):
    return bool(RU_PATTERN.search(link))

def get_fingerprint(link):
    return hashlib.sha256(link.strip().encode()).hexdigest()

def decode_base64_if_needed(content):
    content = content.strip()
    if "://" in content[:300]:
        return content
    try:
        return base64.b64decode(content + "==").decode("utf-8", errors="ignore")
    except:
        return content

# ==================== ЗАГРУЗКА СТАРЫХ HYSTERIA2 ====================
def load_existing_hysteria2():
    configs = []
    seen = set()
    if not os.path.exists(HYST_FOLDER):
        return configs

    for file in sorted(os.listdir(HYST_FOLDER)):
        if not file.endswith(".txt"):
            continue
        try:
            with open(f"{HYST_FOLDER}/{file}", "r", encoding="utf-8") as f:
                content = decode_base64_if_needed(f.read())
                for line in content.splitlines():
                    if "hysteria2://" in line.lower() or "hy2://" in line.lower():
                        fp = get_fingerprint(line)
                        if fp not in seen:
                            seen.add(fp)
                            configs.append(line)
        except:
            pass
    return configs

# ==================== СКАЧИВАНИЕ ====================
def fetch_one_url(url):
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            return url, decode_base64_if_needed(r.text)
        except:
            time.sleep(2 ** attempt)
    return url, None

# ==================== ГЛАВНЫЙ ЗАПУСК ====================
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [clean_url(line) for line in f if clean_url(line) and not clean_url(line).startswith("#")]

logger.info(f"Найдено {len(urls)} ссылок. Начинаем скачивание...")

merged = []
seen = set()

with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    futures = {executor.submit(fetch_one_url, url): url for url in urls}

    for future in as_completed(futures):
        url, content = future.result()
        if not content:
            continue

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
            logger.info(f"+ {added} конфигов из {url[:70]}")

print(f"\nВсего уникальных конфигов: {len(merged)}")

# ==================== HYSTERIA2 ====================
old_hy = load_existing_hysteria2()
new_hy = [x for x in merged if get_proxy_type(x) == "hysteria2"]

all_hysteria2 = old_hy + [
    x for x in new_hy
    if get_fingerprint(x) not in {get_fingerprint(y) for y in old_hy}
]

# ==================== СОХРАНЕНИЕ ====================
def save_chunks(links, folder, prefix):
    if not links:
        return
    os.makedirs(folder, exist_ok=True)

    part = 1
    for i in range(0, len(links), MAX_LINKS_PER_FILE):
        chunk = links[i:i + MAX_LINKS_PER_FILE]
        filename = f"{folder}/{prefix}_{part}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk) + "\n")
        part += 1

ru_links = [l for l in merged if is_russian_config(l)]
world_links = [l for l in merged if not is_russian_config(l)]

save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")
save_chunks(all_hysteria2, HYST_FOLDER, "hysteria2")

for t in types:
    if t == "hysteria2":
        continue
    links = [l for l in merged if get_proxy_type(l) == t]
    save_chunks(links, f"{TYPE_FOLDER}/{t}", t)

with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

logger.info("🎉 Сборка завершена!")
print("🎉 Готово!")