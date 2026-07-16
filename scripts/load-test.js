import http from "k6/http";
import { check, sleep, group } from "k6";

export const options = {
  stages: [
    { duration: "30s", target: 20 },
    { duration: "1m", target: 50 },
    { duration: "2m", target: 50 },
    { duration: "30s", target: 0 },
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
