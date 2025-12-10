#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_IMPORT_PATH="backend.app.main:app"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIREMENTS_FILE="${SCRIPT_DIR}/backend/requirements.txt"
FRONTEND_DIR="${SCRIPT_DIR}/frontend"
DEFAULT_BACKEND_PORT=8000
DEFAULT_FRONTEND_PORT=5173

print_usage() {
  cat <<EOF
Usage: $(basename "$0") [backend_port] [frontend_port]

Arguments:
  backend_port   可选。FastAPI 端口，默认 8000（或环境变量 PORT）。
  frontend_port  可选。Vite 端口，默认 5173（或环境变量 FRONTEND_PORT）。

示例：$(basename "$0") 9000 5100
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  print_usage
  exit 0
fi

find_python() {
  if command -v python3 >/dev/null 2>&1; then
    command -v python3
  elif command -v python >/dev/null 2>&1; then
    command -v python
  else
    echo ""
  fi
}

ensure_venv() {
  if [[ -d "${VENV_DIR}" ]]; then
    return
  fi
  local py_bin
  py_bin="$(find_python)"
  if [[ -z "${py_bin}" ]]; then
    echo "[ERROR] 未找到 python3，请先安装 Python 3。" >&2
    exit 1
  fi
  echo "未检测到虚拟环境，使用 ${py_bin} 创建 .venv ..."
  "${py_bin}" -m venv "${VENV_DIR}"
}

activate_venv() {
  # shellcheck source=/dev/null
  source "${VENV_DIR}/bin/activate"
}

install_requirements() {
  if [[ -f "${REQUIREMENTS_FILE}" ]]; then
    echo "安装/更新后端依赖 ..."
    python -m pip install -r "${REQUIREMENTS_FILE}"
  else
    echo "[WARN] 未找到 ${REQUIREMENTS_FILE}，跳过依赖安装。"
  fi
}

ensure_node_tools() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "[ERROR] 未找到 npm，请先安装 Node.js。" >&2
    exit 1
  fi
}

setup_frontend() {
  ensure_node_tools
  if [[ ! -d "${FRONTEND_DIR}" ]]; then
    echo "[ERROR] 未找到 frontend 目录。" >&2
    exit 1
  fi
  pushd "${FRONTEND_DIR}" >/dev/null
  if [[ ! -d "node_modules" ]]; then
    echo "首次运行前端，执行 npm install ..."
    npm install
  fi
  popd >/dev/null
}

start_backend() {
  echo "启动 backend 应用：uvicorn ${APP_IMPORT_PATH} --host 127.0.0.1 --port ${BACKEND_PORT}"
  "${VENV_DIR}/bin/uvicorn" "${APP_IMPORT_PATH}" --host 127.0.0.1 --port "${BACKEND_PORT}" &
  BACKEND_PID=$!
}

start_frontend() {
  pushd "${FRONTEND_DIR}" >/dev/null
  export VITE_API_BASE="http://127.0.0.1:${BACKEND_PORT}"
  echo "启动 frontend：VITE_API_BASE=${VITE_API_BASE} npm run dev -- --host 127.0.0.1 --port ${FRONTEND_PORT}"
  VITE_API_BASE="${VITE_API_BASE}" npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}"
  popd >/dev/null
}

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]]; then
    echo "停止 backend (PID ${BACKEND_PID}) ..."
    kill "${BACKEND_PID}" >/dev/null 2>&1 || true
    wait "${BACKEND_PID}" 2>/dev/null || true
  fi
}

BACKEND_PORT="${PORT:-$DEFAULT_BACKEND_PORT}"
FRONTEND_PORT="${FRONTEND_PORT:-$DEFAULT_FRONTEND_PORT}"

if [[ -n "${1:-}" ]]; then
  BACKEND_PORT="$1"
fi
if [[ -n "${2:-}" ]]; then
  FRONTEND_PORT="$2"
fi

cd "$SCRIPT_DIR"

ensure_venv
activate_venv
install_requirements
setup_frontend

if ! command -v uvicorn >/dev/null 2>&1; then
  echo "[ERROR] 虚拟环境内未找到 uvicorn，请检查 requirements 是否安装成功。" >&2
  exit 1
fi

trap cleanup EXIT INT TERM

start_backend
start_frontend
