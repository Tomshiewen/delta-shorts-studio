# GitHub 一次性接管脚本（幂等，可重复运行）
#
# 用法：
#   .\tools\github-setup.ps1 -Token ghp_xxxxxxxx
#   .\tools\github-setup.ps1                      # 从 studio\.env 读 GITHUB_TOKEN
#   .\tools\github-setup.ps1 -Repo my-repo -Private
#
# 做四件事：验证 token → 建仓库（若不存在）→ 提交本地改动 → 推送
#
# 安全说明：
#   - token 只用于本次推送的 URL，**不会写进 .git/config**（remote 保存的是无 token 的干净地址）
#   - 不会打印 token 内容
#   - 随时可在 GitHub 设置里吊销该 token

param(
  [string]$Token,
  [string]$Repo = 'delta-shorts-studio',
  [string]$Description = '三角洲竖屏动画 AI 短视频生产管线（固定资产库 + 分镜 + 拆解器 + 夜间下载）',
  [switch]$Private,
  [switch]$NoPush
)

$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)   # studio\
Set-Location $Root

function Say($m, $c = 'Gray') { Write-Host $m -ForegroundColor $c }
function Die($m) { Write-Host "`n✗ $m" -ForegroundColor Red; exit 1 }

# ---------------------------------------------------------------- 1. 取 token
if (-not $Token) {
  $envFile = Join-Path $Root '.env'
  if (Test-Path $envFile) {
    foreach ($line in Get-Content $envFile -Encoding UTF8) {
      if ($line -match '^\s*GITHUB_TOKEN\s*=\s*(.+?)\s*$') { $Token = $Matches[1].Trim('"').Trim("'") }
      if ($line -match '^\s*GITHUB_REPO\s*=\s*(.+?)\s*$' -and $Matches[1].Trim()) { $Repo = $Matches[1].Trim() }
    }
  }
}
if (-not $Token) {
  Die @"
没有拿到 token。

两种给法（任选）：
  A) 命令行：  .\tools\github-setup.ps1 -Token ghp_你的token
  B) 写文件：  在 $Root\.env 里写一行   GITHUB_TOKEN=ghp_你的token
               （.env 已在 .gitignore 里，不会被提交）
"@
}

$Headers = @{
  Authorization          = "Bearer $Token"
  Accept                 = 'application/vnd.github+json'
  'User-Agent'           = 'delta-shorts-studio-setup'
  'X-GitHub-Api-Version' = '2022-11-28'
}

# ---------------------------------------------------------------- 2. 验证
Say "`n[1/5] 验证 token …"
try {
  $me = Invoke-RestMethod -Uri 'https://api.github.com/user' -Headers $Headers -TimeoutSec 30
} catch {
  Die "token 无效或网络不通：$($_.Exception.Message)"
}
$Login = $me.login
Say "      ✓ 已认证为 $Login" Green

$Scopes = ''
try {
  $r = Invoke-WebRequest -Uri 'https://api.github.com/user' -Headers $Headers -UseBasicParsing -TimeoutSec 30
  $Scopes = [string]$r.Headers['X-OAuth-Scopes']
} catch { }
if ($Scopes) { Say "      权限范围：$Scopes" }

# ---------------------------------------------------------------- 3. 建仓库
Say "`n[2/5] 检查仓库 $Login/$Repo …"
$Exists = $false
try {
  Invoke-RestMethod -Uri "https://api.github.com/repos/$Login/$Repo" -Headers $Headers -TimeoutSec 30 | Out-Null
  $Exists = $true
  Say "      已存在，跳过创建"
} catch {
  if ($_.Exception.Response.StatusCode.value__ -eq 404) { $Exists = $false }
  else { Say "      查询失败（按不存在处理）：$($_.Exception.Message)" Yellow }
}

if (-not $Exists) {
  $Body = @{ name = $Repo; description = $Description; private = [bool]$Private; auto_init = $false } | ConvertTo-Json
  try {
    Invoke-RestMethod -Uri 'https://api.github.com/user/repos' -Method Post -Headers $Headers -Body $Body -ContentType 'application/json' -TimeoutSec 60 | Out-Null
    Say "      ✓ 已创建 https://github.com/$Login/$Repo" Green
  } catch {
    Die @"
建仓库失败：$($_.Exception.Message)

最常见原因：用的是 fine-grained token，它无法创建新仓库。
→ 请改用【经典 token】并在 Scopes 里勾选 repo。
（只想推到已有仓库的话，fine-grained 也可以，但要把 -Repo 指向已存在的仓库。）
"@
  }
}

# ---------------------------------------------------------------- 4. 提交本地
Say "`n[3/5] 提交本地改动 …"
if (-not (Test-Path (Join-Path $Root '.git'))) { git init -q; Say "      已 git init" }

$uname = (git config user.name)
if (-not $uname) { git config user.name 'Tomshiewen'; Say "      已设 user.name=Tomshiewen" }
$umail = (git config user.email)
if (-not $umail) { git config user.email 'xiexwj@163.com'; Say "      已设 user.email=xiexwj@163.com" }

git add -A
$pending = (git status --porcelain | Measure-Object -Line).Lines
if ($pending -gt 0) {
  $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm'
  git commit -q -m "chore: 提交本地改动（$stamp）"
  Say "      ✓ 已提交 $pending 个文件的改动" Green
} else {
  Say "      无待提交改动"
}
Say "      当前 HEAD: $(git log --oneline -1)"

# ---------------------------------------------------------------- 5. 推送
Say "`n[4/5] 配置 remote …"
$cleanUrl = "https://github.com/$Login/$Repo.git"
$existing = (git remote) -contains 'origin'
if ($existing) { git remote set-url origin $cleanUrl } else { git remote add origin $cleanUrl }
Say "      origin = $cleanUrl（不含 token）"

if ($NoPush) {
  Say "`n[5/5] 已指定 -NoPush，跳过推送。" Yellow
  Say "      手动推送：  git push https://<token>@github.com/$Login/$Repo.git main" 
  exit 0
}

Say "`n[5/5] 推送 …"
$authUrl = "https://$Login`:$Token@github.com/$Login/$Repo.git"
$branch = (git rev-parse --abbrev-ref HEAD)
$out = git push $authUrl "HEAD:refs/heads/$branch" 2>&1
$code = $LASTEXITCODE
$out | ForEach-Object { $s = [string]$_; if ($s -notmatch [regex]::Escape($Token)) { Say "      $_" } }   # 回显时过滤掉 token

if ($code -ne 0) {
  Die @"
推送失败（exit $code）。

常见原因：
  1. token 没有 Contents: Read and write 权限
  2. token 已过期或被吊销
  3. 仓库名/用户名不匹配（本次用 $Login/$Repo）
"@
}

Say "`n✓ 完成：https://github.com/$Login/$Repo" Green
Say "  默认分支：$branch"
Say "`n后续我就能直接做：推代码、开 PR、管 issue、配 Actions、发 release。" Green
