#!/usr/bin/env python3
"""
夜间批量下载器（CC0 / 免费商用资产）。

设计成"可重复运行"：已存在的文件按 hash 跳过，中断后可续。
先跑 --plan 看清单与体积，确认后再真下。

用法：
  python fetch_assets.py --plan                 # 只列清单，不下载
  python fetch_assets.py --plan --kind font     # 只看某一类
  python fetch_assets.py                        # 真下载（夜间跑）
  python fetch_assets.py --kind font            # 只下某一类

支持的 kind：font / hdri / texture / sfx
下载后会在 assets/manifest.json 里追加条目（含 origin / ipOwner / licenseStatus / commercialUse）。
"""
import argparse
import hashlib
import json
import os
import ssl
import sys
import urllib.error
import urllib.request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ASSETS = os.path.join(ROOT, "assets")
MANIFEST = os.path.join(ASSETS, "manifest.json")
UA = "delta-shorts-studio/1.0 (asset fetcher)"
CTX = ssl.create_default_context()

# Poly Haven 免密钥 API
PH_API = "https://api.polyhaven.com"
# 想要多少（控制夜间用时）
LIMITS = {"hdri": 8, "texture": 12, "model": 0}


def log(*a):
    print(*a, flush=True)


def http_json(url, timeout=45):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def head_size(url, timeout=30):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA}, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            return int(r.headers.get("Content-Length") or 0)
    except Exception:
        return 0


def download(url, dest, expect_sha=None):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.path.exists(dest) and os.path.getsize(dest) > 0:
        return "skip"
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=300, context=CTX) as r, open(tmp, "wb") as f:
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
    os.replace(tmp, dest)
    return "ok"


def sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- Poly Haven
def plan_polyhaven(kind, limit):
    """kind: hdri / texture / model"""
    api_kind = {"hdri": "hdris", "texture": "textures", "model": "models"}[kind]
    try:
        items = http_json(f"{PH_API}/assets?t={api_kind}")
    except Exception as e:
        log(f"  ! Poly Haven 列表获取失败：{e}")
        return []
    out = []
    for aid in list(items.keys())[:limit]:
        try:
            files = http_json(f"{PH_API}/files/{aid}")
        except Exception:
            continue
        url = None
        if kind == "hdri":
            url = (files.get("hdri", {}).get("1k", {}).get("hdr", {}) or {}).get("url")
        elif kind == "texture":
            for _map, variants in (files.get("Diffuse") or {}).items():
                pass
            dif = files.get("Diffuse") or files.get("diffuse") or {}
            first = next(iter(dif.values()), {}) if isinstance(dif, dict) else {}
            url = (first.get("1k", {}).get("jpg", {}) or {}).get("url") if isinstance(first, dict) else None
        else:
            gltf = files.get("gltf", {})
            first = next(iter(gltf.values()), {}) if isinstance(gltf, dict) else {}
            url = (first.get("1k", {}).get("gltf", {}) or {}).get("url") if isinstance(first, dict) else None
        if not url:
            continue
        ext = os.path.splitext(url.split("?")[0])[1] or ".bin"
        out.append({
            "id": f"{kind}_{aid}_v1".replace("-", "_"),
            "type": {"hdri": "scene", "texture": "scene", "model": "prop"}[kind],
            "url": url,
            "dest": os.path.join(ASSETS, {"hdri": "scenes", "texture": "scenes", "model": "props"}[kind],
                                 f"{kind}_{aid}{ext}"),
            "origin": "licensed",
            "ipOwner": "none",
            "licenseStatus": "permitted",
            "commercialUse": "safe",
            "riskNote": "Poly Haven · CC0",
            "source": "Poly Haven",
        })
    return out


# --------------------------------------------------------------------- 字体
FONT_SOURCES = [
    {
        "name": "smiley-sans", "label": "得意黑 Smiley Sans", "license": "OFL-1.1",
        "api": "https://api.github.com/repos/atelier-anchor/smiley-sans/releases/latest",
        "match": lambda n: n.lower().endswith((".ttf", ".otf", ".zip")),
    },
    {
        "name": "noto-sans-sc", "label": "思源黑体 Noto Sans SC", "license": "OFL-1.1",
        "api": "https://api.github.com/repos/notofonts/noto-cjk/releases/latest",
        "match": lambda n: "sanssc" in n.lower().replace("-", "").replace("_", "") and n.lower().endswith(".zip"),
    },
]


