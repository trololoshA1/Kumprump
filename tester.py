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
MAX_PARALLEL = 30  # количество одновременных тестов

# ==================== ПАПКИ ====================
types = ["trojan", "hysteria2"]

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
    if l.startswith("trojan://"): return "trojan"
    return None  # остальные игнорируем

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
                            "type": "trojan" if proxy_link.startswith("trojan://") else "hysteria2",
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

    proxy_url = f"socks5://127.0.0.1:{SING_BOX_PORT}"
    transport = httpx.AsyncHTTPTransport(proxy=proxy_url)

    try:
        async with httpx.AsyncClient(
            transport=transport,
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

# ==================== ПАРАЛЛЕЛЬНОЕ ТЕСТИРОВАНИЕ ====================
async def worker(link, sem, good, bad):
    async with sem:
        print(f"⏳ Тест: {link[:60]}...")
        ok = await test_proxy(link)
        if ok:
            print(f"✔ Рабочий")
            good.append(link)
        else:
            print(f"✖ Не работает")
            bad.append(link)

async def test_all(links):
    good = []
    bad = []
    sem = asyncio.Semaphore(MAX_PARALLEL)

    tasks = [worker(link, sem, good, bad) for link in links]
    await asyncio.gather(*tasks)

    return good, bad

# ==================== СОХРАНЕНИЕ ====================
def save_tested(links):
    for link in links:
        t = get_proxy_type(link)
        if not t:
            continue

        if is_russian_config(link):
            folder = RU_FOLDER
        else:
            folder = WORLD_FOLDER

        type_folder = f"{TYPE_FOLDER}/{t}"

        with open(f"{folder}/tested.txt", "a", encoding="utf-8") as f:
            f.write(link + "\n")

        with open(f"{type_folder}/tested.txt", "a", encoding="utf-8") as f:
            f.write(link + "\n")

# ==================== ЗАПУСК ====================
print("📌 Загружаем merged_subs.txt...")

with open(MERGED_FILE, "r", encoding="utf-8") as f:
    all_links = [l.strip() for l in f if l.strip()]

# фильтруем только trojan + hysteria2
links = [l for l in all_links if get_proxy_type(l) in ("trojan", "hysteria2")]

print(f"Всего конфигов для теста: {len(links)}")

good, bad = asyncio.run(test_all(links))

print(f"\n✔ Рабочих: {len(good)}")
print(f"✖ Нерабочих: {len(bad)}")

save_tested(good)

print("\n🎉 Тестирование завершено! Рабочие конфиги сохранены в папку tested/")