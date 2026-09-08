#!/usr/bin/env python3
"""CI 用：更新 chart/values.yaml 的镜像配置，实现 GitOps 闭环。

用法：python3 scripts/bump-chart-values.py <dockerhub-user> <image-name> <git-sha>

CI 构建并推送 <user>/cloudforge:<short-sha> 多架构镜像后，把 repository/tag/pullPolicy
写回 chart/values.yaml 并 commit（由 workflow 执行 push，commit message 带 [skip ci]），
ArgoCD 检测到 chart 变更 → 自动同步 → 集群滚动更新到新版本。
回滚 = 回退代码重新 push（CI 重新构建并更新 tag），无需任何手工操作。

本地 k3d 演示环境不需要跑此脚本，保持 values.yaml 默认值（本地镜像名）即可。
"""
import re
import sys
from pathlib import Path


def main() -> None:
    user, image, sha = sys.argv[1], sys.argv[2], sys.argv[3]
    short_sha = sha[:7]

    path = Path("chart/values.yaml")
    s = path.read_text(encoding="utf-8")

    # 行内精确替换值（保留缩进与行尾注释）：repository / tag（image 与 canary 两个块）/ pullPolicy
    s = re.sub(r"(?m)^(\s*repository:\s*)\S+", rf"\g<1>{user}/{image}", s)
    s = re.sub(r"(?m)^(\s*tag:\s*)\S+", rf"\g<1>{short_sha}", s)
    s = re.sub(r"(?m)^(\s*pullPolicy:\s*)\S+", r"\g<1>IfNotPresent", s)

    path.write_text(s, encoding="utf-8")
    print(f"values.yaml → repository={user}/{image}  tag={short_sha}  pullPolicy=IfNotPresent")


if __name__ == "__main__":
    main()
