@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ====================================================================
rem  GitHub 全权接管 —— 双击运行，或带 token 运行
rem
rem  有 token 的两种给法：
rem    1) 先把 token 写进  studio\.env    （推荐，之后双击即可）
rem          GITHUB_TOKEN=ghp_xxxxx
rem    2) 命令行：  github-setup.cmd ghp_xxxxx
rem
rem  自建仓库需要【经典 token 且勾选 repo】；fine-grained 推已有仓库可以，
rem  但不能新建仓库。
rem ====================================================================

set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

if "%~1"=="" (
  "%PY%" "tools\github-setup.py"
) else (
  "%PY%" "tools\github-setup.py" --token "%~1"
)

echo.
echo ----------------------------------------------------------
echo   完成后可在 GitHub 上看到仓库。若失败，把上面的红字发我。
echo ----------------------------------------------------------
pause
