#!/bin/bash
echo "========================================"
echo "  Data BI Agent - 智能数据分析平台"
echo "========================================"
echo ""

if [ ! -f ".env" ]; then
    echo "正在创建配置文件..."
    cp .env.example .env
    echo ""
    echo "[重要] 请编辑 .env 文件，填入你的 LLM API Key"
    echo "支持任何 OpenAI 兼容 API (OpenAI / Deepseek / Ollama 等)"
    echo ""
    ${EDITOR:-vi} .env
fi

echo "正在检查依赖..."
pip install -r requirements.txt -q

echo ""
echo "启动 Data BI Agent..."
echo "首次启动将自动生成演示数据 (约 6000 条订单)"
echo ""
python app.py
