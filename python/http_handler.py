import os
import json
import socket
import urllib.parse
from http.server import HTTPServer as BaseHTTPServer, SimpleHTTPRequestHandler
from logger_config import logger, LOG_DIR
from datetime import datetime

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
        if path == "/api/logs/sn-list":
            # 获取SN列表
            self.send_json_response(self.get_sn_list())
            return
        elif path.startswith("/api/logs/date-list/"):
            # 获取日期列表
            sn = path.replace("/api/logs/date-list/", "")
            self.send_json_response(self.get_date_list(sn))
            return
        elif path.startswith("/api/logs/content/"):
            # 获取日志内容
            log_path = path.replace("/api/logs/content/", "")
            self.view_log_content(log_path)
            return
        elif path == "/api/logs":
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
            log_path = path.replace("/api/logs/download/", "")
            self.download_log_file(log_path)
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

    def get_sn_list(self):
        """获取所有SN列表"""
        sn_list = []
        try:
            # 遍历日志目录
            for item in os.listdir(LOG_DIR):
                item_path = os.path.join(LOG_DIR, item)
                # 如果是目录，且不是default目录，则认为是SN目录
                if os.path.isdir(item_path) and item != 'default':
                    sn_list.append(item)
            sn_list.sort()  # 按字母顺序排序
            logger.info(f"找到 {len(sn_list)} 个SN目录")
        except Exception as e:
            logger.error(f"获取SN列表失败: {str(e)}")
        return sn_list

    def get_date_list(self, sn):
        """获取指定SN的日期列表"""
        date_list = []
        try:
            # 确定目标目录
            target_dir = os.path.join(LOG_DIR, 'default' if sn == 'default' else sn)
            logger.info(f"正在搜索日志目录: {target_dir}")
            
            if not os.path.exists(target_dir):
                logger.warning(f"目录不存在: {target_dir}")
                return date_list

            # 遍历目录中的日志文件
            for filename in os.listdir(target_dir):
                if filename.startswith('server.log'):
                    if filename == 'server.log':
                        # 当前日志文件
                        date_list.append(datetime.now().strftime('%Y-%m-%d'))
                    else:
                        # 历史日志文件，格式为 server.log.YYYY-MM-DD
                        date = filename.split('.')[-1]
                        date_list.append(date)
                    logger.info(f"找到日志文件: {filename}")
            
            # 按日期倒序排序，最新的在前
            date_list.sort(reverse=True)
            logger.info(f"在 {target_dir} 中找到 {len(date_list)} 个日志文件: {date_list}")
        except Exception as e:
            logger.error(f"获取日期列表失败: {str(e)}")
        return date_list

    def view_log_content(self, log_path):
        """查看日志内容"""
        # 构建完整的日志文件路径
        full_path = os.path.join(LOG_DIR, log_path)
        full_path = os.path.normpath(full_path)  # 规范化路径
        
        logger.info(f"请求查看日志文件: {full_path}")
        
        # 安全检查：确保路径在LOG_DIR内
        if not full_path.startswith(os.path.abspath(LOG_DIR)):
            logger.warning(f"尝试访问日志目录外的文件: {full_path}")
            self.send_error(403, "Access denied")
            return
            
        try:
            # 获取请求的日期
            requested_date = os.path.basename(full_path).replace('.log', '')
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # 如果是当日日志，使用server.log
            if requested_date == current_date:
                sn_dir = os.path.dirname(full_path)
                full_path = os.path.join(sn_dir, 'server.log')
                logger.info(f"当日日志，使用server.log: {full_path}")
            else:
                # 历史日志，使用server.log.YYYY-MM-DD格式
                sn_dir = os.path.dirname(full_path)
                full_path = os.path.join(sn_dir, f'server.log.{requested_date}')
                logger.info(f"历史日志，使用server.log.{requested_date}: {full_path}")
            
            if not os.path.exists(full_path):
                logger.error(f"日志文件不存在: {full_path}")
                self.send_error(404, "Log file not found")
                return
                
            if not os.access(full_path, os.R_OK):
                logger.error(f"无权限访问日志文件: {full_path}")
                self.send_error(403, "Permission denied")
                return

            # 获取文件大小
            file_size = os.path.getsize(full_path)
            logger.info(f"日志文件大小: {file_size} bytes")
            
            # 发送响应头
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Content-Length', str(file_size))
            self.end_headers()

            # 读取并发送文件内容
            with open(full_path, 'rb') as f:
                content = f.read()
                logger.info(f"成功读取日志内容，长度: {len(content)} bytes")
                self.wfile.write(content)
                logger.info("成功发送日志内容")
                    
        except Exception as e:
            logger.error(f"读取日志内容失败 {full_path}: {str(e)}")
            self.send_error(500, str(e))

    def get_log_list(self):
        logs = []
        try:
            # 确保使用绝对路径
            log_dir = os.path.abspath(LOG_DIR)
            logger.info(f"正在搜索日志目录: {log_dir}")
            
            if not os.path.exists(log_dir):
                logger.warning(f"日志目录不存在: {log_dir}")
                return logs
                
            # 遍历所有SN目录
            for sn_dir in os.listdir(log_dir):
                sn_path = os.path.join(log_dir, sn_dir)
                if not os.path.isdir(sn_path):
                    continue
                    
                # 遍历SN目录下的日志文件
                for filename in os.listdir(sn_path):
                    if filename.startswith('server.log'):
                        file_path = os.path.join(sn_path, filename)
                        try:
                            stat = os.stat(file_path)
                            date = filename.split('.')[-1] if filename != 'server.log' else datetime.now().strftime('%Y-%m-%d')
                            logs.append({
                                'name': f"{sn_dir}/{filename}",
                                'sn': sn_dir,
                                'date': date,
                                'size': stat.st_size,
                                'modified_time': int(stat.st_mtime)
                            })
                            logger.debug(f"找到日志文件: {filename} in {sn_dir}")
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

    def download_log_file(self, log_path):
        """处理日志下载请求"""
        try:
            # 规范化路径分隔符
            log_path = log_path.replace('\\', '/').strip('/')
            
            # 获取请求的日期和SN
            path_parts = log_path.split('/')
            if len(path_parts) != 2:
                logger.error(f"无效的日志路径格式: {log_path}")
                self.send_error(400, "Invalid log path format")
                return
                
            sn_dir, log_file = path_parts
            requested_date = log_file.replace('.log', '')
            current_date = datetime.now().strftime('%Y-%m-%d')
            
            # 构建正确的日志文件路径
            sn_dir_path = os.path.join(LOG_DIR, sn_dir)
            
            # 如果是当日日志，使用server.log
            if requested_date == current_date:
                full_path = os.path.join(sn_dir_path, 'server.log')
                logger.info(f"当日日志，使用server.log: {full_path}")
            else:
                # 历史日志，使用server.log.YYYY-MM-DD格式
                full_path = os.path.join(sn_dir_path, f'server.log.{requested_date}')
                logger.info(f"历史日志，使用server.log.{requested_date}: {full_path}")
            
            # 规范化路径
            full_path = os.path.normpath(full_path)
            
            # 安全检查：确保路径在LOG_DIR内
            if not os.path.abspath(full_path).startswith(os.path.abspath(LOG_DIR)):
                logger.warning(f"尝试访问日志目录外的文件: {full_path}")
                self.send_error(403, "Access denied")
                return
            
            if not os.path.exists(full_path):
                logger.error(f"日志文件不存在: {full_path}")
                self.send_error(404, "Log file not found")
                return
                
            if not os.access(full_path, os.R_OK):
                logger.error(f"无权限访问日志文件: {full_path}")
                self.send_error(403, "Permission denied")
                return

            # 获取文件大小
            file_size = os.path.getsize(full_path)
            logger.info(f"日志文件大小: {file_size} bytes")
            
            # 准备响应头
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Access-Control-Allow-Origin', '*')
            
            # 构建下载文件名
            download_filename = f"{sn_dir}_{requested_date}.log"
            encoded_filename = urllib.parse.quote(download_filename)
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
            with open(full_path, 'rb') as f:
                try:
                    chunk_size = 8192  # 8KB chunks
                    while True:
                        chunk = f.read(chunk_size)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    logger.info(f"成功发送日志文件: {download_filename}")
                except (ConnectionAbortedError, BrokenPipeError) as e:
                    logger.warning(f"客户端中断了下载: {str(e)}")
                    return
                except Exception as e:
                    logger.error(f"发送日志文件失败 {full_path}: {str(e)}")
                    if not self.wfile.closed:
                        self.send_error(500, "Internal Server Error")
                    return

        except Exception as e:
            logger.error(f"处理日志下载请求时出错: {str(e)}")
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