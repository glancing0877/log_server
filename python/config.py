import os

# 服务器配置
HTTP_HOST = '0.0.0.0'  # 监听所有网络接口
HTTP_PORT = 8080
TCP_HOST = '0.0.0.0'
TCP_PORT = 45860
WEBSOCKET_HOST = '0.0.0.0'
WEBSOCKET_PORT = 8765

# 日志配置
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(BASE_DIR, 'python', 'logs')
LOG_BACKUP_COUNT = 30
LOG_ENCODING = 'utf-8'

# 静态文件配置
STATIC_DIR = os.path.join(BASE_DIR, 'static')
HTML_DIR = BASE_DIR 