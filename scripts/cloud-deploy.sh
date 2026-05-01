#!/usr/bin/env bash
# 云服务器一键部署脚本（阿里云/腾讯云/AWS等）

set -euo pipefail

echo "🚀 MetaClaw 云服务器一键部署"
echo "=============================="

# 检测系统
if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    OS=$NAME
else
    echo "❌ 无法检测操作系统"
    exit 1
fi

echo "📦 系统: $OS"

# 安装 Docker
echo "📥 安装 Docker..."
if [[ "$OS" == *"Ubuntu"* ]] || [[ "$OS" == *"Debian"* ]]; then
    apt-get update
    apt-get install -y docker.io docker-compose
elif [[ "$OS" == *"CentOS"* ]] || [[ "$OS" == *"Red Hat"* ]]; then
    yum install -y docker docker-compose
elif [[ "$OS" == *"Amazon Linux"* ]]; then
    yum install -y docker
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
fi

# 启动 Docker
systemctl start docker
systemctl enable docker

# 部署 MetaClaw
echo "🤖 部署 MetaClaw..."
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/scripts/deploy.sh -o /usr/local/bin/metaclaw-deploy
chmod +x /usr/local/bin/metaclaw-deploy

# 创建配置目录
mkdir -p /opt/metaclaw
cd /opt/metaclaw

# 下载配置文件
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/docker-compose.yml -o docker-compose.yml
curl -fsSL https://raw.githubusercontent.com/WarholYuan/metaclaw-installer/main/.env.example -o .env.example

# 提示配置
echo ""
echo "✅ 基础安装完成！"
echo ""
echo "下一步："
echo "1. cd /opt/metaclaw"
echo "2. cp .env.example .env"
echo "3. nano .env  # 填入 API Key"
echo "4. docker-compose up -d"
echo ""
echo "Web 控制台将运行在: http://$(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip'):9899"
