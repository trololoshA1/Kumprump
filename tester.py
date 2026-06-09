import os
import re
import json
import time
import tempfile
import subprocess
import httpx
import asyncio

# ==================== НАСТРОЙКИ ====================
MERGED_FILE = "merged_subs.txt"
TESTED_FOLDER = "tested"

# Только Hysteria2!
TEST_TIMEOUT = 8
SING_BOX_PORT = 1080
MAX_PARALLEL = 25   # уменьшил, чтобы было стабильнее и быстрее

# ==================== ПАПКИ ====================
os.makedirs(TESTED_FOLDER, exist_ok=True)

# ==================== ВСПОМОГАТЕЛЬНЫЕ ====================
def get_fingerprint(link):
    return link.strip()

# ==================== ТЕСТ ОДНОГО PROXY ====================
async def test_proxy(proxy_link):
    config = {
        "log": {"disabled": True},
        "inbounds": [{"type": "socks", "listen": "127.0.0.1", "listen_port": SING_BOX_PORT}],
        "outbounds": [{
            "type": "hysteria2",
            "server": proxy_link
        }]
    }

    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as cfg:
        config_path = cfg.name
        cfg.write(json.dumps(config))

    try:
        # Запускаем sing-box
        proc = subprocess.Popen(
            ["sing-box", "-c", config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        await asyncio.sleep(1.5)  # даём время запуститься

        proxy_url = f"socks5://127.0.0.1:{SING_BOX_PORT}"
        
        async with httpx.AsyncClient(
            proxy=proxy_url, 
            timeout=TEST_TIMEOUT
        ) as client:
            
            # Быстрые тесты
            for site in ["https://api.ipify.org", "https://cloudflare.com/cdn-cgi/trace"]:
                try:
                    r = await client.get(site)
                    if r.status_code == 200:
                        return True
                except:
                    continue
        return False

    finally:
        proc.kill()
        try:
            os.remove(config_path)
        except:
            pass

# ==================== МАССОВЫЙ ТЕСТ ====================
async def test_all(links):
    good = []
    bad = []
    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def worker(link):
        async with sem:
            print(f"⏳ Проверка: {link[:50]}...")
            if await test_proxy(link):
                print(f"✅ РАБОЧИЙ")
                good.append(link)
            else:
                print(f"❌ Мёртвый")
                bad.append(link)

    await asyncio.gather(*[worker(link) for link in links])
    return good, bad

# ==================== ЗАПУСК ====================
print("🚀 Начинаем тестирование Hysteria2...")

with open(MERGED_FILE, "r", encoding="utf-8") as f:
    all_links = [l.strip() for l in f if l.strip()]

# Фильтруем ТОЛЬКО hysteria2
hysteria_links = [l for l in all_links if l.lower().startswith(("