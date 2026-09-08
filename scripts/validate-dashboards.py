#!/usr/bin/env python3
"""Validate Grafana dashboard JSON files have required schema fields."""
import json
import sys
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DASHBOARDS = [
    os.path.join(BASE, "dashboards", "cloudforge-overview.json"),
    os.path.join(BASE, "dashboards", "cloudforge-k8s.json"),
]

errors = 0
for path in DASHBOARDS:
    with open(path) as fh:
        d = json.load(fh)
    required = ["title", "uid", "panels", "schemaVersion"]
    for k in required:
        if k not in d:
            print(f"ERROR: {path} missing key: {k}")
            errors += 1
    print(f"OK: {path} (title={d.get('title')}, panels={len(d.get('panels', []))})")

sys.exit(errors)
