import asyncio
import websockets
import socket
import threading
import json
import logging
import time
import os
from datetime import datetime
from queue import Queue
from concurrent.futures import ThreadPoolExecutor
from logging.handlers import TimedRotatingFileHandler
from http.server import HTTPServer, SimpleHTTPRequestHandler
import mimetypes
import urllib.parse

# 创建日志目录
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 配置日志
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

# 创建消息队列和事件循环
message_queue = Queue()
loop = asyncio.new_event_loop()
executor = ThreadPoolExecutor(max_workers=1)

class TCPClient:
    def __init__(self, conn, addr_str):
        self.conn = conn
        self.addr_str = addr_str
        self.wifi_name = None
        self.sn = None
        self.display_name = addr_str
        self.is_alive = True

    def update_info(self, wifi_name, sn):
        """更新客户端信息"""
        self.wifi_name = wifi_name
        self.sn = sn
        self.display_name = f"{sn}" if sn else self.addr_str
        logger.info(f"客户端信息已更新: {self.display_name}")

    def close(self):
        """安全关闭连接"""
        try:
            self.conn.close()
        except:
            pass
        finally:
            self.is_alive = False

tcp_clients = {}  # 存储TCP客户端 {addr_str: TCPClient}
websocket_clients = set()  # 存储WebSocket客户端

def addr_to_str(addr):
    """将地址元组转换为字符串"""
    return f"{addr[0]},{addr[1]}"

def get_current_time():
    """获取当前格式化的时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def format_message(addr, content, current_time=None):
    """格式化消息，统一添加时间戳"""
    if current_time is None:
        current_time = get_current_time()
    if addr == "系统":
        return f"[{current_time}] {content}"
    return f"[{current_time}] [{addr}]: {content}"

async def websocket_server(websocket, path):
    websocket_clients.add(websocket)
    try:
        # 发送当前连接状态
        await notify_web_clients({
            "type": "client_update",
            "clients": [client.display_name for client in tcp_clients.values()]
        })
        
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            logger.info(f"收到WebSocket消息: {data}")
            
            if data["type"] == "init":
                # 响应初始化请求
                await notify_web_clients({
                    "type": "client_update",
                    "clients": [client.display_name for client in tcp_clients.values()]
                })
            elif data["type"] == "send":
                target_name = data["addr"]
                msg = data["message"]
                current_time = get_current_time()
                
                # 查找目标客户端
                target_client = None
                for client in tcp_clients.values():
                    if client.display_name == target_name:
                        target_client = client
                        break

                if target_client and target_client.is_alive:
                    try:
                        target_client.conn.sendall(msg.encode())
                        logger.info(f"发送消息到TCP客户端 {target_name}: {msg}")
                        await notify_web_clients({
                            "type": "message",
                            "addr": "系统",
                            "data": format_message("系统", f"发送 [{target_name}]: {msg}", current_time)
                        })
                    except Exception as e:
                        logger.error(f"发送消息到TCP客户端 {target_name} 失败: {str(e)}")
                        target_client.is_alive = False
                        await notify_web_clients({
                            "type": "message",
                            "addr": "系统",
                            "data": format_message("系统", f"发送失败: 客户端可能已断开，消息内容: {msg}", current_time)
                        })
                        await notify_web_clients({
                            "type": "client_update", 
                            "clients": [c.display_name for c in tcp_clients.values()]
                        })
                else:
                    logger.warning(f"目标TCP客户端不存在或已断开: {target_name}")
                    await notify_web_clients({
                        "type": "message",
                        "addr": "系统",
                        "data": format_message("系统", f"发送失败: 客户端不存在或已断开，目标客户端: [{target_name}]", current_time)
                    })
    except Exception as e:
        logger.error(f"WebSocket错误: {str(e)}")
    finally:
        websocket_clients.remove(websocket)
        logger.info("WebSocket客户端断开连接")

async def notify_web_clients(data):
    """ 将TCP数据推送给所有WebSocket客户端 """
    if websocket_clients:
        message = json.dumps(data)
        try:
            await asyncio.wait([ws.send(message) for ws in websocket_clients])
            logger.info(f"通知所有Web客户端: {message}")
        except Exception as e:
            logger.error(f"通知Web客户端失败: {e}")

def process_message_queue():
    """处理消息队列的后台任务"""
    while True:
        message = message_queue.get()
        if message is None:
            break
        asyncio.run_coroutine_threadsafe(notify_web_clients(message), loop)

def parse_client_info(message):
    """解析客户端连接消息中的信息"""
    try:
        # 解析Wifi名称
        wifi_start = message.find("Wifi :") + 6
        wifi_end = message.find(",", wifi_start)
        wifi_name = message[wifi_start:wifi_end].strip() if wifi_start > 5 else None

        # 解析SN号
        sn_start = message.find("SN:") + 3
        sn_end = message.find(",", sn_start)
        sn = message[sn_start:sn_end].strip() if sn_start > 2 else None

        logger.info(f"解析到客户端信息 - Wifi: {wifi_name}, SN: {sn}")
        return wifi_name, sn
    except Exception as e:
        logger.error(f"解析客户端信息失败: {str(e)}")
        return None, None

def handle_tcp_client(conn, addr):
    """ 处理TCP客户端数据接收 """
    addr_str = addr_to_str(addr)
    client = TCPClient(conn, addr_str)
    tcp_clients[addr_str] = client
    current_time = get_current_time()
    logger.info(f"新的TCP客户端连接: {addr_str}")
    
    # 发送连接通知
    message_queue.put({
        "type": "message",
        "addr": "系统",
        "data": format_message("系统", f"新客户端连接: {addr_str}", current_time)
    })
    message_queue.put({"type": "client_update", "clients": [c.display_name for c in tcp_clients.values()]})
    
    try:
        while client.is_alive:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                current_time = get_current_time()
                decoded_data = data.decode()

                # 检查是否是首次连接消息
                if "Wifi :" in decoded_data and "SN:" in decoded_data:
                    wifi_name, sn = parse_client_info(decoded_data)
                    if wifi_name and sn:
                        client.update_info(wifi_name, sn)
                        # 更新客户端列表并发送通知
                        message_queue.put({
                            "type": "message",
                            "addr": "系统",
                            "data": format_message("系统", f"识别到设备信息 - Wifi: {wifi_name}, SN: {sn}", current_time)
                        })
                        message_queue.put({"type": "client_update", "clients": [c.display_name for c in tcp_clients.values()]})
                        continue  # 跳过这条连接消息的显示

                # 发送普通消息
                msg = {
                    "type": "message",
                    "addr": client.display_name,
                    "data": format_message(client.display_name, decoded_data, current_time)
                }
                message_queue.put(msg)
                logger.info(f"收到TCP客户端 {client.display_name} 消息: {decoded_data}")
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"接收TCP客户端 {client.display_name} 数据时出错: {str(e)}")
                break
    finally:
        client.close()
        if addr_str in tcp_clients:
            current_time = get_current_time()
            del tcp_clients[addr_str]
            logger.info(f"TCP客户端断开连接: {addr_str}")
            # 发送断开连接通知
            message_queue.put({
                "type": "message",
                "addr": "系统",
                "data": format_message("系统", f"客户端断开连接: {addr_str}", current_time)
            })
            message_queue.put({"type": "client_update", "clients": list(tcp_clients.keys())})

def tcp_server():
    """ 启动TCP服务器 """
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 45860))
    server.listen(15)
    server.settimeout(1)  # 设置超时，使accept不会永久阻塞
    logger.info("TCP服务器启动在 0.0.0.0:45860")
    
    while True:
        try:
            conn, addr = server.accept()
            conn.settimeout(5)  # 设置socket超时
            threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()
        except socket.timeout:
            continue
        except Exception as e:
            logger.error(f"接受TCP连接时出错: {str(e)}")

class LogHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=".", **kwargs)

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
            for filename in os.listdir(LOG_DIR):
                if filename.endswith('.log'):
                    file_path = os.path.join(LOG_DIR, filename)
                    try:
                        logs.append({
                            'name': filename,
                            'size': os.path.getsize(file_path),
                            'mtime': os.path.getmtime(file_path)
                        })
                    except OSError as e:
                        logger.error(f"获取日志文件信息失败 {filename}: {str(e)}")
            # 按修改时间排序，最新的在前
            logs.sort(key=lambda x: x['mtime'], reverse=True)
        except Exception as e:
            logger.error(f"获取日志列表失败: {str(e)}")
        return logs

    def view_log_file(self, log_name):
        """处理日志查看请求"""
        log_path = os.path.join(LOG_DIR, log_name)
        try:
            # 检查文件是否存在和可访问
            if not os.path.exists(log_path):
                self.send_error(404, "Log file not found")
                return
            if not os.access(log_path, os.R_OK):
                self.send_error(403, "Permission denied")
                return

            # 获取文件大小
            file_size = os.path.getsize(log_path)
            
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
        log_path = os.path.join(LOG_DIR, log_name)
        try:
            # 检查文件是否存在和可访问
            if not os.path.exists(log_path):
                self.send_error(404, "Log file not found")
                return
            if not os.access(log_path, os.R_OK):
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

def check_port_available(port):
    """检查端口是否可用"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(('0.0.0.0', port))
        sock.close()
        return True
    except OSError:
        return False

