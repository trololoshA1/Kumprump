import os
import json
import time
import tempfile
import subprocess
import httpx
import asyncio
from pathlib import Path

# ==================== НАСТРОЙКИ ====================
SUBS_FOLDER = "subs/type/hysteria2"
TESTED_FOLDER = "tested"

TEST_TIMEOUT = 8
SING_BOX_PORT = 1080
MAX_PARALLEL = 25

# ==================== ПАПКИ ====================
os.makedirs(TESTED_FOLDER, exist_ok=True)

# ==================== ЧИТАЕМ ВСЕ HYSTERIA2 ФАЙЛЫ ====================
def load_all_hysteria_links():
    links = []
    folder = Path(SUBS_FOLDER)
    
    if not folder.exists():
        print(f"❌ Папка {SUBS_FOLDER} не найдена!")
        return []
    
    for file in folder.glob("*.txt"):
        print(f"📂 Читаем файл: {file.name}")
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and (line.lower().startswith("hysteria2://") or line.lower().startswith("hy2://")):
                    links.append(line)
    
    return list(dict.fromkeys(links))  # убираем дубликаты

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
        proc = subprocess.Popen(
            ["sing-box", "-c", config_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        await asyncio.sleep(1.5)

        proxy_url = f"socks5://127.0.0.1:{SING_BOX_PORT}"
        
        async with httpx.AsyncClient(proxy=proxy_url, timeout=TEST_TIMEOUT) as client:
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
            print(f"⏳ Проверка: {link[:60]}...")
            if await test_proxy(link):
                print(f"✅ РАБОЧИЙ")
                good.append(link)
            else:
                print(f"❌ Мёртвый")
                bad.append(link)

    await asyncio.gather(*[worker(link) for link in links])
    return good, bad

# ==================== ЗАПУСК ====================
print("🚀 Начинаем тестирование Hysteria2 из папки subs/type/hysteria2...")

all_links = load_all_hysteria_links()
print(f"Найдено Hysteria2 ссылок: {len(all_links)}")

if not all_links:
    print("❌ Нет ссылок для теста!")
else:
    good, bad = asyncio.run(test_all(all_links))

    print(f"\n🎉 Готово!")
    print(f"Рабочих: {len(good)}")
    print(f"Мёртвых: {len(bad)}")

    # Сохраняем результаты
    with open(f"{TESTED_FOLDER}/good_hysteria2.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(good) + "\n" if good else "")

    with open(f"{TESTED_FOLDER}/bad_hysteria2.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(bad) + "\n" if bad else "")

    print("✅ Результаты сохранены в папку tested/")