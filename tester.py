import os
import json
import tempfile
import subprocess
import httpx
import asyncio
import uvloop
from pathlib import Path
from urllib.parse import urlparse, parse_qs

asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

SUBS_FOLDER = "subs/type/hysteria2"
TESTED_FOLDER = "tested"

TEST_TIMEOUT = 4
MAX_PARALLEL = 40

os.makedirs(TESTED_FOLDER, exist_ok=True)

def parse_hy2(link):
    if link.startswith("hysteria2://"):
        link = link.replace("hysteria2://", "hy2://")

    u = urlparse(link)
    params = parse_qs(u.query)

    port = u.port or 443
    server = f"{u.hostname}:{port}"
    password = u.username or ""

    obfs = params.get("obfs", [""])[0]
    sni = params.get("sni", [""])[0] or u.hostname

    return {
        "server": server,
        "password": password,
        "obfs": obfs,
        "sni": sni
    }

async def test_proxy(link, port):
    try:
        cfg = parse_hy2(link)
    except Exception as e:
        return False, f"parse_error: {e}"

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
            "auth": {"type": "none"},
            "udp": {"enabled": True},
            "tls": {
                "enabled": True,
                "server_name": cfg["sni"],
                "insecure": True
            }
        }]
    }

    if cfg["obfs"]:
        config["outbounds"][0]["obfs"] = cfg["obfs"]

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(json.dumps(config))
        path = f.name

    proc = subprocess.Popen(["sing-box", "-c", path])
    await asyncio.sleep(0.8)

    try:
        async with httpx.AsyncClient(
            proxy=f"socks5://127.0.0.1:{port}",
            timeout=TEST_TIMEOUT
        ) as c:
            r = await c.get("https://api.ipify.org")
            if r.status_code == 200:
                return True, None
            return False, f"bad_status: {r.status_code}"

    except Exception as e:
        return False, f"http_error: {e}"

    finally:
        proc.kill()
        os.remove(path)

async def worker(i, link, good, bad, errors, sem):
    port = 20000 + i
    async with sem:
        print(f"⏳ {link[:60]}...")
        ok, err = await test_proxy(link, port)
        if ok:
            print("✅ Рабочий")
            good.append(link)
        else:
            print("❌ Мёртвый")
            bad.append(link)
            errors.append(f"{link}\n{err}\n\n")

async def test_all(links):
    good, bad, errors = [], [], []
    sem = asyncio.Semaphore(MAX_PARALLEL)

    await asyncio.gather(*[
        worker(i, link, good, bad, errors, sem)
        for i, link in enumerate(links)
    ])

    return good, bad, errors

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

good, bad, errors = asyncio.run(test_all(links))

print(f"\n🎉 Готово!")
print(f"Рабочих: {len(good)}")
print(f"Мёртвых: {len(bad)}")

with open(f"{TESTED_FOLDER}/good_hysteria2.txt", "w") as f:
    f.write("\n".join(good))

with open(f"{TESTED_FOLDER}/bad_hysteria2.txt", "w") as f:
    f.write("\n".join(bad))

with open(f"{TESTED_FOLDER}/errors.txt", "w") as f:
    f.writelines(errors)

print("🔥 Результаты сохранены в tested/")