#!/usr/bin/env bash
# 重置或创建 Strapi 管理后台账号
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# 检查容器是否存在
if ! docker inspect server >/dev/null 2>&1; then
  echo -e "${RED}[ERROR]${NC} 容器 'server' 不存在，请先部署服务"
  exit 1
fi

# 检查容器是否运行，未运行则启动
running=$(docker inspect -f '{{.State.Running}}' server 2>/dev/null)
if [ "$running" != "true" ]; then
  echo -e "${YELLOW}[WARN]${NC}  容器 'server' 未运行，正在启动..."
  docker start server
  echo -e "${CYAN}[INFO]${NC}  等待服务就绪..."
  sleep 5
fi

# 读取密码（带二次确认）
read_password() {
  local password confirm
  while true; do
    read -rsp "密码: " password; echo
    if [ -z "$password" ]; then
      echo -e "${YELLOW}[WARN]${NC}  密码不能为空，请重新输入"
      continue
    fi
    read -rsp "确认密码: " confirm; echo
    if [ "$password" != "$confirm" ]; then
      echo -e "${YELLOW}[WARN]${NC}  两次输入不一致，请重新输入"
      continue
    fi
    echo "$password"
    return
  done
}

echo ""
echo "请选择操作："
echo "  1) 重置已有账号的密码"
echo "  2) 新建管理员账号"
read -rp "请选择 [1/2，默认 1]: " choice
choice="${choice:-1}"

case "$choice" in
  1)
    read -rp "账号邮箱: " email
    if [ -z "$email" ]; then
      echo -e "${RED}[ERROR]${NC} 邮箱不能为空"
      exit 1
    fi
    password=$(read_password)
    echo -e "${CYAN}[INFO]${NC}  正在重置密码..."
    docker exec server npx strapi admin:reset-user-password \
      --email="$email" \
      --password="$password"
    echo -e "${GREEN}[OK]${NC}    密码已更新"
    ;;
  2)
    read -rp "邮箱: " email
    read -rp "名字 [默认: Admin]: " firstname
    firstname="${firstname:-Admin}"
    read -rp "姓氏 [默认留空]: " lastname
    password=$(read_password)
    echo -e "${CYAN}[INFO]${NC}  正在创建账号..."
    docker exec server npx strapi admin:create-user \
      --email="$email" \
      --firstname="$firstname" \
      --lastname="$lastname" \
      --password="$password"
    echo -e "${GREEN}[OK]${NC}    账号已创建"
    ;;
  *)
    echo -e "${RED}[ERROR]${NC} 无效选项"
    exit 1
    ;;
esac

echo -e "${CYAN}[INFO]${NC}  登录地址：http://<服务器IP>:1337/admin"
