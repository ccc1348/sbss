const { app, BrowserWindow, dialog } = require('electron');
const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const http = require('http');

let mainWindow = null;
let pythonProcess = null;
let flaskPort = 8080;
let startupLog = [];

// 記錄啟動日誌
function log(msg) {
    const timestamp = new Date().toLocaleTimeString();
    const line = `[${timestamp}] ${msg}`;
    console.log(line);
    startupLog.push(line);
}

// 顯示錯誤對話框
function showError(title, message) {
    const logText = startupLog.join('\n');
    dialog.showErrorBox(title, `${message}\n\n=== 啟動日誌 ===\n${logText}`);
}

// 取得資源路徑
function getBasePath() {
    if (app.isPackaged) {
        // 打包後: resources/app 目錄
        return path.dirname(app.getAppPath());
    }
    // 開發環境: 專案根目錄
    return __dirname;
}

function getResourcePath(subPath) {
    if (app.isPackaged) {
        // 打包後: resources 目錄下
        return path.join(process.resourcesPath, subPath);
    }
    // 開發環境: 專案根目錄下
    return path.join(__dirname, subPath);
}

// 取得 Python 執行檔路徑
function getPythonPath() {
    // 1. 打包環境: 嵌入式 Python
    if (app.isPackaged) {
        const embeddedPython = getResourcePath('python/python.exe');
        log(`檢查嵌入式 Python: ${embeddedPython}`);
        if (fs.existsSync(embeddedPython)) {
            log('找到嵌入式 Python');
            return embeddedPython;
        }
        log('嵌入式 Python 不存在！');
    }

    // 2. 開發環境: venv
    const venvPython = process.platform === 'win32'
        ? path.join(__dirname, 'venv', 'Scripts', 'python.exe')
        : path.join(__dirname, 'venv', 'bin', 'python');

    log(`檢查 venv Python: ${venvPython}`);
    if (fs.existsSync(venvPython)) {
        log('使用 venv Python');
        return venvPython;
    }

    // 3. 系統 Python
    log('使用系統 Python');
    return process.platform === 'win32' ? 'python' : 'python3';
}

// 取得 web.py 路徑
function getWebPyPath() {
    if (app.isPackaged) {
        // 打包後在 app.asar 同級目錄（因為 asar: false）
        return path.join(app.getAppPath(), 'web.py');
    }
    return path.join(__dirname, 'web.py');
}

// 尋找可用端口
async function findFreePort(startPort) {
    for (let port = startPort; port < startPort + 10; port++) {
        const available = await checkPort(port);
        if (available) return port;
    }
    throw new Error('找不到可用端口 (8080-8089)');
}

function checkPort(port) {
    return new Promise((resolve) => {
        const server = require('net').createServer();
        server.once('error', () => resolve(false));
        server.once('listening', () => {
            server.close();
            resolve(true);
        });
        server.listen(port, '127.0.0.1');
    });
}

// 等待 Flask 就緒
function waitForFlask(port, timeout = 20000) {
    const startTime = Date.now();

    return new Promise((resolve, reject) => {
        const check = () => {
            if (Date.now() - startTime > timeout) {
                reject(new Error(`Flask 啟動超時 (${timeout/1000}秒)`));
                return;
            }

            const req = http.get(`http://127.0.0.1:${port}/`, (res) => {
                resolve();
            });

            req.on('error', () => {
                setTimeout(check, 300);
            });

            req.setTimeout(1000, () => {
                req.destroy();
                setTimeout(check, 300);
            });
        };

        check();
    });
}

