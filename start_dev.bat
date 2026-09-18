@echo off
title 空间数据库实习 - 一键启动脚本

echo ======================================================================
echo   全国高校志愿填报空间数据库暨地理查询原型系统 (WebGIS)
echo   武汉大学 遥感信息工程学院 · 空间数据库实习
echo ======================================================================
echo.

:: 1. 检查后端 .env 配置文件
if not exist "%~dp0backend\.env" (
    echo [提示] 检测到 backend 目录下缺少 .env 配置文件，正在从 .env.example 自动生成...
    copy "%~dp0backend\.env.example" "%~dp0backend\.env" >nul
    echo [提示] 已生成 backend\.env，默认密码如需修改请手动编辑该文件。
    echo.
)

:: 2. 启动 FastAPI 后端服务
echo [1/3] 正在启动后端服务 (FastAPI, 端口 8000)...
start "FastAPI Backend (8000)" cmd /k "title FastAPI Backend && cd /d ""%~dp0backend"" && if exist .venv\Scripts\activate.bat (call .venv\Scripts\activate.bat) && python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

:: 稍作等待
timeout /t 3 /nobreak >nul

:: 3. 启动 Vue 3 前端服务
echo [2/3] 正在启动前端开发服务 (Vite, 端口 5173)...
start "Vue 3 Frontend (5173)" cmd /k "title Vue 3 Frontend && cd /d ""%~dp0frontend"" && if not exist node_modules (echo [提示] 首次运行，正在安装前端依赖 npm install... && npm install) && npm run dev"

:: 4. 自动打开浏览器
echo [3/3] 正在调起默认浏览器访问系统...
timeout /t 2 /nobreak >nul
start http://localhost:5173/

echo.
echo ======================================================================
echo   服务已在独立窗口中后台启动！
echo.
echo   - 前端页面: http://localhost:5173/
echo   - 后端接口: http://127.0.0.1:8000/
echo   - 接口文档: http://127.0.0.1:8000/docs
echo.
echo   【前置提示】请确保本机 PostgreSQL 数据库已启动且包含 gaokao3！
echo   如果接口报错，请检查 backend\.env 中的 PGPASSWORD 是否与本机一致。
echo ======================================================================
echo.
pause
