@echo off
chcp 65001 >nul
cd /d "%~dp0"

where git >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 git，请先安装: https://git-scm.com/download/win
    pause
    exit /b 1
)

if not exist .git (
    git init
    git remote add origin https://github.com/Archdogms/knowledge_graph.git
)

git add .
git status
git commit -m "Initial: LLM entity/relation extraction + Nanhai corpus"
git branch -M main
git push -u origin main

echo.
echo 完成。若推送时要求登录，请在浏览器中完成 GitHub 认证。
pause
