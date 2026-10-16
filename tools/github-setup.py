#!/usr/bin/env python3
"""
GitHub 一次性接管（幂等，可重复运行）

做四件事：验证 token → 建仓库（若不存在）→ 提交本地改动 → 推送

用法：
  python tools/github-setup.py --token ghp_xxx
  python tools/github-setup.py                  # 从 studio/.env 读 GITHUB_TOKEN
  python tools/github-setup.py --repo my-repo --private
  python tools/github-setup.py --no-push

安全：
  - token 只用于本次推送的 URL，不写进 .git/config（remote 存的是无 token 的干净地址）
  - 回显时过滤 token，绝不打印出来
  - 随时可在 GitHub 设置里吊销

为什么是 Python 而不是 PowerShell：PowerShell 5.1 读「无 BOM 的 UTF-8 脚本」会按
GBK 解码，中文会把字符串截断（实测报过错）。Python 源码默认 UTF-8，没这个坑。
"""
import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request

# 保证中文在任何控制台都不乱码（Windows 控制台默认可能是 GBK）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
API = "https://api.github.com"


def say(msg, color=None):
    codes = {"green": "\033[32m", "red": "\033[31m", "yellow": "\033[33m", "gray": "\033[90m"}
    pre = codes.get(color, "")
    suf = "\033[0m" if pre else ""
    print(f"{pre}{msg}{suf}", flush=True)


def die(msg):
    say(f"\n[X] {msg}", "red")
    sys.exit(1)


def api(url, token, method="GET", body=None, timeout=45):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "delta-shorts-studio-setup",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if data:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw.strip() else {}), dict(r.headers)
    except urllib.error.HTTPError as e:
        return e.code, None, dict(e.headers or {})
    except Exception as e:
        return 0, {"_err": str(e)}, {}


def git(*args, check=True):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "").strip())
    return p


def load_env():
    vals = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                vals[k.strip()] = v.strip().strip('"').strip("'")
    return vals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token")
    ap.add_argument("--repo", default=None)
    ap.add_argument("--description",
                    default="三角洲竖屏动画 AI 短视频生产管线（固定资产库 + 分镜 + 拆解器 + 夜间下载）")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args()

    env = load_env()
    token = a.token or env.get("GITHUB_TOKEN") or ""
    repo = a.repo or env.get("GITHUB_REPO") or "delta-shorts-studio"

    if not token:
        die(f"""没有拿到 token。

两种给法（任选）：
  A) 命令行：  python tools\\github-setup.py --token ghp_你的token
  B) 写文件：  在 {os.path.join(ROOT, '.env')} 里写一行
               GITHUB_TOKEN=ghp_你的token
               （.env 已在 .gitignore 里，不会被提交）""")

    token = token.strip()

    # 1. 验证
    say("\n[1/5] 验证 token ...")
    status, me, _ = api(f"{API}/user", token)
    if status == 401:
        die("token 无效或已被吊销（401）。")
    if status != 200 or not isinstance(me, dict) or "login" not in me:
        die(f"验证失败：HTTP {status} {me}")
    login = me["login"]
    say(f"      OK  已认证为 {login}", "green")

    # 2. 建仓库
    say(f"\n[2/5] 检查仓库 {login}/{repo} ...")
    status, data, _ = api(f"{API}/repos/{login}/{repo}", token)
    exists = (status == 200)
    if exists:
        say("      已存在，跳过创建")
    else:
        body = {"name": repo, "description": a.description,
                "private": bool(a.private), "auto_init": False}
        st2, d2, _ = api(f"{API}/user/repos", token, "POST", body, timeout=60)
        if st2 in (200, 201):
            say(f"      OK  已创建 https://github.com/{login}/{repo}", "green")
        else:
            die(f"""建仓库失败：HTTP {st2} {d2}

最常见原因：用的是 fine-grained token，它无法创建新仓库。
-> 请改用【经典 token】并勾选 Scopes 里的 repo。
   （只想推到已有仓库的话 fine-grained 也可以，但要用 --repo 指向已存在的仓库）""")

    # 3. 提交
    say("\n[3/5] 提交本地改动 ...")
    if not os.path.isdir(os.path.join(ROOT, ".git")):
        git("init", "-q")
        say("      已 git init")
    if not git("config", "user.name", check=False).stdout.strip():
        git("config", "user.name", "Tomshiewen")
        say("      已设 user.name=Tomshiewen")
    if not git("config", "user.email", check=False).stdout.strip():
        git("config", "user.email", "xiexwj@163.com")
        say("      已设 user.email=xiexwj@163.com")

    git("add", "-A")
    pending = [l for l in git("status", "--porcelain").stdout.splitlines() if l.strip()]
    if pending:
        git("commit", "-q", "-m", "chore: 本地改动（github-setup 自动提交）")
        say(f"      OK  已提交 {len(pending)} 个文件的改动", "green")
    else:
        say("      无待提交改动")
    say("      当前 HEAD: " + git("log", "--oneline", "-1").stdout.strip())

    # 4. remote
    say("\n[4/5] 配置 remote ...")
    clean = f"https://github.com/{login}/{repo}.git"
    remotes = git("remote").stdout.split()
    if "origin" in remotes:
        git("remote", "set-url", "origin", clean)
    else:
        git("remote", "add", "origin", clean)
    say(f"      origin = {clean}   （不含 token）")

    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip() or "main"

    if a.no_push:
        say("\n[5/5] 已指定 --no-push，跳过推送。", "yellow")
        say(f"      手动推送：git push https://<token>@github.com/{login}/{repo}.git {branch}")
        return 0

    # 5. 推送
    say("\n[5/5] 推送 ...")
    auth = f"https://{login}:{token}@github.com/{login}/{repo}.git"
    p = subprocess.run(["git", "push", auth, f"HEAD:refs/heads/{branch}"],
                       cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = ((p.stdout or "") + (p.stderr or "")).replace(token, "***")
    for line in out.splitlines():
        if line.strip():
            say("      " + line.strip())
    if p.returncode != 0:
        die(f"""推送失败（exit {p.returncode}）。

常见原因：
  1. token 缺少 Contents: Read and write 权限
  2. token 已过期或被吊销
  3. 仓库名/用户名不匹配（本次用 {login}/{repo}）""")

    say(f"\n[OK] 完成：https://github.com/{login}/{repo}", "green")
    say(f"     默认分支：{branch}")
    say("\n后续我可以直接做：推代码、开 PR、管 issue、配 Actions、发 release。", "green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
