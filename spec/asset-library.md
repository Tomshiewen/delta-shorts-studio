# 固定资产库规范

**一句话**：资产库决定产能。每多一条可复用资产，后续每条视频的边际成本就更低。

这个库不是「素材文件夹」，是**带来源与风险追踪的索引系统**——因为素材路线是二创，风险必须结构化记录，而不是靠记忆。

---

## 一、什么算「固定资产」

可以**跨多条视频重复使用**、且质量稳定到不需要每次重做的元素：

| 类别 | 目录 | 例子 |
| --- | --- | --- |
| 角色 | `assets/characters/` | 主角立绘（多表情/多角度）、反派、NPC |
| 场景 | `assets/scenes/` | 巷战、撤离点、物资点、载具内部 |
| 道具 | `assets/props/` | 枪械剪影、医疗包、弹药箱、对讲机 |
| 特效 | `assets/fx/` | 枪口火焰、弹道、命中反馈、UI 动效、转场 |
| 音频 | `assets/audio/` | BGM、枪声、脚步、UI 音、报点语音 |
| 字幕模板 | `assets/templates/` | 花字样式、标题条、结尾卡 |
| 分镜模板 | `assets/templates/` | 常用节奏结构（3 秒钩子 / 8 秒冲突 / 10 秒回收） |

**不进库的**：一次性素材、质量不达标的、来源不明的。

---

## 二、命名规范

```
<类别>_<主体>_<变体>_<版本>.<扩展名>

char_ghost_idle_v1.png
scene_downtown_dusk_v2.png
fx_muzzleflash_small_v1.mp4
audio_gunshot_ak_v1.wav
tmpl_hook_3s_v1.json
```

规则：
- 全小写、下划线分隔，**不用中文文件名**（避免编码与跨工具问题）
- 版本号从 `v1` 起，**修改即升版本，不覆盖**
- 一个文件只表达一件事；「主角+场景」不合并成一张图

---

## 三、来源与风险追踪（核心）

每条资产在 `manifest.json` 里必须有这些字段：

| 字段 | 取值 | 用途 |
| --- | --- | --- |
| `id` | 与文件名一致 | 主键 |
| `type` | character / scene / prop / fx / audio / template | 分类 |
| `path` | 相对 `assets/` 的路径 | 定位 |
| `hash` | sha256 前 16 位 | 去重、变更检测 |
| `origin` | `original` / `recorded` / `generated` / `licensed` / `unknown` | **来源性质** |
| `ipOwner` | 如 `Tencent` / `none` | **是否含第三方 IP** |
| `licenseStatus` | `owned` / `permitted` / `fanwork` / `unclear` | 授权状态 |
| `commercialUse` | `safe` / `caution` / `no` | **能否用于商业变现** |
| `riskNote` | 自由文本 | 具体风险说明 |
| `usedIn` | 项目 id 数组 | 复用追踪（算出复用率） |
| `addedAt` | ISO 日期 | 库龄 |

### 判定规则

| origin | ipOwner | commercialUse | 说明 |
| --- | --- | --- | --- |
| `original` | none | **safe** | 自己画的/自己录的原创素材 |
| `generated` | none | **safe** | AI 生成，无第三方形象 |
| `generated` | Tencent | **caution** | AI 重绘但明显指向某游戏角色 |
| `recorded` | Tencent | **caution** | 游戏录屏，二创发布通常被容忍，**带货时风险升高** |
| `recorded` | Tencent | **no** | 直接包含他人 UI/水印/肖像的片段 |
| `unknown` | — | **no** | 来源不明，一律不用 |

**硬规则**：`commercialUse = no` 的资产**不允许**出现在挂了购物车的视频里。合成层会做一次检查并报错。

---

## 四、复用率是唯一该看的产能指标

```
复用率 = 1 − (本视频新增资产数 ÷ 本视频总引用资产数)
```

- 第 1 条视频：复用率 ≈ 0（一切都要新建）
- 第 10 条：目标 ≥ 60%
- 第 30 条：目标 ≥ 80%

`manifest.json` 里的 `usedIn` 让这个数可算。**如果复用率上不去，问题不在剪辑技巧，在资产库设计。**

---

## 五、目录与文件约定

```
assets/
├─ manifest.json          索引（唯一事实来源）
├─ characters/            透明底 PNG/WebP，建议 2048 高
├─ scenes/                16:9 与 9:16 各一套；命名后缀 _h / _v
├─ props/                 透明底
├─ fx/                    带 alpha 的 mp4（ProRes/WebM）或序列帧
├─ audio/                 wav / mp3，命名含时长：audio_bgm_tense_30s_v1.mp3
└─ templates/             字幕与分镜模板 JSON
```

**大文件不入 git**：单个 > 20 MB 的资产走本地库 + manifest 索引，仓库里只存 manifest 与缩略图。`.gitignore` 已覆盖 `assets/**/*.mp4` 等。

---

## 六、维护节奏

| 频率 | 动作 |
| --- | --- |
| 每条视频后 | 新增资产补进 manifest；更新 `usedIn` |
| 每周 | 检查 `commercialUse=caution` 的资产是否被误用于带货视频 |
| 每月 | 算复用率；低于目标就停下来补资产，而不是硬发视频 |
