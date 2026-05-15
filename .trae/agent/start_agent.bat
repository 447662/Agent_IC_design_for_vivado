@echo off
REM -----------------------------------------------------------------------------
REM Script Name: start_agent.bat
REM Description: 启动数字IC前端设计Agent
REM Author: Digital IC Designer Team
REM Date: 2026-05-15
REM -----------------------------------------------------------------------------

echo ==============================================
echo   数字IC前端设计Agent
echo ==============================================

REM 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: Python未安装或未添加到PATH
    echo 请安装Python并添加到系统环境变量
    pause
    exit /b 1
)

REM 运行Agent
python "%~dp0\agent.py" %*

pause