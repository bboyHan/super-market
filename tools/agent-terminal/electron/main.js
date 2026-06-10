const { app, BrowserWindow, BrowserView, Tray, Menu, nativeImage, dialog, ipcMain, session } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const http = require('http');

const isDev = !app.isPackaged;
const SERVER_PORT = 8800;
const VITE_PORT = 5173;

let mainWindow = null;
let collectorView = null;
let tray = null;
let serverProcess = null;
let mitmProcess = null;
let captureCount = 0;

// ═══════════════════════════════════════════
// Python Backend
// ═══════════════════════════════════════════

function getServerPath() {
  if (isDev) return path.join(__dirname, '..', 'server', 'main.py');
  return path.join(process.resourcesPath, 'agent-terminal-server');
}

function getVenvPython() {
  return [
    path.join(__dirname, '..', 'server', 'venv', 'bin', 'python'),
    path.join(__dirname, '..', 'server', '.venv', 'bin', 'python'),
    'python3', 'python',
  ];
}

function startServer() {
  const serverPath = getServerPath();
  const pythonCmds = isDev ? getVenvPython() : ['agent-terminal-server'];
  
  function tryStart(index = 0) {
    if (index >= pythonCmds.length) {
      dialog.showErrorBox('启动失败', '无法找到 Python 环境');
      return;
    }
    const cmd = pythonCmds[index];
    console.log(`[AT] 尝试启动后端: ${cmd} ${serverPath}`);
    const proc = spawn(cmd, [serverPath], {
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env, AGENT_TERMINAL: '1' },
    });
    proc.stdout.on('data', d => console.log(`[backend] ${d}`));
    proc.stderr.on('data', d => console.log(`[backend] ${d}`));
    proc.on('error', () => tryStart(index + 1));
    proc.on('exit', (code) => {
      if (code !== 0 && index < pythonCmds.length - 1) tryStart(index + 1);
    });
    serverProcess = proc;
  }
  tryStart();
}

// ═══════════════════════════════════════════
// mitmproxy Management
// ═══════════════════════════════════════════

function getMitmPath() {
  if (isDev) return path.join(__dirname, '..', 'mitmproxy', 'mitmdump');
  return path.join(process.resourcesPath, 'mitmdump');
}

function startMitmProxy() {
  const mitmPath = getMitmPath();
  const scriptPath = path.join(__dirname, '..', 'mitmproxy', 'pay_collector.py');
  
  mitmProcess = spawn(mitmPath, [
    '-s', scriptPath,
    '--listen-host', '0.0.0.0',
    '--listen-port', '8802',
    '--ssl-insecure',
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  mitmProcess.stdout.on('data', d => console.log(`[mitm] ${d}`));
  mitmProcess.stderr.on('data', d => console.log(`[mitm] ${d}`));
  mitmProcess.on('exit', (code) => console.log(`[mitm] exit ${code}`));
}

function stopMitmProxy() {
  if (mitmProcess) {
    mitmProcess.kill();
    mitmProcess = null;
  }
}

// ═══════════════════════════════════════════
// IPC Handlers
// ═══════════════════════════════════════════

function setupIPC() {
  // Capture event from preload
  ipcMain.on('capture-credential', (event, credential) => {
    captureCount++;
    console.log(`[AT] 已采集 #${captureCount}: ${credential.product}`);
    // Forward to backend
    const postData = JSON.stringify(credential);
    const req = http.request({
      hostname: 'localhost', port: 8800, path: '/api/collector/capture',
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': postData.length },
    });
    req.write(postData);
    req.end();
  });

  // Status query
  ipcMain.handle('get-collector-status', async () => {
    return {
      browser: { active: !!collectorView, count: captureCount },
      pcgame: { active: !!mitmProcess, count: 0 },
      mobile: { active: false, count: 0 },
      backend: !!serverProcess,
      platform: true,
      totalCount: captureCount,
    };
  });

  // Start collector browser
  ipcMain.handle('open-collector-browser', async (event, url) => {
    if (collectorView) {
      collectorView.webContents.loadURL(url);
      return;
    }
    collectorView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        sandbox: false,
        nodeIntegration: false,
        contextIsolation: true,
      }
    });
    mainWindow.setBrowserView(collectorView);
    const bounds = mainWindow.getBounds();
    collectorView.setBounds({ x: 0, y: 0, width: bounds.width, height: bounds.height - 50 });
    collectorView.webContents.loadURL(url);
    
    collectorView.webContents.on('did-navigate', () => {
      mainWindow.webContents.send('url-changed', collectorView.webContents.getURL());
    });
    
    collectorView.setAutoResize({ width: true, height: true });
  });

  // Start mitmproxy
  ipcMain.handle('start-mitm', async () => {
    startMitmProxy();
    return { success: true };
  });

  // Stop mitmproxy
  ipcMain.handle('stop-mitm', async () => {
    stopMitmProxy();
    return { success: true };
  });
}

// ═══════════════════════════════════════════
// Window Creation
// ═══════════════════════════════════════════

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 900,
    minWidth: 900,
    minHeight: 600,
    title: 'Agent Terminal — 支付凭证采集器',
    icon: path.join(__dirname, '..', 'icons', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
    },
    frame: true,
    show: false,
  });

  if (isDev) {
    mainWindow.loadURL(`http://localhost:${VITE_PORT}`);
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));
  }

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => {
    mainWindow = null;
    collectorView = null;
  });

  // Tray
  tray = new Tray(nativeImage.createEmpty());
  const contextMenu = Menu.buildFromTemplate([
    { label: '显示窗口', click: () => mainWindow?.show() },
    { label: '退出', click: () => app.quit() },
  ]);
  tray.setToolTip('Agent Terminal');
  tray.setContextMenu(contextMenu);
  tray.on('click', () => mainWindow?.show());
}

// ═══════════════════════════════════════════
// App Lifecycle
// ═══════════════════════════════════════════

app.whenReady().then(() => {
  setupIPC();
  createWindow();
  startServer();
  
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  stopMitmProxy();
  if (serverProcess) serverProcess.kill();
  if (process.platform !== 'darwin') app.quit();
});

app.on('before-quit', () => {
  stopMitmProxy();
  if (serverProcess) serverProcess.kill();
});
