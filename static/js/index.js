// 服务器配置
const SERVER_HOST = window.location.hostname;  // 使用当前域名
const SERVER_PORT = 8080;
const WS_PORT = 8765;
const SERVER_URL = `http://${SERVER_HOST}:${SERVER_PORT}`;
const WS_URL = `ws://${SERVER_HOST}:${WS_PORT}`;

const ws = new WebSocket(WS_URL);
let shouldAutoScroll = true;
let messagesContainer = null;
let allMessages = [];  // 存储所有消息
let filteredClients = new Set();  // 存储选中的客户端

// ANSI颜色代码映射
const ANSI_COLORS = {
    '30': '#000000', // 黑
    '31': '#cd3131', // 红
    '32': '#0dbc79', // 绿
    '33': '#e5e510', // 黄
    '34': '#2472c8', // 蓝
    '35': '#bc3fbc', // 紫
    '36': '#11a8cd', // 青
    '37': '#e5e5e5', // 白
    '90': '#666666', // 亮黑
    '91': '#f14c4c', // 亮红
    '92': '#23d18b', // 亮绿
    '93': '#f5f543', // 亮黄
    '94': '#3b8eea', // 亮蓝
    '95': '#d670d6', // 亮紫
    '96': '#29b8db', // 亮青
    '97': '#ffffff'  // 亮白
};

// 解析ANSI颜色代码
function parseAnsiColor(text) {
    const regex = /\u001b\[(\d+)m(.*?)(?=\u001b|\n|$)/g;
    let result = text;
    let match;
    
    while ((match = regex.exec(text)) !== null) {
        const [fullMatch, colorCode, content] = match;
        const color = ANSI_COLORS[colorCode] || '#d4d4d4';
        result = result.replace(fullMatch, `<span style="color: ${color}">${content}</span>`);
    }
    
    return result.replace(/\u001b\[\d+m/g, '');
}

// 在页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    messagesContainer = document.querySelector('.messages-container');
    
    // 监听滚动事件
    messagesContainer.addEventListener('scroll', function() {
        const isAtBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight < 10;
        shouldAutoScroll = isAtBottom;
    });
});

function selectAllClients(selected) {
    const checkboxes = document.querySelectorAll('#clients input[type="checkbox"]');
    checkboxes.forEach(checkbox => {
        checkbox.checked = selected;
        updateClientFilter(checkbox);
    });
}

function updateClientFilter(checkbox) {
    const clientId = checkbox.value;
    if (checkbox.checked) {
        filteredClients.add(clientId);
    } else {
        filteredClients.delete(clientId);
    }
    refreshMessages();
}

function refreshMessages() {
    const messagesDiv = document.getElementById("messages");
    messagesDiv.innerHTML = "";
    
    allMessages.forEach(msg => {
        if (shouldShowMessage(msg)) {
            const div = document.createElement("div");
            if (msg.addr === "系统") {
                div.className = "system-message";
            }
            // 使用ANSI颜色解析
            div.innerHTML = parseAnsiColor(msg.data);
            messagesDiv.appendChild(div);
        }
    });
    
    scrollToBottom();
}

function shouldShowMessage(msg) {
    if (msg.addr === "系统") {
        // 检查系统消息是否与被过滤的客户端相关
        const messageText = msg.data.toLowerCase();
        return Array.from(filteredClients).some(client => 
            messageText.includes(client.toLowerCase())
        ) || messageText.includes("新客户端连接") || messageText.includes("客户端断开连接");
    }
    // 检查消息发送者是否在过滤列表中
    return filteredClients.has(msg.addr);
}

// 滚动到底部的函数
function scrollToBottom() {
    if (shouldAutoScroll && messagesContainer) {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }
}

// 添加WebSocket连接状态处理
ws.onopen = function() {
    console.log("WebSocket连接已建立");
    document.querySelector('button').disabled = false;
    // 请求初始化数据
    ws.send(JSON.stringify({
        type: "init",
        message: "request_current_state"
    }));
};

ws.onerror = function(error) {
    console.error("WebSocket错误:", error);
    alert("连接服务器失败，请检查服务器是否运行");
};

ws.onclose = function() {
    console.log("WebSocket连接已关闭");
    document.querySelector('button').disabled = true;
};

// 获取每个客户端的消息数量
function getClientMessageCount(clientId) {
    return allMessages.filter(msg => 
        msg.addr === clientId || 
        (msg.addr === "系统" && msg.data.toLowerCase().includes(clientId.toLowerCase()))
    ).length;
}

// 更新客户端列表项
function updateClientListItem(client) {
    const li = document.createElement("li");
    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.id = `client-${client}`;
    checkbox.value = client;
    checkbox.checked = filteredClients.has(client);
    checkbox.onchange = () => updateClientFilter(checkbox);
    
    const label = document.createElement("label");
    label.htmlFor = `client-${client}`;
    label.textContent = client;
    
    const count = document.createElement("span");
    count.className = "message-count";
    count.textContent = getClientMessageCount(client);
    
    li.appendChild(checkbox);
    li.appendChild(label);
    li.appendChild(count);
    return li;
}

// 更新所有客户端的消息计数
function updateAllClientCounts() {
    const clientList = document.getElementById("clients");
    const clients = Array.from(clientList.children);
    
    clients.forEach(li => {
        const clientId = li.querySelector('input').value;
        const countSpan = li.querySelector('.message-count');
        countSpan.textContent = getClientMessageCount(clientId);
    });
}

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    if (data.type === "client_update") {
        document.getElementById("client-count").innerText = data.clients.length;
        let clientList = document.getElementById("clients");
        let select = document.getElementById("client-select");
        clientList.innerHTML = "";
        select.innerHTML = "";
        
        data.clients.forEach(client => {
            // 使用新的创建列表项函数
            const li = updateClientListItem(client);
            clientList.appendChild(li);

            // 更新发送消息的下拉框
            let option = document.createElement("option");
            option.value = client;
            option.innerText = client;
            select.appendChild(option);
        });

        // 如果是首次加载，默认选中所有客户端
        if (filteredClients.size === 0) {
            selectAllClients(true);
        }
    } else if (data.type === "message") {
        // 保存消息
        allMessages.push(data);
        
        // 更新消息计数
        updateAllClientCounts();
        
        // 如果消息应该显示，则添加到界面
        if (shouldShowMessage(data)) {
            let messages = document.getElementById("messages");
            let div = document.createElement("div");
            
            if (data.addr === "系统") {
                div.className = "system-message";
            }
            
            // 使用ANSI颜色解析
            div.innerHTML = parseAnsiColor(data.data);
            messages.appendChild(div);
            scrollToBottom();
        }
    }
};

function sendMessage() {
    const select = document.getElementById("client-select");
    const messageInput = document.getElementById("message");
    const messageText = messageInput.value.trim();
    
    if (!select.value) {
        alert("请选择一个客户端");
        return;
    }
    
    if (!messageText) {
        alert("请输入消息内容");
        return;
    }

    if (ws.readyState !== WebSocket.OPEN) {
        alert("WebSocket连接已断开，请刷新页面重试");
        return;
    }

    try {
        const messageData = {
            type: "send",
            addr: select.value,
            message: messageText
        };
        
        console.log("发送消息:", messageData);
        ws.send(JSON.stringify(messageData));
        
        // 清空输入框
        messageInput.value = "";
    } catch (error) {
        console.error("发送消息失败:", error);
        alert("发送消息失败，请重试");
    }
}

// 添加回车发送功能
document.getElementById("message").addEventListener("keypress", function(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}); 