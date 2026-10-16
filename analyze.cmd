@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"

rem ====================================================================
rem  对标视频拆解器 —— 把视频文件【拖到这个 cmd 上】即可
rem  或者：  analyze.cmd "C:\路径\视频.mp4"
rem  输出：  tmp\ref-analysis-last\report.json  +  contact-sheet.png
rem ====================================================================

set "PY=%USERPROFILE%\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
if not exist "%PY%" set "PY=python"

if "%~1"=="" (
  echo.
  echo   用法：把视频文件拖到本文件上，或者
  echo         analyze.cmd "C:\路径\视频.mp4"
  echo.
  pause
  exit /b 1
)

echo.
echo ==========================================================
echo   拆解：%~nx1
echo ==========================================================
"%PY%" "tools\analyze_reference.py" "%~1" --out "tmp\ref-analysis-last"
if errorlevel 1 (
  echo.
  echo   !! 拆解失败。常见原因：
  echo      - 路径含特殊字符（把文件复制到 C:\temp 再试）
  echo      - 视频编码 cv2 解不开
)

echo.
echo ----------------------------------------------------------
echo   产出目录：%~dp0tmp\ref-analysis-last
echo     report.json        镜头表 / 切点 / 节奏 / 色调
echo     contact-sheet.png  缩略图拼版（可直接看图判风格）
echo ----------------------------------------------------------
echo.
echo   提醒：如果这个文件是【手机录屏】，数字描述的是录屏而不是原视频。
echo         要准确数据，请用【原片】（无水印下载或作者原始文件）。
echo.
pause