// 啟動 Python Flask
async function startFlask() {
    flaskPort = await findFreePort(8080);
    log(`使用端口: ${flaskPort}`);

    const pythonPath = getPythonPath();
    const webPyPath = getWebPyPath();

    log(`Python 路徑: ${pythonPath}`);
    log(`web.py 路徑: ${webPyPath}`);
    log(`app.isPackaged: ${app.isPackaged}`);
    log(`app.getAppPath(): ${app.getAppPath()}`);
    log(`process.resourcesPath: ${process.resourcesPath}`);

    // 檢查檔案是否存在
    if (!fs.existsSync(pythonPath)) {
        throw new Error(`Python 執行檔不存在: ${pythonPath}`);
    }
    if (!fs.existsSync(webPyPath)) {
        throw new Error(`web.py 不存在: ${webPyPath}`);
    }

    // 設定環境變數
    const env = {
        ...process.env,
        FLASK_PORT: flaskPort.toString(),
        PYTHONIOENCODING: 'utf-8'
    };

    // 設定工作目錄為 web.py 所在目錄
    const cwd = path.dirname(webPyPath);
    log(`工作目錄: ${cwd}`);

    // 啟動 Python
    pythonProcess = spawn(pythonPath, [webPyPath], {
        cwd: cwd,
        env: env,
        stdio: ['ignore', 'pipe', 'pipe'],
        // Windows: 不要開啟新視窗
        windowsHide: true
    });

    // 收集輸出
    let stdoutData = '';
    let stderrData = '';

    pythonProcess.stdout.on('data', (data) => {
        const text = data.toString().trim();
        stdoutData += text + '\n';
        log(`[Flask] ${text}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        const text = data.toString().trim();
        stderrData += text + '\n';
        // Flask 的警告訊息也會輸出到 stderr
        if (text.includes('WARNING') || text.includes('Running on')) {
            log(`[Flask] ${text}`);
        } else {
            log(`[Flask Error] ${text}`);
        }
    });

    pythonProcess.on('error', (err) => {
        log(`Python 進程錯誤: ${err.message}`);
    });

    pythonProcess.on('exit', (code, signal) => {
        log(`Python 進程結束 (code=${code}, signal=${signal})`);
        if (code !== 0 && code !== null) {
            // 非正常退出，顯示錯誤
            const errorMsg = stderrData || stdoutData || '未知錯誤';
            showError('Flask 啟動失敗', `退出代碼: ${code}\n\n${errorMsg}`);
        }
        pythonProcess = null;
    });

    // 等待 Flask 就緒
    log('等待 Flask 就緒...');
    await waitForFlask(flaskPort);
    log('Flask 就緒！');
}

// 建立主視窗
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true
        },
        title: 'sbss - Android 自動工具',
        show: false,
        // Windows: 顯示選單列（方便除錯時用 DevTools）
        autoHideMenuBar: true
    });

    const url = `http://127.0.0.1:${flaskPort}/`;
    log(`載入 URL: ${url}`);
    mainWindow.loadURL(url);

    mainWindow.once('ready-to-show', () => {
        mainWindow.show();
    });

    // 載入失敗時顯示錯誤
    mainWindow.webContents.on('did-fail-load', (event, errorCode, errorDescription) => {
        log(`頁面載入失敗: ${errorDescription} (${errorCode})`);
        showError('頁面載入失敗', `${errorDescription}\n\nURL: ${url}`);
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });
}

// 停止 Flask
function stopFlask() {
    if (pythonProcess) {
        log('停止 Flask...');
        if (process.platform === 'win32') {
            // Windows: 使用 taskkill 確保子進程也被終止
            try {
                execSync(`taskkill /pid ${pythonProcess.pid} /f /t`, { stdio: 'ignore' });
            } catch (e) {
                // 忽略錯誤（進程可能已經結束）
            }
        } else {
            pythonProcess.kill('SIGTERM');
        }
        pythonProcess = null;
    }
}

// 寫入啟動日誌到檔案（方便除錯）
function writeLogFile() {
    try {
        const logPath = path.join(app.getPath('userData'), 'startup.log');
        fs.writeFileSync(logPath, startupLog.join('\n'), 'utf-8');
        log(`日誌已寫入: ${logPath}`);
    } catch (e) {
        // 忽略
    }
}

// App 事件
app.whenReady().then(async () => {
    log('=== sbss 啟動 ===');
    log(`Electron 版本: ${process.versions.electron}`);
    log(`平台: ${process.platform}`);

    try {
        await startFlask();
        createWindow();
    } catch (err) {
        log(`啟動失敗: ${err.message}`);
        writeLogFile();
        showError('啟動失敗', err.message);
        app.quit();
    }
});

app.on('window-all-closed', () => {
    stopFlask();
    writeLogFile();
    app.quit();
});

app.on('before-quit', () => {
    stopFlask();
    writeLogFile();
});

app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
        createWindow();
    }
});
