import asyncio
import websockets
import socket
import threading
import json
import logging
import time
from datetime import datetime
from queue import Queue
from concurrent.futures import ThreadPoolExecutor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 创建消息队列和事件循环
message_queue = Queue()
loop = asyncio.new_event_loop()
executor = ThreadPoolExecutor(max_workers=1)

class TCPClient:
    def __init__(self, conn, addr_str):
        self.conn = conn
        self.addr_str = addr_str
        self.is_alive = True

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
            "clients": list(tcp_clients.keys())
        })
        
        while True:
            message = await websocket.recv()
            data = json.loads(message)
            logging.info(f"收到WebSocket消息: {data}")
            
            if data["type"] == "init":
                # 响应初始化请求
                await notify_web_clients({
                    "type": "client_update",
                    "clients": list(tcp_clients.keys())
                })
            elif data["type"] == "send":
                addr = data["addr"]
                msg = data["message"]
                current_time = get_current_time()
                if addr in tcp_clients and tcp_clients[addr].is_alive:
                    try:
                        tcp_clients[addr].conn.sendall(msg.encode())
                        logging.info(f"消息{addr}: {msg}")
                        # 发送消息确认给Web客户端
                        await notify_web_clients({
                            "type": "message",
                            "addr": "系统",
                            "data": format_message("系统", f"发送 [{addr}]: {msg}", current_time)
                        })
                    except Exception as e:
                        logging.error(f"发送消息到TCP客户端失败: {e}")
                        tcp_clients[addr].is_alive = False
                        await notify_web_clients({
                            "type": "message",
                            "addr": "系统",
                            "data": format_message("系统", f"发送失败: 客户端可能已断开，消息内容: {msg}", current_time)
                        })
                        await notify_web_clients({"type": "client_update", "clients": list(tcp_clients.keys())})
                else:
                    logging.warning(f"目标TCP客户端不存在或已断开: {addr}")
                    await notify_web_clients({
                        "type": "message",
                        "addr": "系统",
                        "data": format_message("系统", f"发送失败: 客户端不存在或已断开，目标客户端: [{addr}]", current_time)
                    })
    except Exception as e:
        logging.error(f"WebSocket错误: {e}")
    finally:
        websocket_clients.remove(websocket)
        logging.info("WebSocket客户端断开连接")

async def notify_web_clients(data):
    """ 将TCP数据推送给所有WebSocket客户端 """
    if websocket_clients:
        message = json.dumps(data)
        try:
            await asyncio.wait([ws.send(message) for ws in websocket_clients])
            logging.info(f"通知所有Web客户端: {message}")
        except Exception as e:
            logging.error(f"通知Web客户端失败: {e}")

def process_message_queue():
    """处理消息队列的后台任务"""
    while True:
        message = message_queue.get()
        if message is None:
            break
        asyncio.run_coroutine_threadsafe(notify_web_clients(message), loop)

def handle_tcp_client(conn, addr):
    """ 处理TCP客户端数据接收 """
    addr_str = addr_to_str(addr)
    client = TCPClient(conn, addr_str)
    tcp_clients[addr_str] = client
    current_time = get_current_time()
    logging.info(f"新的TCP客户端连接: {addr_str}")
    
    # 发送连接通知
    message_queue.put({
        "type": "message",
        "addr": "系统",
        "data": format_message("系统", f"新客户端连接: {addr_str}", current_time)
    })
    message_queue.put({"type": "client_update", "clients": list(tcp_clients.keys())})
    
    try:
        while client.is_alive:
            try:
                data = conn.recv(1024)
                if not data:
                    break
                current_time = get_current_time()
                msg = {
                    "type": "message",
                    "addr": addr_str,
                    "data": format_message(addr_str, data.decode(), current_time)
                }
                message_queue.put(msg)
                logging.info(f"收到TCP客户端消息: {msg}")
            except socket.timeout:
                continue
            except Exception as e:
                logging.error(f"接收TCP客户端数据时出错: {e}")
                break
    finally:
        client.close()
        if addr_str in tcp_clients:
            current_time = get_current_time()
            del tcp_clients[addr_str]
            logging.info(f"TCP客户端断开连接: {addr_str}")
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
    logging.info("TCP服务器启动在 0.0.0.0:45860")
    
    while True:
        try:
            conn, addr = server.accept()
            conn.settimeout(5)  # 设置socket超时
            threading.Thread(target=handle_tcp_client, args=(conn, addr), daemon=True).start()
        except socket.timeout:
            continue
        except Exception as e:
            logging.error(f"接受TCP连接时出错: {e}")

if __name__ == "__main__":
    # 启动消息处理线程
    message_processor = threading.Thread(target=process_message_queue, daemon=True)
    message_processor.start()

    # 启动TCP服务器
    threading.Thread(target=tcp_server, daemon=True).start()

    # 设置事件循环
    asyncio.set_event_loop(loop)
    
    # 启动WebSocket服务器
    logging.info("WebSocket服务器启动在 0.0.0.0:8765")
    start_server = websockets.serve(websocket_server, "0.0.0.0", 8765)
    loop.run_until_complete(start_server)
    loop.run_forever()
