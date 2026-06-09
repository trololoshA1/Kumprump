import os
import json
import time
import tempfile
import subprocess
import httpx
import asyncio
import uvloop
from pathlib import Path
from urllib.parse import urlparse, parse_qs

# Ускоряем asyncio
asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

SUBS_FOLDER = "subs/type/hysteria2"
TESTED_FOLDER = "tested"

TEST_TIMEOUT = 3
MAX_PARALLEL = 100

os.makedirs(TESTED_FOLDER, exist_ok=True)

def parse_hy2(link):
    if link.startswith("hysteria2://"):
        link = link.replace("hysteria2://", "hy2://")

    u = urlparse(link)
    params = parse_qs(u.query)

    return {
        "server": f"{u.hostname}:{u.port}",
        "password": u.username,
        "obfs": params.get("obfs", [""])[0],
        "sni": params.get("sni", [""])[0] or u.hostname
    }

async def test_proxy(link, port):
    cfg = parse_hy2(link)

    config = {
        "log": {"disabled": True},
        "inbounds": [{
            "type": "socks",
            "listen": "127.0.0.1",
            "listen_port": port
        }],
        "outbounds": [{
            "type": "hysteria2",
            "server": cfg["server"],
            "password": cfg["password"],
            "obfs": cfg["obfs"],
            "tls": {"enabled": True, "server_name": cfg["sni"]}
        }]
    }

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(json.dumps(config))
        path = f.name

    proc = subprocess.Popen(["sing-box", "-c", path])
    await asyncio.sleep(0.5)

    try:
        async with httpx.AsyncClient(
            proxy=f"socks5://127.0.0.1:{port}",
            timeout=TEST_TIMEOUT
        ) as c:
            r = await c.get("https://api.ipify.org")
            return r.status_code == 200
    except:
        return False
    finally:
        proc.kill()
        os.remove(path)

async def test_all(links):
    good, bad = [], []
    sem = asyncio.Semaphore(MAX_PARALLEL)

    async def worker(i, link):
        port = 20000 + i
        async with sem:
            print(f"⏳ {link[:60]}...")
            if await test_proxy(link, port):
                print("✅ OK")
                good.append(link)
            else:
                print("❌ DEAD")
                bad.append(link)

    await asyncio.gather(*[worker(i, link) for i, link in enumerate(links)])
    return good, bad

def load_all():
    links = []
    for file in Path(SUBS_FOLDER).glob("*.txt"):
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(("hysteria2://", "hy2://")):
                    links.append(line)
    return list(dict.fromkeys(links))

print("🚀 Загружаем ссылки...")
links = load_all()
print(f"Найдено: {len(links)}")

good, bad = asyncio.run(test_all(links))

print(f"\nРабочих: {len(good)}")
print(f"Мёртвых: {len(bad)}")

with open(f"{TESTED_FOLDER}/good_hysteria2.txt", "w") as f:
    f.write("\n".join(good))

with open(f"{TESTED_FOLDER}/bad_hysteria2.txt", "w") as f:
    f.write("\n".join(bad))

print("Готово!")