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
let messageHistory = [];  // 存储发送历史记录

// ANSI颜色代码映射
const ANSI_COLORS = {
    // 前景色
    '30': 'black',
    '31': 'red',
    '32': 'green',
    '33': 'yellow',
    '34': 'blue',
    '35': 'magenta',
    '36': 'cyan',
    '37': 'white',
    '90': '#888', // 亮黑（灰色）
    '91': '#f44336', // 亮红
    '92': '#4caf50', // 亮绿
    '93': '#ffc107', // 亮黄
    '94': '#2196f3', // 亮蓝
    '95': '#e91e63', // 亮洋红
    '96': '#00bcd4', // 亮青
    '97': '#fff',  // 亮白
    // 背景色
    '40': 'black',
    '41': 'red',
    '42': 'green',
    '43': 'yellow',
    '44': 'blue',
    '45': 'magenta',
    '46': 'cyan',
    '47': 'white',
    '100': '#333', // 亮黑（灰色）背景
    '101': '#ffebee', // 亮红背景
    '102': '#e8f5e9', // 亮绿背景
    '103': '#fff8e1', // 亮黄背景
    '104': '#e3f2fd', // 亮蓝背景
    '105': '#fce4ec', // 亮洋红背景
    '106': '#e0f7fa', // 亮青背景
    '107': '#fff',  // 亮白背景
    // 样式
    '0': 'reset',   // 重置
    '1': 'bold',    // 粗体
    '3': 'italic',  // 斜体
    '4': 'underline' // 下划线
};

// 创建ANSI转换器实例
const ansiUp = new AnsiUp();
ansiUp.use_classes = true;  // 使用CSS类而不是内联样式
ansiUp.escape_for_html = true;  // 转义HTML字符

// 解析ANSI转义序列
function parseAnsiToHtml(text) {
    try {
        // 调试日志
        console.log('Original text:', text);
        
        // 处理转义字符
        text = text.replace(/\\u001b/g, '\u001b')
                  .replace(/\\x1b/g, '\u001b')
                  .replace(/\\033/g, '\u001b')
                  .replace(/\\n/g, '\n')
                  .replace(/\\r/g, '\r')
                  .replace(/\[(\d+;)*\d+m/g, (match) => `\u001b${match}`);  // 处理可能缺少转义字符的颜色代码
        
        // 使用ansi_up转换
        const html = ansiUp.ansi_to_html(text);
        
        // 调试日志
        console.log('Converted HTML:', html);
        
        return html;
    } catch (error) {
        console.error('Error parsing ANSI:', error);
        return text;
    }
}

// 从localStorage加载历史记录
function loadMessageHistory() {
    const savedHistory = localStorage.getItem('messageHistory');
    if (savedHistory) {
        messageHistory = JSON.parse(savedHistory);
    }
}

// 保存历史记录到localStorage
function saveMessageHistory() {
    localStorage.setItem('messageHistory', JSON.stringify(messageHistory));
}

// 添加消息到历史记录
function addToMessageHistory(message) {
    // 避免重复
    if (!messageHistory.includes(message)) {
        messageHistory.unshift(message);  // 添加到开头
        if (messageHistory.length > 50) {  // 限制50条
            messageHistory.pop();
        }
        saveMessageHistory();
        updateHistoryDropdown();
    }
}

// 更新历史记录下拉列表
function updateHistoryDropdown() {
    const historyList = document.getElementById('message-history');
    if (!historyList) return;
    
    historyList.innerHTML = '';
    messageHistory.forEach(msg => {
        const option = document.createElement('option');
        option.value = msg;
        option.textContent = msg.length > 50 ? msg.substring(0, 47) + '...' : msg;
        historyList.appendChild(option);
    });
}

// 在页面加载完成后初始化
document.addEventListener('DOMContentLoaded', function() {
    messagesContainer = document.querySelector('.messages-container');
    
    // 监听滚动事件
    messagesContainer.addEventListener('scroll', function() {
        const isAtBottom = messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight < 10;
        shouldAutoScroll = isAtBottom;
    });

    // 加载历史记录
    loadMessageHistory();
    
    // 创建历史记录下拉列表
    const messageInput = document.getElementById('message');
    const historySelect = document.createElement('select');
    historySelect.id = 'message-history';
    historySelect.style.width = '100%';
    historySelect.size = 8;  // 显示8行
    
    // 当选择历史记录时，填充到输入框
    historySelect.addEventListener('change', function() {
        if (this.value) {
            messageInput.value = this.value;
            this.selectedIndex = -1;  // 清除选择状态
        }
    });
    
    // 将历史记录下拉列表添加到历史区域
    const historyContainer = document.getElementById('history-container');
    historyContainer.appendChild(historySelect);
    
    // 更新历史记录显示
    updateHistoryDropdown();
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
            // 使用ANSI解析器处理消息内容
            div.innerHTML = parseAnsiToHtml(msg.data);
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
            
            // 使用ANSI解析器处理消息内容
            div.innerHTML = parseAnsiToHtml(data.data);
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
        
        // 添加到历史记录
        addToMessageHistory(messageText);
        
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

// 清空历史记录
function clearHistory() {
    if (confirm('确定要清空所有发送历史记录吗？')) {
        messageHistory = [];
        saveMessageHistory();
        updateHistoryDropdown();
    }
}

// 填充常用指令到输入框
function fillCommand(command) {
    const messageInput = document.getElementById("message");
    messageInput.value = command;
    messageInput.focus();
} 