import socket
import threading
from datetime import datetime
from queue import Queue
from logger_config import logger

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

class TCPServer:
    def __init__(self, host="0.0.0.0", port=45860, message_queue=None):
        self.host = host
        self.port = port
        self.message_queue = message_queue
        self.tcp_clients = {}  # 存储TCP客户端 {addr_str: TCPClient}

    def handle_tcp_client(self, conn, addr):
        """ 处理TCP客户端数据接收 """
        addr_str = addr_to_str(addr)
        client = TCPClient(conn, addr_str)
        self.tcp_clients[addr_str] = client
        current_time = get_current_time()
        logger.info(f"新的TCP客户端连接: {addr_str}")
        
        # 发送连接通知
        self.message_queue.put({
            "type": "message",
            "addr": "系统",
            "data": format_message("系统", f"新客户端连接: {addr_str}", current_time)
        })
        self.message_queue.put({"type": "client_update", "clients": [c.display_name for c in self.tcp_clients.values()]})
        
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
                            self.message_queue.put({
                                "type": "message",
                                "addr": "系统",
                                "data": format_message("系统", f"识别到设备信息 - Wifi: {wifi_name}, SN: {sn}", current_time)
                            })
                            self.message_queue.put({"type": "client_update", "clients": [c.display_name for c in self.tcp_clients.values()]})
                            continue  # 跳过这条连接消息的显示

                    # 发送普通消息
                    msg = {
                        "type": "message",
                        "addr": client.display_name,
                        "data": format_message(client.display_name, decoded_data, current_time)
                    }
                    self.message_queue.put(msg)
                    logger.info(f"收到TCP客户端 {client.display_name} 消息: {decoded_data}")
                except socket.timeout:
                    continue
                except Exception as e:
                    logger.error(f"接收TCP客户端 {client.display_name} 数据时出错: {str(e)}")
                    break
        finally:
            client.close()
            if addr_str in self.tcp_clients:
                current_time = get_current_time()
                del self.tcp_clients[addr_str]
                logger.info(f"TCP客户端断开连接: {addr_str}")
                # 发送断开连接通知
                self.message_queue.put({
                    "type": "message",
                    "addr": "系统",
                    "data": format_message("系统", f"客户端断开连接: {addr_str}", current_time)
                })
                self.message_queue.put({"type": "client_update", "clients": [c.display_name for c in self.tcp_clients.values()]})

    def start(self):
        """ 启动TCP服务器 """
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind((self.host, self.port))
        server.listen(15)
        server.settimeout(1)  # 设置超时，使accept不会永久阻塞
        logger.info(f"TCP服务器启动在 {self.host}:{self.port}")
        
        while True:
            try:
                conn, addr = server.accept()
                conn.settimeout(5)  # 设置socket超时
                threading.Thread(target=self.handle_tcp_client, args=(conn, addr), daemon=True).start()
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"接受TCP连接时出错: {str(e)}")

    def get_client_by_display_name(self, display_name):
        """根据显示名称获取客户端"""
        for client in self.tcp_clients.values():
            if client.display_name == display_name:
                return client
        return None 