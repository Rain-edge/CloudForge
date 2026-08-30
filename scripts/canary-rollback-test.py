"""金丝雀秒级回滚计时实验：weight=100 -> 0，测量 nginx 摘流生效时间。
连续请求期间执行 helm upgrade --set canary.weight=0，
从 nginx 访问日志提取 canary upstream 的最后一条时间戳，对比 upgrade 完成时刻。
"""
import os
import subprocess
import threading
import time
import urllib.request

PORT = os.environ.get("NGINX_PORT", "18080")   # Windows 上 8080 常被系统保留，默认用 18080；可 NGINX_PORT=8080 覆盖
STOP = threading.Event()
REQS = []  # (t, status)

def requester():
    while not STOP.is_set():
        t0 = time.time()
        req = urllib.request.Request(f"http://localhost:{PORT}/tasks", headers={"Host": "cloudforge.local"})
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                r.read()
            REQS.append((t0, r.status))
        except Exception as e:
            REQS.append((t0, f"ERR:{e}"))
        time.sleep(0.15)

t = threading.Thread(target=requester, daemon=True)
t.start()
time.sleep(2)

t_up_start = time.time()
r = subprocess.run(
    ["helm", "upgrade", "cloudforge", "./chart",
     "--set", "autoscaling.enabled=true",
     "--set", "observability.serviceMonitor.enabled=true",
     "--set", "observability.prometheusRule.enabled=true",
     "--set", "grafanaDashboard.enabled=true",
     "--set", "ingress.enabled=true",
     "--set", "ingress.host=cloudforge.local",
     "--set", "canary.enabled=true",
     "--set", "canary.weight=0",
     "--set", "canary.tag=v2"],
    capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
t_up_end = time.time()

print(f"helm upgrade 发出: {t_up_start:.2f}  完成: {t_up_end:.2f}  ({t_up_end-t_up_start:.1f}s)")
print("upgrade 输出:", r.stdout.strip().splitlines()[-1] if r.stdout else r.stderr.strip().splitlines()[-1])

time.sleep(8)
STOP.set()
t.join(timeout=5)

ok = sum(1 for _, s in REQS if s == 200)
print(f"请求总数: {len(REQS)}, 200 响应: {ok}")
with open("docs/experiments/2026-08-28-k6-hpa/canary-rollback-reqs.json", "w") as f:
    import json
    json.dump({"upgrade_start": t_up_start, "upgrade_end": t_up_end, "reqs": REQS}, f)
print("已保存 canary-rollback-reqs.json")
