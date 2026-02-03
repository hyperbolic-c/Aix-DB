/**
 * 测试框架前端应用
 * Google 科技风格
 */

// API 基础配置
const API_BASE_URL = 'http://localhost:8003';

// 状态管理
const state = {
    selectedCaseId: null,
    loading: false,
    logs: []
};

// DOM 元素
const elements = {
    serviceUrl: document.getElementById('serviceUrl'),
    caseIdInput: document.getElementById('caseIdInput'),
    loadCaseBtn: document.getElementById('loadCaseBtn'),
    caseInfo: document.getElementById('caseInfo'),
    caseId: document.getElementById('caseId'),
    caseLevel: document.getElementById('caseLevel'),
    caseTable: document.getElementById('caseTable'),
    questionInput: document.getElementById('questionInput'),
    resultsSection: document.getElementById('resultsSection'),
    sqlCode: document.getElementById('sqlCode'),
    rowCount: document.getElementById('rowCount'),
    execTime: document.getElementById('execTime'),
    dataTable: document.getElementById('dataTable'),
    chartCode: document.getElementById('chartCode'),
    summaryText: document.getElementById('summaryText'),
    logsContainer: document.getElementById('logsContainer'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    runTestBtn: document.getElementById('runTestBtn'),
    resetBtn: document.getElementById('resetBtn'),
    clearLogsBtn: document.getElementById('clearLogsBtn'),
    copySqlBtn: document.getElementById('copySqlBtn')
};

// 日志功能
function addLog(message) {
    const timestamp = new Date().toLocaleTimeString();
    const logLine = document.createElement('div');
    logLine.className = 'log-line';
    logLine.textContent = `[${timestamp}] ${message}`;
    
    // 移除空提示
    const emptyLog = elements.logsContainer.querySelector('.log-empty');
    if (emptyLog) {
        emptyLog.remove();
    }
    
    elements.logsContainer.appendChild(logLine);
    elements.logsContainer.scrollTop = elements.logsContainer.scrollHeight;
    state.logs.push(`[${timestamp}] ${message}`);
}

function clearLogs() {
    elements.logsContainer.innerHTML = '<div class="log-empty">暂无日志...</div>';
    state.logs = [];
}

// 加载指定用例
async function loadCase() {
    const caseId = parseInt(elements.caseIdInput.value);
    
    if (!caseId || caseId < 1) {
        addLog('错误: 请输入有效的用例ID');
        return;
    }
    
    try {
        addLog(`正在加载用例 #${caseId}...`);
        
        const response = await fetch(`${API_BASE_URL}/api/test-framework/gold-cases/${caseId}`);
        if (!response.ok) {
            if (response.status === 404) {
                throw new Error(`用例 #${caseId} 不存在`);
            }
            throw new Error(`HTTP ${response.status}`);
        }
        
        const caseData = await response.json();
        state.selectedCaseId = caseId;
        
        // 更新用例信息
        elements.caseId.textContent = `#${caseData.id}`;
        elements.caseLevel.textContent = `Level ${caseData.level}`;
        elements.caseLevel.className = `badge level-${caseData.level}`;
        elements.caseTable.textContent = caseData.table;
        elements.caseInfo.style.display = 'block';
        
        // 填充问题输入
        elements.questionInput.value = caseData.question;
        
        addLog(`✓ 已加载用例 #${caseId}`);
    } catch (error) {
        addLog(`✗ 加载失败: ${error.message}`);
        // 清空用例信息
        elements.caseInfo.style.display = 'none';
        state.selectedCaseId = null;
    }
}

// 获取选中的 Schema 模式
function getSchemaMode() {
    const radios = document.getElementsByName('schemaMode');
    for (const radio of radios) {
        if (radio.checked) {
            return radio.value;
        }
    }
    return 'related';
}

// 运行测试
async function runTest() {
    const question = elements.questionInput.value.trim();
    
    if (!question) {
        addLog('错误: 请输入问题或加载用例');
        return;
    }
    
    try {
        state.loading = true;
        elements.loadingOverlay.style.display = 'flex';
        clearLogs();
        
        addLog('开始测试...');
        addLog(`问题: ${question.slice(0, 60)}...`);
        addLog(`Schema 模式: ${getSchemaMode()}`);
        
        const request = {
            query: question,
            datasource_config: {
                db_type: 'sqlite',
                db_path: 'target_db/competition/final.db'
            },
            schema_info: {
                tables: []
            },
            schema_mode: getSchemaMode(),
            case_id: state.selectedCaseId || undefined
        };
        
        const response = await fetch(`${API_BASE_URL}/api/test-framework/run`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(request)
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            addLog('✓ 测试成功');
            displayResults(result);
        } else {
            addLog(`✗ 测试失败: ${result.error}`);
            displayError(result.error);
        }
    } catch (error) {
        addLog(`✗ 执行错误: ${error.message}`);
        displayError(error.message);
    } finally {
        state.loading = false;
        elements.loadingOverlay.style.display = 'none';
    }
}

// 显示结果
function displayResults(result) {
    elements.resultsSection.style.display = 'block';
    
    // SQL
    elements.sqlCode.textContent = result.sql || '-- 无 SQL 生成';
    
    // 执行结果
    if (result.execution_result) {
        elements.rowCount.textContent = result.execution_result.row_count;
        elements.execTime.textContent = `${result.execution_result.execution_time_ms}ms`;
        
        // 填充表格
        const data = result.execution_result.data;
        if (data && data.length > 0) {
            const headers = Object.keys(data[0]);
            
            // 表头
            const thead = elements.dataTable.querySelector('thead');
            thead.innerHTML = `<tr>${headers.map(h => `<th>${h}</th>`).join('')}</tr>`;
            
            // 表体
            const tbody = elements.dataTable.querySelector('tbody');
            tbody.innerHTML = data.map(row => 
                `<tr>${headers.map(h => `<td>${row[h]}</td>`).join('')}</tr>`
            ).join('');
        }
    }
    
    // 图表配置
    elements.chartCode.textContent = result.chart_config 
        ? JSON.stringify(result.chart_config, null, 2) 
        : '// 无图表配置';
    
    // 总结
    elements.summaryText.textContent = result.summary || '无总结信息';
    
    // 滚动到结果区域
    elements.resultsSection.scrollIntoView({ behavior: 'smooth' });
}

// 显示错误
function displayError(error) {
    elements.resultsSection.style.display = 'block';
    elements.sqlCode.textContent = `-- 错误: ${error}`;
    elements.rowCount.textContent = '-';
    elements.execTime.textContent = '-';
    elements.dataTable.querySelector('thead').innerHTML = '';
    elements.dataTable.querySelector('tbody').innerHTML = '';
    elements.chartCode.textContent = '// 无图表配置';
    elements.summaryText.textContent = `测试失败: ${error}`;
}

// 重置
function reset() {
    state.selectedCaseId = null;
    elements.caseIdInput.value = '';
    elements.caseInfo.style.display = 'none';
    elements.questionInput.value = '';
    elements.resultsSection.style.display = 'none';
    clearLogs();
    addLog('已重置');
}

// 复制 SQL
function copySql() {
    const sql = elements.sqlCode.textContent;
    navigator.clipboard.writeText(sql).then(() => {
        addLog('SQL 已复制到剪贴板');
    }).catch(err => {
        addLog('复制失败');
    });
}

// Tab 切换
function initTabs() {
    const tabs = document.querySelectorAll('.tab');
    const panels = document.querySelectorAll('.tab-panel');
    
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const targetTab = tab.dataset.tab;
            
            // 更新 Tab 状态
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            
            // 更新面板状态
            panels.forEach(panel => {
                panel.classList.remove('active');
                if (panel.id === `${targetTab}Panel`) {
                    panel.classList.add('active');
                }
            });
        });
    });
}

// 初始化
function init() {
    // 事件监听
    elements.loadCaseBtn.addEventListener('click', loadCase);
    elements.caseIdInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            loadCase();
        }
    });
    
    elements.runTestBtn.addEventListener('click', runTest);
    elements.resetBtn.addEventListener('click', reset);
    elements.clearLogsBtn.addEventListener('click', clearLogs);
    elements.copySqlBtn.addEventListener('click', copySql);
    
    // 初始化 Tabs
    initTabs();
    
    addLog('测试框架已初始化');
    addLog('请输入用例ID (1-800) 并按回车或点击加载按钮');
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);
