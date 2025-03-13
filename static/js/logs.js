document.addEventListener('DOMContentLoaded', function() {
    // 初始化页面
    initializePage();
});

let currentSN = 'default';
let currentDate = null;

function initializePage() {
    // 获取可用的SN列表
    fetchSNList();
    // 获取当前选择的SN的日期列表
    fetchDateList();
}

function fetchSNList() {
    fetch('/api/logs/sn-list')
        .then(response => response.json())
        .then(snList => {
            const snSelect = document.getElementById('sn-select');
            // 保留默认选项
            snSelect.innerHTML = '<option value="default">全局日志</option>';
            
            snList.forEach(sn => {
                const option = document.createElement('option');
                option.value = sn;
                option.textContent = `设备 ${sn}`;
                snSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('获取SN列表失败:', error);
        });
}

function fetchDateList() {
    fetch(`/api/logs/date-list/${currentSN}`)
        .then(response => response.json())
        .then(dates => {
            const dateSelect = document.getElementById('date-select');
            dateSelect.innerHTML = '';
            
            dates.forEach(date => {
                const option = document.createElement('option');
                option.value = date;
                option.textContent = date;
                dateSelect.appendChild(option);
            });
            
            // 默认选择最新的日期
            if (dates.length > 0) {
                currentDate = dates[0];
                dateSelect.value = currentDate;
                // 使用setTimeout确保DOM更新后再获取日志内容
                setTimeout(() => {
                    fetchLogContent();
                }, 100);
            }
        })
        .catch(error => {
            console.error('获取日期列表失败:', error);
        });
}

function handleSNChange() {
    const snSelect = document.getElementById('sn-select');
    currentSN = snSelect.value;
    // 更新日期列表
    fetchDateList();
}

function handleDateChange() {
    const dateSelect = document.getElementById('date-select');
    currentDate = dateSelect.value;
    fetchLogContent();
}

function fetchLogContent() {
    if (!currentDate) {
        console.warn('没有选择日期，跳过获取日志内容');
        return;
    }
    
    const path = currentSN === 'default' 
        ? `default/${currentDate}.log`
        : `${currentSN}/${currentDate}.log`;
    
    console.log('正在获取日志内容:', path);
        
    fetch(`/api/logs/content/${path}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(content => {
            console.log('成功获取日志内容，长度:', content.length);
            displayLogContent(content);
        })
        .catch(error => {
            console.error('获取日志内容失败:', error);
            const container = document.querySelector('.log-lines-container');
            container.innerHTML = '<div class="error-message">获取日志内容失败，请重试</div>';
        });
}

function displayLogContent(content) {
    const container = document.querySelector('.log-lines-container');
    // 先按行分割，然后过滤掉空行或只包含空白字符的行
    const lines = content.split('\n').filter(line => line.trim());
    let formattedContent = '';
    
    lines.forEach((line, index) => {
        const lineNumber = index + 1;
        const parts = line.match(/^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) - (\w+) - \[([^\]]+)\] - (.+)$/);
        
        if (parts) {
            const [_, timestamp, level, threadName, message] = parts;
            let messageClass = 'message';
            if (level === 'ERROR') messageClass = 'error-message';
            if (level === 'WARNING') messageClass = 'warning-message';
            
            // 解析消息中的ANSI颜色代码
            const parsedMessage = parseAnsiColor(message);
            
            formattedContent += `<div class="log-line"><span class="line-number">${lineNumber}</span><div class="line-content"><span class="timestamp">${timestamp}</span> - <span class="log-level ${level.toLowerCase()}">${level}</span> - <span class="thread-name">[${threadName}]</span> - <span class="${messageClass}">${parsedMessage}</span></div></div>`;
        } else {
            // 解析整行的ANSI颜色代码
            const parsedLine = parseAnsiColor(line);
            formattedContent += `<div class="log-line"><span class="line-number">${lineNumber}</span><div class="line-content"><span class="message">${parsedLine}</span></div></div>`;
        }
    });
    
    container.innerHTML = formattedContent;
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

function refreshLogs() {
    fetchLogContent();
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