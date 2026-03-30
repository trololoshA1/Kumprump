import requests
import time
from datetime import datetime

# ?????????
INPUT_FILE = "links.txt"
OUTPUT_FILE = "merged_subs.txt"
TIMEOUT = 15
RETRIES = 3
DELAY = 1  # ??????? ????? ?????????, ????? ?? ??????? ???

def is_proxy_link(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return False
    return any(line.startswith(proto) for proto in [
        "vless://", "vmess://", "trojan://", "ss://", "warp://",
        "hysteria2://", "hy2://", "tuic://"
    ])

print(f"[{datetime.now()}] ?????? ?????? ????????...")

with open(INPUT_FILE, "r", encoding="utf-8") as f:
    urls = [line.strip() for line in f if line.strip() and not line.startswith("#")]

merged = set()
total_found = 0

for i, url in enumerate(urls, 1):
    print(f"[{i}/{len(urls)}] ????????: {url}")
    for attempt in range(RETRIES):
        try:
            r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            content = r.text

            # ???? ???????? ? base64 ? ??????????? (?????? ??? ??????)
            if content.startswith("ey") or len(content) > 1000 and "://" not in content[:200]:
                import base64
                try:
                    content = base64.b64decode(content + "===").decode("utf-8")
                except:
                    pass

            lines = content.splitlines()
            new_links = [line for line in lines if is_proxy_link(line)]
            merged.update(new_links)
            total_found += len(new_links)
            break
        except Exception as e:
            print(f"   ?????? (??????? {attempt+1}): {e}")
            time.sleep(2)

    time.sleep(DELAY)

# ????????? ??????????
with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
    for link in sorted(merged):
        f.write(link + "\n")

print(f"??????! ??????? {len(merged)} ?????????? ???????? (????? ?????????? \~{total_found})")