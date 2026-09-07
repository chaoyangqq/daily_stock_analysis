#!/bin/bash
# ==============================================================================
# 投资日报与交易计划系统 - 快捷运行脚本
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

exec "$PYTHON_EXEC" main.py "$@"
