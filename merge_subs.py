import requests
import time
import base64
import os
import re
from datetime import datetime

INPUT_FILE = "links.txt"
MAX_LINKS_PER_FILE = 4000   # теперь для всех типов, включая hysteria2

RU_FOLDER = "subs/ru"
WORLD_FOLDER = "subs/world"
TYPE_FOLDER = "subs/type"

print(f"[{datetime.now()}] 🚀 Запуск | Декодирование base64 + Hysteria2 без ограничения 100")

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
            if "://" in decoded[:500]:
                print("   ✅ Декодировано из base64")
                return decoded
        except:
            continue

    try:
        decoded = base64.urlsafe_b64decode(content + "==").decode("utf-8", errors="ignore")
        if "://" in decoded[:500]:
            print("   ✅ Декодировано (urlsafe base64)")
            return decoded
    except:
        pass

    return content


def clean_url(url: str) -> str:
    url = re.sub(r'[\u200b\u200c\u200d\u200e\u200f\ufeff]', '', url.strip())
    return url.strip('"\' \t\n')

def is_proxy_link(line: str) -> bool:
    if not line or line.startswith('#'): return False
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
    keywords = ["ru-", "🇷🇺", "russia", "moscow", "spb", "yandex", "vk.com", "ozon"]
    return any(k in lower for k in keywords)

def load_existing_configs(folder, prefix):
    configs = []
    if not os.path.exists(folder):
        return configs
    for file in sorted(os.listdir(folder)):
        if file.startswith(prefix) and file.endswith(".txt"):
            try:
                with open(f"{folder}/{file}", "r", encoding="utf-8") as f:
                    configs.extend([line.strip() for line in f if line.strip()])
            except:
                pass
    return configs

# ===================== Скачивание =====================
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
            content = r.text

            content = decode_base64_if_needed(content)

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
    time.sleep(1.3)

print(f"\nВсего новых уникальных: {len(merged)}")

# ===================== Разделение =====================
ru_links = [link for link in merged if is_russian_config(link)]
world_links = [link for link in merged if not is_russian_config(link)]

type_links = {t: [] for t in types}
for link in merged:
    type_links[get_proxy_type(link)].append(link)

# Hysteria2 накопление
hysteria_existing = load_existing_configs(f"{TYPE_FOLDER}/hysteria2", "hysteria2")
new_hy2 = [link for link in type_links["hysteria2"] if link not in hysteria_existing]
all_hysteria2 = hysteria_existing + new_hy2

print(f"Hysteria2 всего: {len(all_hysteria2)} (+{len(new_hy2)})")

# ===================== Сохранение =====================
def save_chunks(links, folder, prefix, max_per_file=MAX_LINKS_PER_FILE):
    if not links:
        return
    for i in range(0, len(links), max_per_file):
        chunk = links[i:i + max_per_file]
        part = i // max_per_file + 1
        filename = f"{folder}/{prefix}_{part}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write("\n".join(chunk) + "\n")

save_chunks(ru_links, RU_FOLDER, "ru")
save_chunks(world_links, WORLD_FOLDER, "world")
save_chunks(all_hysteria2, f"{TYPE_FOLDER}/hysteria2", "hysteria2")

for t in types:
    if t == "hysteria2":
        continue
    save_chunks(type_links[t], f"{TYPE_FOLDER}/{t}", t)

with open("merged_subs.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(merged))

print("\n🎉 ГОТОВО! Hysteria2 теперь без ограничения в 100, по 4000 на файл.")