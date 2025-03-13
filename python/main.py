import asyncio
import threading
from queue import Queue
from logger_config import logger
from tcp_handler import TCPServer
from websocket_handler import WebSocketServer
from http_handler import CustomHTTPServer

def process_message_queue(message_queue):
    """处理消息队列的后台任务"""
    while True:
        message = message_queue.get()
        if message is None:
            break
        asyncio.run_coroutine_threadsafe(ws_server.notify_web_clients(message), loop)

if __name__ == "__main__":
    try:
        logger.info("服务器启动...")
        
        # 创建消息队列
        message_queue = Queue()
        
        # 创建事件循环
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # 创建TCP服务器
        tcp_server = TCPServer(message_queue=message_queue)
        
        # 创建WebSocket服务器
        ws_server = WebSocketServer(tcp_server=tcp_server)
        
        # 创建HTTP服务器
        http_server = CustomHTTPServer()

        # 启动消息处理线程
        message_processor = threading.Thread(
            target=process_message_queue,
            args=(message_queue,),
            daemon=True
        )
        message_processor.start()

        # 启动TCP服务器线程
        tcp_thread = threading.Thread(
            target=tcp_server.start,
            daemon=True
        )
        tcp_thread.start()

        # 启动HTTP服务器线程
        http_thread = threading.Thread(
            target=http_server.start,
            daemon=True
        )
        http_thread.start()

        # 启动WebSocket服务器
        loop.run_until_complete(ws_server.start())
        
        # 等待所有线程启动
        import time
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