def start_http_server():
    """启动HTTP服务器"""
    port = 8080
    retries = 3
    
    # 检查端口是否被占用
    if not check_port_available(port):
        logger.error(f"HTTP服务器端口 {port} 已被占用")
        # 尝试其他端口
        for p in range(port + 1, port + retries + 1):
            if check_port_available(p):
                port = p
                logger.warning(f"使用备用端口 {port}")
                break
        else:
            logger.critical(f"无法启动HTTP服务器：所有端口({port}-{port+retries})都被占用")
            return
    
    try:
        http_server = HTTPServer(('0.0.0.0', port), LogHandler)
        logger.info(f"HTTP服务器启动在 http://localhost:{port}")
        http_server.serve_forever()
    except Exception as e:
        logger.critical(f"HTTP服务器启动失败: {str(e)}")
        raise

if __name__ == "__main__":
    try:
        logger.info("服务器启动...")
        
        # 启动消息处理线程
        message_processor = threading.Thread(target=process_message_queue, daemon=True)
        message_processor.start()

        # 启动TCP服务器
        tcp_thread = threading.Thread(target=tcp_server, daemon=True)
        tcp_thread.start()

        # 启动HTTP服务器
        http_thread = threading.Thread(target=start_http_server, daemon=True)
        http_thread.start()

        # 设置事件循环
        asyncio.set_event_loop(loop)
        
        # 启动WebSocket服务器
        logger.info("WebSocket服务器启动在 ws://localhost:8765")
        start_server = websockets.serve(websocket_server, "0.0.0.0", 8765)
        loop.run_until_complete(start_server)
        
        # 等待所有线程启动
        time.sleep(1)
        
        # 检查线程状态
        if not http_thread.is_alive():
            raise Exception("HTTP服务器启动失败")
        if not tcp_thread.is_alive():
            raise Exception("TCP服务器启动失败")
        if not message_processor.is_alive():
            raise Exception("消息处理线程启动失败")
            
        loop.run_forever()
    except Exception as e:
        logger.critical(f"服务器启动失败: {str(e)}")
        raise
