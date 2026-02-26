"""Health check helper for start_all.bat — polls a URL until it responds."""
import sys
import time
from urllib.request import urlopen

url = sys.argv[1]
timeout = int(sys.argv[2]) if len(sys.argv) > 2 else 60

start = time.time()
while time.time() - start < timeout:
    try:
        urlopen(url, timeout=2)
        sys.exit(0)
    except Exception:
        time.sleep(2)

sys.exit(1)