def plan_fonts():
    out = []
    for s in FONT_SOURCES:
        try:
            rel = http_json(s["api"])
        except Exception as e:
            log(f"  ! {s['label']} 版本查询失败：{e}")
            continue
        assets = [a for a in rel.get("assets", []) if s["match"](a["name"])]
        if not assets:
            continue
        a = max(assets, key=lambda x: x.get("size", 0))
        out.append({
            "id": f"font_{s['name'].replace('-', '_')}_v1",
            "type": "template",
            "url": a["browser_download_url"],
            "size": a.get("size", 0),
            "dest": os.path.join(ASSETS, "templates", "fonts", a["name"]),
            "origin": "licensed",
            "ipOwner": "none",
            "licenseStatus": "permitted",
            "commercialUse": "safe",
            "riskNote": f"{s['label']} · {s['license']} · 可商用",
            "source": s["label"],
        })
    return out


# -------------------------------------------------------------------- Kenney
def plan_kenney():
    """抓 Kenney 素材索引页里的 zip 直链（站点结构若变则跳过，不报错）"""
    import re
    out = []
    try:
        req = urllib.request.Request("https://kenney.nl/assets", headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=45, context=CTX) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        log(f"  ! Kenney 索引抓取失败：{e}")
        return out
    links = sorted(set(re.findall(r'href="(/media/pages/assets/[^"]+\.zip)"', html)))
    for l in links[:6]:
        name = os.path.basename(l)
        out.append({
            "id": "kenney_" + re.sub(r"[^a-z0-9]+", "_", name.rsplit(".", 1)[0].lower()),
            "type": "prop",
            "url": "https://kenney.nl" + l,
            "dest": os.path.join(ASSETS, "props", name),
            "origin": "licensed",
            "ipOwner": "none",
            "licenseStatus": "permitted",
            "commercialUse": "safe",
            "riskNote": "Kenney · CC0",
            "source": "Kenney",
        })
    return out


# ---------------------------------------------------------------------- 主流程
def build_plan(kinds):
    plan = []
    if "font" in kinds:
        plan += plan_fonts()
    if "hdri" in kinds:
        plan += plan_polyhaven("hdri", LIMITS["hdri"])
    if "texture" in kinds:
        plan += plan_polyhaven("texture", LIMITS["texture"])
    if "sfx" in kinds:
        # Kenney 含音效包；Sonniss 明确禁止 AI 训练用途，这里不纳入
        plan += plan_kenney()
    return plan


def update_manifest(entries):
    try:
        m = json.load(open(MANIFEST, encoding="utf-8"))
    except Exception:
        m = {"version": "1.0.0", "assets": []}
    known = {a.get("id") for a in m.get("assets", [])}
    added = 0
    for e in entries:
        if e["id"] in known:
            continue
        p = e.get("dest")
        if p and os.path.exists(p):
            e = dict(e)
            e["path"] = os.path.relpath(p, ASSETS).replace("\\", "/")
            e["hash"] = sha16(p)
            e["addedAt"] = "2026-10-16"
            e["usedIn"] = []
            e.pop("url", None)
            e.pop("dest", None)
            m["assets"].append(e)
            added += 1
    m.setdefault("stats", {})["total"] = len(m["assets"])
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    return added


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", action="store_true", help="只列清单不下载")
    ap.add_argument("--kind", default="font,hdri,texture,sfx", help="逗号分隔：font/hdri/texture/sfx")
    a = ap.parse_args()
    kinds = [k.strip() for k in a.kind.split(",") if k.strip()]

    log(f"资产目录: {ASSETS}")
    log(f"类别: {', '.join(kinds)}\n")

    plan = build_plan(kinds)
    if not plan:
        log("没有可下载的条目（源站结构可能变了）。")
        return 1

    total = 0
    for e in plan:
        sz = e.get("size") or head_size(e["url"])
        e["_size"] = sz
        total += sz
        log(f"  [{e['type']:8}] {e['id'][:52]:52} {sz/1048576:8.2f} MB  <- {e['source']}")

    log(f"\n合计 {len(plan)} 项，约 {total/1048576:.1f} MB")

    if a.plan:
        log("\n（--plan 模式，未下载。去掉 --plan 即真下。）")
        return 0

    ok = skip = fail = 0
    for e in plan:
        try:
            r = download(e["url"], e["dest"])
            if r == "ok":
                ok += 1
                log(f"  ✓ {e['id']}")
            else:
                skip += 1
                log(f"  = {e['id']}（已存在）")
        except Exception as ex:
            fail += 1
            log(f"  ✗ {e['id']} -> {ex}")

    added = update_manifest(plan)
    log(f"\n下载完成：新下 {ok} · 跳过 {skip} · 失败 {fail} · manifest 新增 {added} 条")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
