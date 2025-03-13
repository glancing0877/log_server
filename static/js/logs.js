document.addEventListener('DOMContentLoaded', function() {
    // 获取日志列表
    fetchLogs();

    // 为返回按钮添加事件监听
    const backButton = document.querySelector('.back-button');
    if (backButton) {
        backButton.addEventListener('click', function(e) {
            e.preventDefault();
            window.location.href = '/';
        });
    }
});

function fetchLogs() {
    fetch('/api/logs')
        .then(response => response.json())
        .then(logs => {
            const logsList = document.querySelector('.logs-list');
            logsList.innerHTML = '';
            
            logs.forEach(log => {
                const logItem = createLogItem(log);
                logsList.appendChild(logItem);
            });
        })
        .catch(error => {
            console.error('获取日志列表失败:', error);
            alert('获取日志列表失败，请刷新页面重试');
        });
}

function createLogItem(log) {
    const div = document.createElement('div');
    div.className = 'log-item';
    div.innerHTML = `
        <div class="log-info">
            <div class="log-name">${log.name}</div>
            <div class="log-meta">
                大小: ${formatFileSize(log.size)} | 
                修改时间: ${formatDate(log.modified_time)}
            </div>
            <div class="log-content" id="content-${log.name}"></div>
        </div>
        <div class="log-actions">
            <button class="view-btn" onclick="viewLog('${log.name}', this)">查看</button>
            <button class="download-btn" onclick="downloadLog('${log.name}')">下载</button>
        </div>
    `;
    return div;
}

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
    
    // 替换所有ANSI颜色代码
    while ((match = regex.exec(text)) !== null) {
        const [fullMatch, colorCode, content] = match;
        const color = ANSI_COLORS[colorCode] || '#d4d4d4';
        result = result.replace(fullMatch, `<span style="color: ${color}">${content}</span>`);
    }
    
    // 移除任何剩余的ANSI代码
    return result.replace(/\u001b\[\d+m/g, '');
}

function viewLog(logName, button) {
    const contentDiv = document.getElementById(`content-${logName}`);
    const isActive = contentDiv.classList.contains('active');
    
    if (isActive) {
        contentDiv.classList.remove('active');
        button.textContent = '查看';
        return;
    }

    fetch(`/api/logs/view/${logName}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(content => {
            // 处理日志内容
            const lines = content.split('\n');
            let formattedContent = '<div class="log-lines-container">';
            
            lines.forEach((line, index) => {
                if (!line.trim()) return;
                
                const lineNumber = index + 1;
                const parts = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - \[([^\]]+)\] - (.+)$/);
                
                if (parts) {
                    const [_, timestamp, level, threadName, message] = parts;
                    let messageClass = 'message';
                    if (level === 'ERROR') messageClass = 'error-message';
                    if (level === 'WARNING') messageClass = 'warning-message';
                    
                    // 解析消息中的ANSI颜色代码
                    const parsedMessage = parseAnsiColor(message);
                    
                    formattedContent += `<div class="log-line"><span class="line-number">${lineNumber}</span><div class="line-content"><span class="timestamp">${timestamp}</span> - <span class="log-level">${level}</span> - <span class="thread-name">[${threadName}]</span> - <span class="${messageClass}">${parsedMessage}</span></div></div>`;
                } else {
                    // 解析整行的ANSI颜色代码
                    const parsedLine = parseAnsiColor(line);
                    formattedContent += `<div class="log-line"><span class="line-number">${lineNumber}</span><div class="line-content"><span class="message">${parsedLine}</span></div></div>`;
                }
            });
            
            formattedContent += '</div>';
            contentDiv.innerHTML = formattedContent;
            contentDiv.classList.add('active');
            button.textContent = '隐藏';
        })
        .catch(error => {
            console.error('获取日志内容失败:', error);
            alert('获取日志内容失败，请重试');
            button.textContent = '查看';
        });
}

function downloadLog(logName) {
    const link = document.createElement('a');
    link.href = `/api/logs/${logName}/download`;
    link.download = logName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

function formatDate(timestamp) {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp * 1000);
    if (isNaN(date.getTime())) return 'Invalid Date';
    return date.toLocaleString('zh-CN', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
} 