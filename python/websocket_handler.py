import asyncio
import json
import websockets
from logger_config import logger

class WebSocketServer:
    def __init__(self, host="0.0.0.0", port=8765, tcp_server=None):
        self.host = host
        self.port = port
        self.tcp_server = tcp_server
        self.websocket_clients = set()
        self.loop = None

    async def notify_web_clients(self, data):
        """ 将TCP数据推送给所有WebSocket客户端 """
        if self.websocket_clients:
            message = json.dumps(data)
            try:
                await asyncio.wait([ws.send(message) for ws in self.websocket_clients])
                logger.info(f"通知所有Web客户端: {message}")
            except Exception as e:
                logger.error(f"通知Web客户端失败: {e}")

    async def handle_websocket(self, websocket, path):
        self.websocket_clients.add(websocket)
        try:
            # 发送当前连接状态
            await self.notify_web_clients({
                "type": "client_update",
                "clients": [client.display_name for client in self.tcp_server.tcp_clients.values()]
            })
            
            while True:
                message = await websocket.recv()
                data = json.loads(message)
                logger.info(f"收到WebSocket消息: {data}")
                
                if data["type"] == "init":
                    # 响应初始化请求
                    await self.notify_web_clients({
                        "type": "client_update",
                        "clients": [client.display_name for client in self.tcp_server.tcp_clients.values()]
                    })
                elif data["type"] == "send":
                    target_name = data["addr"]
                    msg = data["message"]
                    
                    # 查找目标客户端
                    target_client = self.tcp_server.get_client_by_display_name(target_name)

                    if target_client and target_client.is_alive:
                        try:
                            target_client.conn.sendall(msg.encode())
                            logger.info(f"发送消息到TCP客户端 {target_name}: {msg}")
                            await self.notify_web_clients({
                                "type": "message",
                                "addr": "系统",
                                "data": f"[{target_name}]: {msg}"
                            })
                        except Exception as e:
                            logger.error(f"发送消息到TCP客户端 {target_name} 失败: {str(e)}")
                            target_client.is_alive = False
                            await self.notify_web_clients({
                                "type": "message",
                                "addr": "系统",
                                "data": f"发送失败: 客户端可能已断开，消息内容: {msg}"
                            })
                            await self.notify_web_clients({
                                "type": "client_update", 
                                "clients": [c.display_name for c in self.tcp_server.tcp_clients.values()]
                            })
                    else:
                        logger.warning(f"目标TCP客户端不存在或已断开: {target_name}")
                        await self.notify_web_clients({
                            "type": "message",
                            "addr": "系统",
                            "data": f"发送失败: 客户端不存在或已断开，目标客户端: [{target_name}]"
                        })
        except Exception as e:
            logger.error(f"WebSocket错误: {str(e)}")
        finally:
            self.websocket_clients.remove(websocket)
            logger.info("WebSocket客户端断开连接")

    async def start(self):
        """启动WebSocket服务器"""
        self.loop = asyncio.get_event_loop()
        server = await websockets.serve(self.handle_websocket, self.host, self.port)
        logger.info(f"WebSocket服务器启动在 ws://{self.host}:{self.port}")
        return server 