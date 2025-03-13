import logging
import os
from logging.handlers import TimedRotatingFileHandler

# 创建日志目录
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def setup_logger():
    logger = logging.getLogger('tcp_server')
    logger.setLevel(logging.INFO)
    
    # ANSI颜色代码
    COLORS = {
        'INFO': '\033[92m',     # 绿色
        'WARNING': '\033[93m',  # 黄色
        'ERROR': '\033[91m',    # 红色
        'CRITICAL': '\033[95m', # 紫色
        'DEBUG': '\033[94m',    # 蓝色
        'RESET': '\033[0m'      # 重置
    }
    
    # 自定义格式化器
    class ColoredFormatter(logging.Formatter):
        def format(self, record):
            # 保存原始消息
            original_msg = record.msg
            # 添加颜色到消息
            if record.levelname in COLORS:
                record.msg = f"{COLORS[record.levelname]}{record.msg}{COLORS['RESET']}"
            # 格式化消息
            formatted_msg = super().format(record)
            # 恢复原始消息
            record.msg = original_msg
            return formatted_msg
    
    # 控制台处理器
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # 文件处理器 - 按天轮换
    log_file = os.path.join(LOG_DIR, "tcp_server.log")
    file_handler = TimedRotatingFileHandler(
        log_file,
        when="midnight",
        interval=1,
        backupCount=30,  # 保留30天的日志
        encoding="utf-8"
    )
    file_handler.suffix = "%Y-%m-%d.log"
    file_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    return logger

# 初始化日志
logger = setup_logger() 