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

# ------------------ АВТООПРЕДЕЛЕНИЕ ТИПА ------------------
def detect_type(params):
    if "obfs-password" in params:
        return "hysteria1"
    if params.get("obfs", [""])[0] == "salamander":
        return "hysteria1"
    if params.get("security", [""])[0] == "tls":
        return "hysteria1"
    return "hysteria2"


# ------------------ ПАРСИНГ ------------------
def parse_link(link):
    if link.startswith("hysteria2://"):
        link = link.replace("hysteria2://", "hy2://")

    u = urlparse(link)
    params = parse_qs(u.query)

    port = u.port or 443
    server = f"{u.hostname}:{port}"
    password = u.username or ""

    obfs = params.get("obfs", [""])[0]
    obfs_pw = params.get("obfs-password", [""])[0]
    sni = params.get("sni", [""])[0] or u.hostname

    link_type = detect_type(params)

    return {
        "type": link_type,
        "server": server,
        "password": password,
        "obfs": obfs,
        "obfs_pw": obfs_pw,
        "sni": sni
    }


# ------------------ ТЕСТ ОДНОГО ПРОКСИ ------------------
async def test_proxy(link, port):
    try:
        cfg = parse_link(link)
    except Exception as e:
        return False, f"parse_error: {e}"

    # ---------- HYSTERIA1 ----------
    if cfg["type"] == "hysteria1":
        outbound = {
            "type": "hysteria",
            "server": cfg["server"],
            "auth": {
                "type": "string",
                "password": cfg["password"]
            },
            "tls": {
                "enabled": True,
                "server_name": cfg["sni"],
                "insecure": True
            },
            "obfs": {
                "type": "salamander",
                "password": cfg["obfs_pw"]
            }
        }

    # ---------- HYSTERIA2 ----------
    else:
        outbound = {
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
        }
        if cfg["obfs"]:
            outbound["obfs"] = cfg["obfs"]

    config = {
        "log": {"level": "error"},
        "inbounds": [{
            "type": "socks",
            "listen": "127.0.0.1",
            "listen_port": port
        }],
        "outbounds": [outbound]
    }

    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write(json.dumps(config))
        path = f.name

    proc = subprocess.Popen(
        ["sing-box", "-c", path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    await asyncio.sleep(1.0)

    err = proc.stderr.read()
    if err.strip():
        return False, f"singbox_error: {err}"

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


# ------------------ ПОТОК ------------------
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


# ------------------ МАССОВЫЙ ТЕСТ ------------------
async def test_all(links):
    good, bad, errors = [], [], []
    sem = asyncio.Semaphore(MAX_PARALLEL)

    await asyncio.gather(*[
        worker(i, link, good, bad, errors, sem)
        for i, link in enumerate(links)
    ])

    return good, bad, errors


# ------------------ ЗАГРУЗКА ------------------
def load_all():
    links = []
    for file in Path(SUBS_FOLDER).glob("*.txt"):
        with open(file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(("hysteria2://", "hy2://", "hysteria://")):
                    links.append(line)
    return list(dict.fromkeys(links))


# ------------------ ЗАПУСК ------------------
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