#!/bin/bash
# ==============================================================================
# 投资日报与交易计划系统 - 快捷运行脚本
# 默认运行：ICT 板块结构机会日报 (纯板块 + 手机端极简 + 图文并茂)
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

PYTHON_EXEC="$PROJECT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON_EXEC" ]; then
    echo "❌ 未找到虚拟环境 Python: $PYTHON_EXEC"
    echo "请先使用 uv 创建环境: uv venv .venv --python 3.11"
    exit 1
fi

echo "🚀 启动投资日报与交易计划系统..."
echo "📁 项目路径: $PROJECT_DIR"
echo "🐍 Python解释器: $PYTHON_EXEC"
echo "⚙️ 传入参数: $@"
echo "------------------------------------------------------------"

if [ "$1" = "stocks" ]; then
    shift
    "$PYTHON_EXEC" main.py "$@"
    EXIT_CODE=$?
    if [[ "$*" != *"--no-notify"* ]]; then
        echo "📊 生成并推送战术复盘长图海报..."
        "$PYTHON_EXEC" src/services/poster_sender.py || true
    fi
    exit $EXIT_CODE
else
    # 默认模式：ICT 板块结构机会日报
    "$PYTHON_EXEC" src/services/ict_sector_reporter.py "$@"
    exit $?
fi
