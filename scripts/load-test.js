import http from "k6/http";
import { check, sleep, group } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 20 },   // 预热：20 VU 起步，让连接池/缓存先热起来
    { duration: "90s", target: 50 },   // 主压测：50 个虚拟用户（VU）持续 90 秒
    { duration: "30s", target: 0 },    // 收尾：逐步降到 0，观察缩容
  ],
  thresholds: {
    http_req_duration: ["p(95)<500"],
    http_req_failed: ["rate<0.01"],
  },
};

const BASE = __ENV.BASE_URL || "http://cloudforge.local";

export default function () {
  group("list tasks", () => {
    const resp = http.get(`${BASE}/tasks`);
    check(resp, { "status 200": (r) => r.status === 200 });
  });

  group("create task", () => {
    const payload = JSON.stringify({
      title: `task-${Date.now()}-${__VU}-${__ITER}`,
    });
    const params = { headers: { "Content-Type": "application/json" } };
    const resp = http.post(`${BASE}/tasks`, payload, params);
    check(resp, { "status 201": (r) => r.status === 201 });
  });

  sleep(1);
}
