import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime

# 创建日志目录
LOG_DIR = os.path.join(os.path.dirname(__file__), "logs")
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# ANSI颜色代码
COLORS = {
    'INFO': '\033[92m',     # 绿色
    'WARNING': '\033[93m',  # 黄色
    'ERROR': '\033[91m',    # 红色
    'CRITICAL': '\033[95m', # 紫色
    'DEBUG': '\033[94m',    # 蓝色
    'RESET': '\033[0m'      # 重置
}

class ColoredFormatter(logging.Formatter):
    def format(self, record):
        original_msg = record.msg
        if record.levelname in COLORS:
            record.msg = f"{COLORS[record.levelname]}{record.msg}{COLORS['RESET']}"
        formatted_msg = super().format(record)
        record.msg = original_msg
        return formatted_msg

class SNBasedLogger:
    def __init__(self):
        self.loggers = {}  # 存储每个SN对应的logger
        
    def get_logger(self, sn=None):
        if not sn:
            return setup_default_logger()
            
        if sn not in self.loggers:
            # 为这个SN创建新的logger
            logger = logging.getLogger(f'tcp_server_{sn}')
            logger.setLevel(logging.INFO)
            
            # 创建该SN的日志目录
            sn_log_dir = os.path.join(LOG_DIR, sn)
            if not os.path.exists(sn_log_dir):
                os.makedirs(sn_log_dir)
            
            # 使用固定的日志文件名
            log_file = os.path.join(sn_log_dir, "server.log")
            
            # 文件处理器
            file_handler = TimedRotatingFileHandler(
                log_file,
                when="midnight",
                interval=1,
                backupCount=30,
                encoding="utf-8"
            )
            file_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            
            # 添加控制台处理器
            console_handler = setup_console_handler()
            logger.addHandler(console_handler)
            
            self.loggers[sn] = logger
            
        return self.loggers[sn]

def setup_console_handler():
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')
    console_handler.setFormatter(console_formatter)
    return console_handler

def setup_default_logger():
    logger = logging.getLogger('tcp_server')
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # 添加控制台处理器
        console_handler = setup_console_handler()
        logger.addHandler(console_handler)
        
        # 默认文件处理器
        default_log_dir = os.path.join(LOG_DIR, "default")
        if not os.path.exists(default_log_dir):
            os.makedirs(default_log_dir)
            
        log_file = os.path.join(default_log_dir, "server.log")
        file_handler = TimedRotatingFileHandler(
            log_file,
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8"
        )
        file_formatter = ColoredFormatter('%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s')
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)
    
    return logger

# 初始化日志管理器
sn_logger = SNBasedLogger()
# 获取默认logger用于向后兼容
logger = setup_default_logger() 