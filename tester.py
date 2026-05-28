import os
import re
import json
import time
import shutil
import hashlib
import tempfile
import subprocess
import httpx
import asyncio

# ==================== НАСТРОЙКИ ====================
MERGED_FILE = "merged_subs.txt"

TESTED_FOLDER = "tested"
RU_FOLDER = f"{TESTED_FOLDER}/ru"
WORLD_FOLDER = f"{TESTED_FOLDER}/world"
TYPE_FOLDER = f"{TESTED_FOLDER}/type"

TEST_SITES = [
    "https://api.ipify.org",
    "https://www.google.com",
    "https://www.youtube.com",
    "https://cloudflare.com/cdn-cgi/trace",
    "https://check-host.net/ip"
]

TEST_TIMEOUT = 7
SING_BOX_PORT = 1080

# ==================== ПАПКИ ====================
types = ["vless", "vmess", "trojan", "hysteria2", "shadowsocks", "tuic", "other"]

for folder in [TESTED_FOLDER, RU_FOLDER, WORLD_FOLDER, TYPE_FOLDER]:
    os.makedirs(folder, exist_ok=True)

for t in types:
    os.makedirs(f"{TYPE_FOLDER}/{t}", exist_ok=True)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
RU_PATTERN = re.compile(r"(ru[-_]|🇷🇺|russia|moscow|moskva|spb|piter)", re.I)

def is_russian_config(link):
    return bool(RU_PATTERN.search(link))

def get_proxy_type(link):
    l = link.lower()
    if l.startswith(("hysteria2://", "hy2://")): return "hysteria2"
    if l.startswith("vless://"): return "vless"
    if l.startswith("vmess://"): return "vmess"
    if l.startswith("trojan://"): return "trojan"
    if l.startswith("ss://"): return "shadowsocks"
    if l.startswith("tuic://"): return "tuic"
    return "other"

def get_fingerprint(link):
    return hashlib.sha256(link.strip().encode()).hexdigest()

# ==================== ТЕСТ ПРОКСИ ====================
async def test_proxy(proxy_link):
    """
    Проверяет один прокси через sing-box.
    Если хотя бы один сайт открылся — прокси рабочий.
    """

    # Создаём временный конфиг sing-box
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as cfg:
        config_path = cfg.name

        config = {
            "log": {"disabled": True},
            "inbounds": [
                {
                    "type": "socks",
                    "listen": "127.0.0.1",
                    "listen_port": SING_BOX_PORT
                }
            ],
            "outbounds": [
                {
                    "type": "selector",
                    "outbounds": [
                        {
                            "type": "vless",
                            "server": proxy_link
                        }
                    ]
                }
            ]
        }

        cfg.write(json.dumps(config))

    # Запускаем sing-box
    proc = subprocess.Popen(
        ["sing-box", "-c", config_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

    await asyncio.sleep(1.2)  # ждём запуска

    try:
        async with httpx.AsyncClient(
            proxies=f"socks5://127.0.0.1:{SING_BOX_PORT}",
            timeout=TEST_TIMEOUT
        ) as client:

            for site in TEST_SITES:
                try:
                    r = await client.get(site)
                    if r.status_code == 200:
                        return True
                except:
                    continue

        return False

    finally:
        proc.kill()
        os.remove(config_path)

# ==================== ТЕСТ ВСЕХ ПРОКСИ ====================
async def test_all(links):
    good = []
    bad = []

    for link in links:
        print(f"⏳ Тест: {link[:60]}...")
        ok = await test_proxy(link)

        if ok:
            print(f"✔ Рабочий")
            good.append(link)
        else:
            print(f"✖ Не работает")
            bad.append(link)

    return good, bad

# ==================== СОХРАНЕНИЕ ====================
def save_tested(links):
    for link in links:
        if is_russian_config(link):
            folder = RU_FOLDER
        else:
            folder = WORLD_FOLDER

        t = get_proxy_type(link)
        type_folder = f"{TYPE_FOLDER}/{t}"

        # Сохраняем в регион
        with open(f"{folder}/tested.txt", "a", encoding="utf-8") as f:
            f.write(link + "\n")

        # Сохраняем по типу
        with open(f"{type_folder}/tested.txt", "a", encoding="utf-8") as f:
            f.write(link + "\n")

# ==================== ЗАПУСК ====================
print("📌 Загружаем merged_subs.txt...")

with open(MERGED_FILE, "r", encoding="utf-8") as f:
    links = [l.strip() for l in f if l.strip()]

print(f"Всего конфигов для теста: {len(links)}")

good, bad = asyncio.run(test_all(links))

print(f"\n✔ Рабочих: {len(good)}")
print(f"✖ Нерабочих: {len(bad)}")

save_tested(good)

print("\n🎉 Тестирование завершено! Рабочие конфиги сохранены в папку tested/")