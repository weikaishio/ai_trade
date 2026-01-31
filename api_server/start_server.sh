#!/bin/bash
# 同花顺交易API服务启动脚本

echo "======================================================"
echo "  同花顺交易API服务启动"
echo "======================================================"

# 检查Python版本
python3 --version

# 检查是否在正确的目录
if [ ! -f "main.py" ]; then
    echo "❌ 错误: 请在 api_server 目录下运行此脚本"
    exit 1
fi

# 检查依赖
echo ""
echo "检查依赖..."
pip3 show fastapi > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️  FastAPI未安装，正在安装依赖..."
    pip3 install -r requirements_api.txt
fi

# 检查配置文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到.env配置文件，使用默认配置"
    echo "   建议: cp .env.example .env 并修改配置"
fi

# 启动服务
echo ""
echo "======================================================"
echo "  启动服务..."
echo "======================================================"
echo ""

python3 -m uvicorn main:app \
    --host 127.0.0.1 \
    --port 8080 \
    --log-level info

# 或者使用内置启动方式
# python3 main.py
