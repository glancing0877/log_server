document.addEventListener('DOMContentLoaded', function() {
    // 检查必要的DOM元素是否存在
    const requiredElements = ['sn-select', 'date-select', 'log-lines-container'];
    const missingElements = requiredElements.filter(id => !document.getElementById(id));
    
    if (missingElements.length > 0) {
        console.error('缺少必要的DOM元素:', missingElements);
        return;
    }
    
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
    console.log('开始获取SN列表');
    fetch('/api/logs/sn-list')
        .then(response => {
            console.log('SN列表响应状态:', response.status);
            if (!response.ok) {
                throw new Error(`获取SN列表失败: HTTP ${response.status}`);
            }
            return response.text().then(text => {
                console.log('SN列表原始响应:', text);
                try {
                    return JSON.parse(text);
                } catch (e) {
                    console.error('SN列表JSON解析失败:', e);
                    throw new Error('SN列表JSON解析失败');
                }
            });
        })
        .then(snList => {
            console.log('获取到的SN列表:', snList);
            if (!Array.isArray(snList)) {
                console.error('SN列表格式错误，期望数组但收到:', typeof snList, snList);
                throw new Error('SN列表格式错误');
            }
            
            const snSelect = document.getElementById('sn-select');
            if (!snSelect) {
                console.error('找不到SN选择器元素');
                return;
            }
            
            // 保留默认选项
            snSelect.innerHTML = '<option value="default">全局日志</option>';
            
            snList.forEach(sn => {
                const option = document.createElement('option');
                option.value = sn;
                option.textContent = `设备 ${sn}`;
                snSelect.appendChild(option);
            });
            
            console.log('SN列表更新完成，选项数量:', snSelect.options.length);
            
            // 触发change事件以更新日期列表
            const event = new Event('change');
            snSelect.dispatchEvent(event);
        })
        .catch(error => {
            console.error('获取SN列表失败:', error);
            const snSelect = document.getElementById('sn-select');
            if (snSelect) {
                snSelect.innerHTML = '<option value="default">加载失败</option>';
            }
        });
}

function fetchDateList() {
    console.log('开始获取日期列表，当前SN:', currentSN);
    const url = `/api/logs/date-list/${currentSN}`;
    console.log('请求URL:', url);
    
    fetch(url)
        .then(response => {
            console.log('日期列表响应状态:', response.status);
            console.log('响应头:', Object.fromEntries(response.headers.entries()));
            if (!response.ok) {
                throw new Error(`获取日期列表失败: HTTP ${response.status}`);
            }
            return response.text();
        })
        .then(text => {
            console.log('日期列表原始响应:', text);
            try {
                const dates = JSON.parse(text);
                console.log('解析后的日期列表:', dates);
                
                if (!Array.isArray(dates)) {
                    console.error('日期列表格式错误，期望数组但收到:', typeof dates, dates);
                    throw new Error('日期列表格式错误');
                }
                
                const dateSelect = document.getElementById('date-select');
                if (!dateSelect) {
                    console.error('找不到日期选择器元素');
                    throw new Error('找不到日期选择器元素');
                }
                
                dateSelect.innerHTML = '';
                
                if (dates.length === 0) {
                    console.log('日期列表为空');
                    dateSelect.innerHTML = '<option value="">无可用日期</option>';
                    return;
                }
                
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
                    console.log('设置当前日期为:', currentDate);
                    fetchLogContent();
                }
            } catch (e) {
                console.error('JSON解析失败:', e);
                throw new Error('解析日期列表JSON失败');
            }
        })
        .catch(error => {
            console.error('获取日期列表失败:', error);
            const dateSelect = document.getElementById('date-select');
            if (dateSelect) {
                dateSelect.innerHTML = '<option value="">加载失败</option>';
            }
            const container = document.querySelector('.log-lines-container');
            if (container) {
                container.innerHTML = `<div class="error-message">获取日期列表失败: ${error.message}</div>`;
            }
        });
}

function handleSNChange() {
    const snSelect = document.getElementById('sn-select');
    if (!snSelect) {
        console.error('找不到SN选择器元素');
        return;
    }
    
    currentSN = snSelect.value;
    console.log('SN变更为:', currentSN);
    // 更新日期列表
    fetchDateList();
}

function handleDateChange() {
    const dateSelect = document.getElementById('date-select');
    if (!dateSelect) {
        console.error('找不到日期选择器元素');
        return;
    }
    
    currentDate = dateSelect.value;
    console.log('日期变更为:', currentDate);
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
    
    console.log('正在获取日志内容，路径:', path);
        
    fetch(`/api/logs/content/${path}`)
        .then(response => {
            console.log('日志内容响应状态:', response.status);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.text();
        })
        .then(content => {
            console.log('成功获取日志内容，长度:', content.length);
            console.log('日志内容前100个字符:', content.substring(0, 100));
            displayLogContent(content);
        })
        .catch(error => {
            console.error('获取日志内容失败:', error);
            const container = document.querySelector('.log-lines-container');
            container.innerHTML = '<div class="error-message">获取日志内容失败，请重试</div>';
        });
}

function displayLogContent(content) {
    console.log('开始处理日志内容');
    const container = document.querySelector('.log-lines-container');
    if (!container) {
        console.error('找不到日志容器元素 .log-lines-container');
        return;
    }
    
    // 先按行分割，然后过滤掉空行或只包含空白字符的行
    const lines = content.split('\n').filter(line => line.trim());
    console.log('处理后的日志行数:', lines.length);
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
    
    console.log('设置日志内容到容器');
    container.innerHTML = formattedContent;
    console.log('日志内容设置完成');
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