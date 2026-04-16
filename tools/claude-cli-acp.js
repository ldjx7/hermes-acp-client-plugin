#!/usr/bin/env node
/**
 * Claude CLI ACP Adapter
 * 
 * 使用官方的 claude CLI 作为 ACP worker，支持自定义 base URL
 * 
 * Usage:
 *   node claude-cli-acp.js
 * 
 * Environment:
 *   ANTHROPIC_API_KEY - API key
 *   ANTHROPIC_BASE_URL - Custom base URL
 *   ANTHROPIC_MODEL - Model name
 */

const { spawn } = require('child_process');
const readline = require('readline');

// 配置
const config = {
    apiKey: process.env.ANTHROPIC_API_KEY,
    baseUrl: process.env.ANTHROPIC_BASE_URL || 'https://api.anthropic.com',
    model: process.env.ANTHROPIC_MODEL || 'claude-3-5-sonnet-20241022',
};

let sessionId = null;
let requestId = null;

// ACP 协议常量
const PROTOCOL_VERSION = 1;

// 日志
function log(...args) {
    const msg = `[claude-cli-acp] ${args.join(' ')}`;
    process.stderr.write(msg + '\n');
}

log('Starting Claude CLI ACP Adapter...');
log(`API Key: ${config.apiKey ? '✅' : '❌'}`);
log(`Base URL: ${config.baseUrl}`);
log(`Model: ${config.model}`);

// 读取 stdin
const rl = readline.createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false
});

// 处理输入
rl.on('line', (line) => {
    try {
        const msg = JSON.parse(line);
        handleMessage(msg);
    } catch (e) {
        log(`Invalid JSON: ${e.message}`);
    }
});

// 发送 JSON 响应
function sendResponse(response) {
    process.stdout.write(JSON.stringify(response) + '\n');
}

// 发送通知
function sendNotification(method, params) {
    sendResponse({
        jsonrpc: '2.0',
        method: method,
        params: params
    });
}

// 处理 ACP 消息
async function handleMessage(msg) {
    const { method, params, id } = msg;
    
    log(`Received: ${method}`);
    
    switch (method) {
        case 'initialize':
            handleInitialize(id, params);
            break;
        
        case 'session/new':
            await handleNewSession(id, params);
            break;
        
        case 'session/prompt':
            await handleSessionPrompt(id, params);
            break;
        
        default:
            log(`Unknown method: ${method}`);
            sendResponse({
                jsonrpc: '2.0',
                id: id,
                error: {
                    code: -32601,
                    message: `Method not found: ${method}`
                }
            });
    }
}

// 处理初始化
function handleInitialize(id, params) {
    sessionId = `session-${Date.now()}`;
    
    sendResponse({
        jsonrpc: '2.0',
        id: id,
        result: {
            protocolVersion: PROTOCOL_VERSION,
            capabilities: {
                tools: true,
                prompts: true
            },
            serverInfo: {
                name: 'claude-cli-acp',
                version: '1.0.0'
            }
        }
    });
    
    log(`Initialized session: ${sessionId}`);
}

// 处理创建会话
async function handleNewSession(id, params) {
    sessionId = params?.sessionId || `session-${Date.now()}`;
    
    sendResponse({
        jsonrpc: '2.0',
        id: id,
        result: {
            sessionId: sessionId
        }
    });
    
    log(`Created session: ${sessionId}`);
}

