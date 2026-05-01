#!/usr/bin/env bash
set -euo pipefail

# MetaClaw 服务器部署脚本

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() { echo -e "${BLUE}ℹ${NC}  $*"; }
log_success() { echo -e "${GREEN}✔${NC}  $*"; }
log_warn() { echo -e "${YELLOW}⚠${NC}  $*"; }
log_error() { echo -e "${RED}✖${NC}  $*" >&2; }

# 检查 Docker
check_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    log_error "Docker 未安装"
    log_info "安装 Docker: https://docs.docker.com/engine/install/"
    exit 1
  fi

  if ! command -v docker-compose >/dev/null 2>&1; then
    log_error "Docker Compose 未安装"
    log_info "安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
  fi

  log_success "Docker 和 Docker Compose 已安装"
}

# 创建配置
create_config() {
  log_info "创建配置..."

  if [[ ! -f .env ]]; then
    log_warn "未找到 .env 文件，使用示例配置"
    cp .env.example .env
    log_info "请编辑 .env 文件填入你的 API Key"
  fi

  mkdir -p workspace
  log_success "配置目录已创建"
}

# 启动服务
start_service() {
  log_info "启动 MetaClaw 服务..."
  docker-compose up -d
  log_success "服务已启动"
}

# 检查状态
check_status() {
  log_info "检查服务状态..."
  sleep 5

  if docker-compose ps | grep -q "Up"; then
    log_success "MetaClaw 运行正常"
    log_info "Web 控制台: http://$(curl -s ifconfig.me):9899"
  else
    log_error "服务启动失败，查看日志:"
    docker-compose logs
    exit 1
  fi
}

# 显示帮助
show_help() {
  cat <<EOF
MetaClaw 服务器部署脚本

用法: ./deploy.sh [命令]

命令:
  install    首次安装并启动
  start      启动服务
  stop       停止服务
  restart    重启服务
  update     更新到最新版本
  logs       查看日志
  status     查看状态
  uninstall  卸载服务

示例:
  ./deploy.sh install    # 首次安装
  ./deploy.sh update     # 更新版本
EOF
}

# 主函数
main() {
  case "${1:-install}" in
    install)
      check_docker
      create_config
      start_service
      check_status
      ;;
    start)
      docker-compose start
      log_success "服务已启动"
      ;;
    stop)
      docker-compose stop
      log_success "服务已停止"
      ;;
    restart)
      docker-compose restart
      log_success "服务已重启"
      ;;
    update)
      docker-compose pull
      docker-compose up -d
      log_success "已更新到最新版本"
      ;;
    logs)
      docker-compose logs -f
      ;;
    status)
      docker-compose ps
      ;;
    uninstall)
      docker-compose down -v
      log_success "服务已卸载"
      ;;
    *)
      show_help
      exit 1
      ;;
  esac
}

main "$@"
