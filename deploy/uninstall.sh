#!/bin/bash

# 检查是否以root权限运行
if [ "$EUID" -ne 0 ]; then 
    echo "请使用root权限运行此脚本"
    echo "使用方法: sudo bash uninstall.sh"
    exit 1
fi

echo "开始卸载日志服务器..."

# 停止并禁用服务
echo "正在停止服务..."
systemctl stop log_server
systemctl disable log_server

# 删除服务文件
echo "正在删除服务文件..."
rm -f /etc/systemd/system/log_server.service
systemctl daemon-reload

# 删除防火墙规则
echo "正在删除防火墙规则..."
if command -v ufw >/dev/null 2>&1; then
    ufw delete allow 8080/tcp
    ufw delete allow 45860/tcp
    ufw delete allow 8765/tcp
    echo "防火墙规则已删除"
fi

# 询问是否删除数据
read -p "是否删除所有数据和日志文件？(y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "正在删除数据目录..."
    rm -rf /opt/log_server
    echo "正在删除服务用户..."
    userdel logserver
    echo "所有数据已删除"
else
    echo "保留数据目录: /opt/log_server"
fi

echo "卸载完成！" 