// 处理提示
async function handleSessionPrompt(id, params) {
    const { sessionId: sid, prompt } = params;
    
    if (!prompt || !Array.isArray(prompt)) {
        sendResponse({
            jsonrpc: '2.0',
            id: id,
            error: {
                code: -32602,
                message: 'Invalid prompt format'
            }
        });
        return;
    }
    
    // 提取提示文本
    const promptText = prompt.map(p => {
        if (typeof p === 'string') return p;
        if (p.type === 'text') return p.text;
        return '';
    }).join('\n');
    
    log(`Processing prompt: ${promptText.substring(0, 50)}...`);
    
    // 发送状态更新（使用标准 ACP session/state 格式）
    sendNotification('session/state', {
        sessionId: sid || sessionId,
        state: 'running'
    });
    
    try {
        // 调用 claude CLI（传入 sessionId 和 id 用于心跳通知）
        const result = await callClaudeCLI(promptText, sid || sessionId, id);
        
        // 发送结果（使用标准格式）
        sendNotification('session/state', {
            sessionId: sid || sessionId,
            state: 'completed',
            result: result,
            message: 'Task completed successfully'
        });
        
        // 发送响应
        sendResponse({
            jsonrpc: '2.0',
            id: id,
            result: {
                result: result,
                stopReason: 'end_turn'
            }
        });
        
        log('Completed');
        
    } catch (error) {
        log(`Error: ${error.message}`);
        
        // 发送错误通知（使用标准格式）
        sendNotification('session/state', {
            sessionId: sid || sessionId,
            state: 'failed',
            error: error.message,
            message: error.message
        });
        
        sendResponse({
            jsonrpc: '2.0',
            id: id,
            error: {
                code: -32000,
                message: error.message
            }
        });
    }
}

// 调用 Claude CLI（带心跳通知）
function callClaudeCLI(prompt, sessionIdentifier, requestId) {
    return new Promise((resolve, reject) => {
        log(`Calling claude CLI with model: ${config.model}`);
        
        // 构建命令
        const args = ['-p', prompt];
        
        // 添加模型参数（如果 claude CLI 支持）
        if (config.model) {
            args.unshift('--model', config.model);
        }
        
        log(`Command: claude ${args.join(' ')}`);
        
        const claude = spawn('claude', args, {
            env: {
                ...process.env,
                ANTHROPIC_API_KEY: config.apiKey,
                ANTHROPIC_BASE_URL: config.baseUrl
            },
            stdio: ['ignore', 'pipe', 'pipe']  // 忽略 stdin，避免警告
        });
        
        let output = '';
        let errorOutput = '';
        let lastProgress = 0;
        let lastActivity = Date.now();
        
        // 监听 stdout - 每有输出就发送心跳
        claude.stdout.on('data', (data) => {
            const text = data.toString();
            output += text;
            
            // 估算进度（基于输出长度，简单但有效）
            const estimatedProgress = Math.min(0.95, output.length / 50000);
            if (estimatedProgress - lastProgress > 0.05) {
                lastProgress = estimatedProgress;
                sendNotification('session/state', {
                    sessionId: sessionIdentifier,
                    state: 'running',
                    progress: lastProgress,
                    message: `Generating response... (${Math.round(lastProgress * 100)}%)`
                });
            }
            
            lastActivity = Date.now();
        });
        
        claude.stderr.on('data', (data) => {
            errorOutput += data.toString();
            log(`stderr: ${data.toString().trim()}`);
            lastActivity = Date.now();  // stderr 输出也视为活动
        });
        
        // 定期检查活动（每 15 秒发送保持活动通知）
        const activityCheck = setInterval(() => {
            const silence = Date.now() - lastActivity;
            if (silence > 15000 && silence < 55000) {
                // 15-55 秒无输出，发送保持活动通知
                sendNotification('session/state', {
                    sessionId: sessionIdentifier,
                    state: 'running',
                    progress: lastProgress,
                    message: `Still processing... (silent for ${Math.round(silence/1000)}s)`
                });
            }
        }, 15000);
        
        claude.on('close', (code) => {
            clearInterval(activityCheck);
            
            if (code === 0) {
                // ✅ 只 resolve，不发响应（让 handleSessionPrompt 统一发送）
                log('Completed');
                resolve(output.trim());
            } else {
                // ✅ 只 reject，不发响应（让 handleSessionPrompt 处理错误）
                log(`Error: claude exited with code ${code}`);
                reject(new Error(`claude exited with code ${code}: ${errorOutput || output}`));
            }
        });
        
        claude.on('error', (err) => {
            clearInterval(activityCheck);
            reject(new Error(`Failed to start claude: ${err.message}`));
        });
        
        // 设置超时（15 分钟，给心跳机制处理）
        setTimeout(() => {
            clearInterval(activityCheck);
            claude.kill('SIGTERM');
            reject(new Error('Timeout after 15 minutes'));
        }, 900000);
    });
}

log('Ready to accept ACP messages');
