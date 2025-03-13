import os
import json
import socket
import urllib.parse
from http.server import HTTPServer as BaseHTTPServer, SimpleHTTPRequestHandler
from logger_config import logger, LOG_DIR

class LogHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # 获取项目根目录
        self.current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        super().__init__(*args, directory=self.current_dir, **kwargs)

    def translate_path(self, path):
        """重写路径转换方法，处理静态文件和日志文件"""
        # 首先尝试查找静态文件
        static_path = super().translate_path(path)
        if os.path.exists(static_path):
            return static_path
            
        # 如果是日志相关的API请求，不需要进行路径转换
        if path.startswith('/api/logs'):
            return path
            
        return static_path

    def do_GET(self):
        # 解析URL
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path

        # 处理API请求
        if path == "/api/logs":
            # 获取日志列表
            self.send_json_response(self.get_log_list())
            return
        elif path.startswith("/api/logs/view/"):
            # 查看日志内容
            log_name = os.path.basename(path.replace("/api/logs/view/", ""))
            self.view_log_file(log_name)
            return
        elif path.startswith("/api/logs/download/"):
            # 下载日志文件
            log_name = os.path.basename(path.replace("/api/logs/download/", ""))
            self.download_log_file(log_name)
            return

        # 处理静态文件请求
        if path == "/" or path == "":
            self.path = "/index.html"
        elif path in ["/index.html", "/logs.html"]:
            self.path = path
        
        try:
            super().do_GET()
        except Exception as e:
            logger.error(f"处理HTTP请求出错: {str(e)}")
            self.send_error(404, str(e))

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')  # 允许跨域访问
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def get_log_list(self):
        logs = []
        try:
            # 确保使用绝对路径
            log_dir = os.path.abspath(LOG_DIR)
            logger.info(f"正在搜索日志目录: {log_dir}")
            
            if not os.path.exists(log_dir):
                logger.warning(f"日志目录不存在: {log_dir}")
                return logs
                
            for filename in os.listdir(log_dir):
                if filename.endswith('.log'):
                    file_path = os.path.join(log_dir, filename)
                    try:
                        stat = os.stat(file_path)
                        logs.append({
                            'name': filename,
                            'size': stat.st_size,
                            'modified_time': int(stat.st_mtime)
                        })
                        logger.debug(f"找到日志文件: {filename}")
                    except OSError as e:
                        logger.error(f"获取日志文件信息失败 {filename}: {str(e)}")
            # 按修改时间排序，最新的在前
            logs.sort(key=lambda x: x['modified_time'], reverse=True)
            logger.info(f"共找到 {len(logs)} 个日志文件")
        except Exception as e:
            logger.error(f"获取日志列表失败: {str(e)}")
        return logs

    def view_log_file(self, log_name):
        """处理日志查看请求"""
        log_path = os.path.abspath(os.path.join(LOG_DIR, log_name))
        logger.info(f"尝试访问日志文件: {log_path}")
        
        # 验证路径，确保不会访问到日志目录之外的文件
        if not log_path.startswith(os.path.abspath(LOG_DIR)):
            logger.warning(f"尝试访问日志目录外的文件: {log_path}")
            self.send_error(403, "Access denied")
            return
            
        try:
            # 检查文件是否存在和可访问
            if not os.path.exists(log_path):
                logger.error(f"日志文件不存在: {log_path}")
                self.send_error(404, "Log file not found")
                return
            if not os.access(log_path, os.R_OK):
                logger.error(f"无权限访问日志文件: {log_path}")
                self.send_error(403, "Permission denied")
                return

            # 获取文件大小
            file_size = os.path.getsize(log_path)
            logger.info(f"日志文件大小: {file_size} bytes")
            
            # 准备响应头
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Expires', '0')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()

            # 分块读取并发送文件内容
            with open(log_path, 'rb') as f:
                try:
                    chunk_size = 8192  # 8KB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (ConnectionAbortedError, BrokenPipeError) as e:
                    logger.warning(f"客户端中断了查看: {str(e)}")
                    return
                except Exception as e:
                    logger.error(f"发送日志内容失败 {log_path}: {str(e)}")
                    if not self.wfile.closed:
                        self.send_error(500, "Internal Server Error")
                    return

        except Exception as e:
            logger.error(f"处理日志查看请求时出错 {log_path}: {str(e)}")
            try:
                error_msg = str(e).encode('ascii', 'replace').decode('ascii')
                self.send_error(500, error_msg)
            except Exception as e2:
                logger.error(f"发送错误响应时出错: {str(e2)}")
                self.send_error(500, "Internal Server Error")

    def download_log_file(self, log_name):
        """处理日志下载请求"""
        log_path = os.path.abspath(os.path.join(LOG_DIR, log_name))
        # 验证路径，确保不会访问到日志目录之外的文件
        if not log_path.startswith(os.path.abspath(LOG_DIR)):
            self.send_error(403, "Access denied")
            return
            
        try:
            # 检查文件是否存在和可访问
            if not os.path.exists(log_path):
                logger.error(f"日志文件不存在: {log_path}")
                self.send_error(404, "Log file not found")
                return
            if not os.access(log_path, os.R_OK):
                logger.error(f"无权限访问日志文件: {log_path}")
                self.send_error(403, "Permission denied")
                return

            # 获取文件大小
            file_size = os.path.getsize(log_path)
            
            # 准备响应头
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-Type', 'application/octet-stream')
            
            # 对文件名进行URL编码，避免中文问题
            encoded_filename = urllib.parse.quote(log_name)
            self.send_header('Content-Disposition', f'attachment; filename="{encoded_filename}"')
            
            # 添加下载相关头
            self.send_header('Content-Description', 'File Transfer')
            self.send_header('Content-Transfer-Encoding', 'binary')
            self.send_header('Expires', '0')
            self.send_header('Cache-Control', 'must-revalidate')
            self.send_header('Pragma', 'public')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()

            # 分块读取并发送文件内容
            with open(log_path, 'rb') as f:
                try:
                    chunk_size = 8192  # 8KB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                except (ConnectionAbortedError, BrokenPipeError) as e:
                    logger.warning(f"客户端中断了下载: {str(e)}")
                    return
                except Exception as e:
                    logger.error(f"发送日志文件失败 {log_path}: {str(e)}")
                    if not self.wfile.closed:
                        self.send_error(500, "Internal Server Error")
                    return

        except Exception as e:
            logger.error(f"处理日志下载请求时出错 {log_path}: {str(e)}")
            try:
                error_msg = str(e).encode('ascii', 'replace').decode('ascii')
                self.send_error(500, error_msg)
            except Exception as e2:
                logger.error(f"发送错误响应时出错: {str(e2)}")
                self.send_error(500, "Internal Server Error")

class CustomHTTPServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port

    def check_port_available(self):
        """检查端口是否可用"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind((self.host, self.port))
            sock.close()
            return True
        except OSError:
            return False

    def start(self):
        """启动HTTP服务器"""
        retries = 3
        
        # 检查端口是否被占用
        if not self.check_port_available():
            logger.error(f"HTTP服务器端口 {self.port} 已被占用")
            # 尝试其他端口
            for p in range(self.port + 1, self.port + retries + 1):
                if self.check_port_available():
                    self.port = p
                    logger.warning(f"使用备用端口 {self.port}")
                    break
            else:
                logger.critical(f"无法启动HTTP服务器：所有端口({self.port}-{self.port+retries})都被占用")
                return
        
        try:
            http_server = BaseHTTPServer((self.host, self.port), LogHandler)
            logger.info(f"HTTP服务器启动在 http://{self.host}:{self.port}")
            http_server.serve_forever()
        except Exception as e:
            logger.critical(f"HTTP服务器启动失败: {str(e)}")
            raise 