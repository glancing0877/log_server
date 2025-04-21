#!/bin/bash

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root权限运行此脚本"
    echo "使用方法: sudo bash install.sh"
    exit 1
fi

echo "开始安装日志服务器..."

# 创建服务用户
echo "正在创建服务用户..."
useradd -r -s /bin/false logserver || echo "用户已存在，跳过创建"

# 创建部署目录
echo "正在创建部署目录..."
mkdir -p /opt/log_server
cd "$(dirname "$0")/.."
cp -r ./* /opt/log_server/

# 部署到网站根目录
echo "正在部署到网站根目录..."
mkdir -p /home/wwwroot/default
cp -r index.html static /home/wwwroot/default/
chown -R www-data:www-data /home/wwwroot/default
chmod -R 755 /home/wwwroot/default

# 设置权限
echo "正在设置文件权限..."
chown -R logserver:logserver /opt/log_server
chmod -R 755 /opt/log_server

# 安装Python依赖
echo "正在安装Python依赖..."
pip3 install -r /opt/log_server/requirements.txt

# 配置systemd服务
echo "正在配置系统服务..."
cp /opt/log_server/deploy/log_server.service /etc/systemd/system/
systemctl daemon-reload

# 配置防火墙
echo "正在配置防火墙规则..."
if command -v ufw >/dev/null 2>&1; then
    ufw allow 8080/tcp
    ufw allow 45860/tcp
    ufw allow 8765/tcp
    echo "防火墙规则已添加"
else
    echo "未检测到ufw，请手动配置防火墙规则"
fi

# 创建日志目录
echo "正在创建日志目录..."
mkdir -p /opt/log_server/python/logs
chown -R logserver:logserver /opt/log_server/python/logs

# 启动服务
echo "正在启动服务..."
systemctl start log_server
systemctl enable log_server

# 检查服务状态
echo "正在检查服务状态..."
if systemctl is-active --quiet log_server; then
    echo "服务已成功启动"
    echo "可以使用以下命令查看服务状态："
    echo "systemctl status log_server"
    echo "journalctl -u log_server -f"
else
    echo "服务启动失败，请检查日志："
    journalctl -u log_server -n 50
    exit 1
fi

# 显示服务信息
echo "
安装完成！

服务信息：
- HTTP服务端口: 8080
- TCP服务端口: 45860
- WebSocket端口: 8765

访问方式：
1. 通过服务端口访问：http://服务器IP:8080
2. 通过网站根目录访问：http://服务器IP/

常用命令：
- 启动服务: systemctl start log_server
- 停止服务: systemctl stop log_server
- 重启服务: systemctl restart log_server
- 查看状态: systemctl status log_server
- 查看日志: journalctl -u log_server -f

日志位置：
- 应用日志: /opt/log_server/python/logs/
- 系统日志: journalctl -u log_server

如果遇到问题，请检查以上日志文件。
"