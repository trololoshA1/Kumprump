import requests
import time
import base64
import os
import re
import shutil
from datetime import datetime
from urllib.parse import urlparse

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000
MAX_HYSTERIA2_SIZE_MB = 90

RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

print(f"[{datetime.now()}] 🚀 Запуск | Hysteria2 — накопление, остальные — свежие + автоочистка")

# Создание папок
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]
for t in types:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# ==================== ОЧИСТКА ПАПОК (кроме hysteria2) ====================
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
        except Exception as e:
            print(f"Не удалось удалить {item_path}: {e}")

# Очищаем все кроме Hysteria2
print("🧹 Очистка папок (кроме hysteria2)...")
clear_folder(RU_FOLDER)
clear_folder(WORLD_FOLDER)

for t in types:
    if t != "hysteria2":
        clear_folder(f"{TYPE_FOLDER}/{t}")

# ==================== ДЕДУПЛИКАЦИЯ ====================
def get_fingerprint(link: str) -> str:
    link = link.strip()
    try:
        if "hysteria2://" in link or "hy2://" in link:
            parsed = urlparse(link)
            hostname = parsed.hostname or ""
            port = parsed.port or ""
            auth = parsed.username or parsed.path.split("?")[0].split("/")[0]
            return f"hy2:{auth}@{hostname}:{port}"
        else:
            return link[:150]
    except:
        return link[:150]

def decode_base64_if_needed(content: str) -> str:
    content = content.strip()
    if "://" in content[:300]:
        return content
    for padding in ["", "==", "=", "==="]:
        try:
            decoded = base64.b64decode(content + padding).decode("utf-8", errors="ignore")
            if "://" in decoded[:400]:
                return decoded
        except:
            continue
    try:
        decoded = base64.urlsafe_b64decode(content + "==").decode("utf-8", errors="ignore")
        if "://" in decoded[:400]:
            return decoded
    except:
        pass
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

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
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
    if lower.startswith(("hysteria2://", "hy2://")): return "hysteria2"
    if lower.startswith("vless://"): return "vless"
    if lower.startswith("vmess://"): return "vmess"
    if lower.startswith("trojan://"): return "trojan"
    if lower.startswith("ss://"): return "shadowsocks"
    if lower.startswith("tuic://"): return "tuic"
    return "other"

def is_russian_config(link: str) -> bool:
    lower = link.lower()
    keywords = ["ru-", "🇷🇺", "russia", "moscow", "spb", "yandex", "vk.com", "ozon"]
    return any(k in lower for k in keywords)

# ===================== ЗАПУСК =====================
with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
    urls = [clean_url(line) for line in f if clean_url(line) and not clean_url(line).startswith("#")]

print(f"Найдено {len(urls)} ссылок на подписки\n")

merged = []
seen = set()

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] ↓ {url[:70]}...")
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=25, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = decode_base64_if_needed(r.text)

            added = 0
            for line in content.splitlines():
                line = line.strip()
                if is_proxy_link(line):
                    fp = get_fingerprint(line)
                    if fp not in seen:
                        seen.add(fp)
                        merged.append(line)
                        added += 1
            print(f"   + {added} новых")
            break
        except Exception as e:
            print(f"   Ошибка {attempt+1}/3: {e}")
            time.sleep(2)
    time.sleep(1.3)

print(f"\nВсего уникальных конфигов за этот запуск: {len(merged)}")

# ===================== Hysteria2 — накопление =====================
old_hy = load_existing_hysteria2()
new_hy = [link for link in merged if get_proxy_type(link) == "hysteria2" and get_fingerprint(link) not in [get_fingerprint(x) for x in old_hy]]
all_hysteria2 = old_hy + new_hy

print(f"Hysteria2: {len(all_hysteria2)} всего (+{len(new_hy)} новых)")

# ===================== Сохранение =====================
def save_chunks(links, folder, prefix, max_per_file=MAX_LINKS_PER_FILE, max_size_mb=None):
    if not links:
        return
    current = []
    part = 1
    for link in links:
        current.append(link)
        size_mb = len("\n".join(current).encode('utf-8')) / (1024*1024)
        
        if (max_size_mb and size_mb > max_size_mb) or len(current) >= max_per_file:
            filename = f"{folder}/{prefix}_{part}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write("\n".join(current) + "\n")
            print(f"   → {filename} ({size_mb:.1f} MB)")
            current = []
            part += 1

    if current:
        filename = f"{folder}/{prefix}_{part}.txt"
        size_mb = len("\n".join(current).encode('utf-8')) / (1024*1024)
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(current) + "\n")
        print(f"   → {filename} ({size_mb:.1f} MB)")

# Сохранение
ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")
save_chunks(all_hysteria2, f"{TYPE_FOLDER}/hysteria2", "hysteria2", max_size_mb=MAX_HYSTERIA2_SIZE_MB)

# Остальные протоколы — только свежие
for t in types:
    if t == "hysteria2":
        continue
    links = [link for link in merged if get_proxy_type(link) == t]
    if links:
        print(f"{t.upper()}: {len(links)} свежих")
        save_chunks(links, f"{TYPE_FOLDER}/{t}", t)

# Общий merged
with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print("\n🎉 ГОТОВО! Все папки кроме hysteria2 очищаются автоматически.")