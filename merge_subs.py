import requests
import time
import base64
import os
import re
from datetime import datetime

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000
MAX_HYSTERIA2_SIZE_MB = 90

RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

print(f"[{datetime.now()}] 🚀 Запуск | Полная очистка Hysteria2 + накопление")

# Создание папок
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]
for t in types:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# ==================== ДЕКОДИРОВАНИЕ BASE64 ====================
def decode_base64_if_needed(content: str) -> str:
    content = content.strip()
    if "://" in content[:300]:
        return content

    for padding in ["", "==", "=", "==="]:
        try:
            decoded = base64.b64decode(content + padding).decode("utf-8", errors="ignore")
            if "hysteria2://" in decoded.lower() or "hy2://" in decoded.lower():
                return decoded
        except:
            continue
    try:
        decoded = base64.urlsafe_b64decode(content + "==").decode("utf-8", errors="ignore")
        if "hysteria2://" in decoded.lower() or "hy2://" in decoded.lower():
            return decoded
    except:
        pass
    return content

# ==================== ПОЛНАЯ ОЧИСТКА ПАПКИ HYSTERIA2 ====================
def cleanup_hysteria2_folder():
    folder = f"{TYPE_FOLDER}/hysteria2"
    if not os.path.exists(folder):
        return
    deleted = 0
    for file in list(os.listdir(folder)):
        try:
            os.remove(os.path.join(folder, file))
            deleted += 1
        except:
            pass
    print(f"🗑 Удалено {deleted} старых файлов в hysteria2/")

# ==================== ЗАГРУЗКА СТАРЫХ HYSTERIA2 ====================
def load_existing_hysteria2():
    folder = f"{TYPE_FOLDER}/hysteria2"
    configs = []
    if not os.path.exists(folder):
        return configs
    for file in os.listdir(folder):
        if not file.endswith(".txt"):
            continue
        try:
            with open(f"{folder}/{file}", "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                decoded = decode_base64_if_needed(content)
                for line in decoded.splitlines():
                    line = line.strip()
                    if line and ("hysteria2://" in line.lower() or "hy2://" in line.lower()):
                        configs.append(line)
        except:
            continue
    return configs

# ==================== ОСНОВНЫЕ ФУНКЦИИ ====================
def clean_url(url: str) -> str:
    url = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', url.strip())
    return url.strip('"\' \t\n')

def is_proxy_link(line: str) -> bool:
    if not line or line.startswith('#'): return False
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
cleanup_hysteria2_folder()   # Полная очистка перед работой

with open(INPUT_FILE, "r", encoding="utf-8", errors="ignore") as f:
    urls = [clean_url(line) for line in f if clean_url(line) and not clean_url(line).startswith("#")]

print(f"Найдено {len(urls)} ссылок\n")

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
                    fp = line[:120]
                    if fp not in seen:
                        seen.add(fp)
                        merged.append(line)
                        added += 1
            print(f"   + {added} конфигов")
            break
        except Exception as e:
            print(f"   Ошибка {attempt+1}/3: {e}")
            time.sleep(2)
    time.sleep(1.3)

print(f"\nВсего новых уникальных: {len(merged)}")

# ===================== Hysteria2 накопление =====================
old_hy = load_existing_hysteria2()
new_hy = [link for link in merged if get_proxy_type(link) == "hysteria2" and link not in old_hy]
all_hysteria2 = old_hy + new_hy

print(f"Hysteria2 всего после накопления: {len(all_hysteria2)} (+{len(new_hy)})")

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

for t in types:
    if t == "hysteria2": continue
    links = [link for link in merged if get_proxy_type(link) == t]
    save_chunks(links, f"{TYPE_FOLDER}/{t}", t)

with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print("\n🎉 ГОТОВО! Hysteria2 полностью очищен и обновлён в нормальном формате.")