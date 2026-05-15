import requests
import time
import base64
import os
import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000

RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

# ==================== ДЕДУПЛИКАЦИЯ ====================
def get_proxy_fingerprint(link: str) -> str:
    """Создаёт уникальный ключ для прокси (чтобы убирать дубли)"""
    link = link.strip()
    try:
        if link.startswith("vmess://"):
            return link  # vmess обычно уникальные
        parsed = urlparse(link)
        scheme = parsed.scheme
        netloc = parsed.netloc or parsed.path.split('/')[0]
        
        # Добавляем UUID / password + сервер
        if '@' in link:
            auth = link.split('@')[0].split('://')[-1]
        else:
            auth = parsed.username or parsed.path.split('/')[0]
            
        key = f"{scheme}://{auth}@{netloc}"
        return key.lower()
    except:
        return link.lower()  # fallback


# ==================== ОПРЕДЕЛЕНИЕ ТИПА ====================
def get_proxy_type(link: str) -> str:
    lower = link.lower()
    if lower.startswith("vless://"):
        return "vless"
    elif lower.startswith("vmess://"):
        return "vmess"
    elif lower.startswith("trojan://"):
        return "trojan"
    elif lower.startswith(("hysteria2://", "hy2://")):
        return "hysteria2"
    elif lower.startswith("ss://"):
        return "shadowsocks"
    elif lower.startswith("tuic://"):
        return "tuic"
    else:
        return "other"


# ==================== RU ОПРЕДЕЛЕНИЕ (оставляем как было) ====================
RU_IP_PREFIXES = [ ... ]  # твои префиксы
RU_KEYWORDS = [ ... ]     # твои ключевые слова

def is_russian_config(link: str) -> bool:
    # ... (оставь твой текущий код без изменений)
    lower = link.lower()
    ip = extract_ip(link)
    if ip and any(ip.startswith(p) for p in RU_IP_PREFIXES):
        return True
    if any(kw.lower() in lower for kw in RU_KEYWORDS):
        return True
    if re.search(r'RU-\d{4,5}', link):
        return True
    return False


# ======================= ОСНОВНОЙ КОД =======================
print(f"[{datetime.now()}] Запуск с дедупликацией и разделением по типам...")

# Очистка
for folder in [RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    if os.path.exists(folder):
        for root, dirs, files in os.walk(folder, topdown=False):
            for name in files:
                os.remove(os.path.join(root, name))
            for name in dirs:
                os.rmdir(os.path.join(root, name))

os.makedirs(RU_FOLDER, exist_ok=True)
os.makedirs(WORLD_FOLDER, exist_ok=True)
os.makedirs(TYPE_FOLDER, exist_ok=True)

# Создаём папки под типы
type_folders = {}
for t in ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]:
    path = f"{TYPE_FOLDER}/{t}"
    os.makedirs(path, exist_ok=True)
    type_folders[t] = path

# Сбор всех ссылок
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = []
seen = set()

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] Скачиваю: {url[:60]}...")
    for _ in range(3):
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text

            # Декодирование base64 если нужно
            if "://" not in content[:300] and len(content) > 500:
                try:
                    content = base64.b64decode(content + "===").decode("utf-8", errors="ignore")
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
            time.sleep(2)
    time.sleep(1.2)

print(f"После дедупликации: {len(merged)} уникальных конфигов")

# Разделение
ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

# Разделение по типам
type_links = {t: [] for t in type_folders.keys()}
for link in merged:
    t = get_proxy_type(link)
    type_links[t].append(link)

print(f"RU: {len(ru_links)} | World: {len(world_links)}")
for t, lst in type_links.items():
    print(f"  {t}: {len(lst)}")

# Функция сохранения чанков
def save_chunks(links, base_path, prefix, make_base64=False):
    for i in range(0, len(links), MAX_LINKS_PER_FILE):
        chunk = links[i:i + MAX_LINKS_PER_FILE]
        part = (i // MAX_LINKS_PER_FILE) + 1
        filename = f"{base_path}/{prefix}_{part}.txt"
        
        if make_base64:
            content = "\n".join(chunk)
            b64 = base64.b64encode(content.encode("utf-8")).decode("utf-8")
            with open(filename, "w", encoding="utf-8") as f:
                f.write(b64)
        else:
            with open(filename, "w", encoding="utf-8") as f:
                f.writelines(link + "\n" for link in chunk)

# Сохраняем всё
save_chunks(ru_links, RU_FOLDER, "ru_part")
save_chunks(world_links, WORLD_FOLDER, "world_part")

for t, links in type_links.items():
    save_chunks(links, type_folders[t], f"{t}_part")
    save_chunks(links, type_folders[t], f"{t}_base64", make_base64=True)

print("\n✅ Готово! Добавлено разделение по типам + дедупликация.")