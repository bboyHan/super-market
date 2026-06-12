const { app, BrowserWindow, BrowserView, Tray, Menu, nativeImage, ipcMain } = require('electron');
const path = require('path');
const DataProbeBridge = require('./data_probe_bridge');

const isDev = !app.isPackaged;
const VITE_PORT = 5173;

let mainWindow = null;
let collectorView = null;
let tray = null;
let dataProbe = null;
let captureCount = 0;
let dataProbeRunning = false;

// ═══════════════════════════════════════════
// DataProbe 引擎管理（替换 Python 后端 + mitmproxy）
// ═══════════════════════════════════════════

async function startDataProbe() {
  dataProbe = new DataProbeBridge({ apiPort: 18801 });
  dataProbe.onStatusChange((running) => {
    dataProbeRunning = running;
    if (mainWindow) mainWindow.webContents.send('dataprobe-status', { running });
    if (tray) tray.setToolTip(running ? 'DataProbe: 运行中' : 'DataProbe: 已停止');
  });
  const ok = await dataProbe.start();
  if (!ok) console.error('[AT] DataProbe 启动失败');
  return ok;
}

function stopDataProbe() {
  if (dataProbe) { dataProbe.stop(); dataProbe = null; }
  dataProbeRunning = false;
}

// ═══════════════════════════════════════════
// IPC 处理器
// ═══════════════════════════════════════════

function setupIPC() {
  ipcMain.on('capture-credential', async (event, credential) => {
    captureCount++;
    console.log(`[AT] #${captureCount}: ${credential.product || credential.type}`);
    if (dataProbe && dataProbeRunning) {
      try { await dataProbe.ingestData(credential); }
      catch (e) { console.warn('[AT] 转发失败:', e.message); }
    }
  });

  ipcMain.handle('get-status', async () => {
    const s = dataProbeRunning ? await dataProbe.getStatus().catch(() => null) : null;
    return { dataprobe: dataProbeRunning, captureCount, dataprobeStatus: s, browserViewActive: !!collectorView };
  });

  ipcMain.handle('start-investigation', async (event, target) => {
    if (!dataProbe || !dataProbeRunning) throw new Error('DataProbe 未运行');
    return await dataProbe.startInvestigation(target);
  });

  ipcMain.handle('stop-investigation', async () => {
    if (!dataProbe) return { status: 'not_running' };
    return await dataProbe.stopInvestigation();
  });

  ipcMain.handle('get-evidence', async () => {
    if (!dataProbe) return { items: [] };
    return await dataProbe.getEvidence();
  });

  ipcMain.handle('get-session', async () => {
    if (!dataProbe) return null;
    return await dataProbe.getSession();
  });

  ipcMain.handle('get-data', async () => {
    if (!dataProbe) return { items: [] };
    return await dataProbe.getCapturedData();
  });

  ipcMain.handle('get-rules', async () => {
    if (!dataProbe) return { rules: [] };
    return await dataProbe.getRules();
  });

  ipcMain.handle('open-browser', async (event, url) => {
    if (collectorView) { collectorView.webContents.loadURL(url); return; }
    collectorView = new BrowserView({
      webPreferences: {
        preload: path.join(__dirname, 'preload.js'),
        sandbox: false, nodeIntegration: false, contextIsolation: true,
      }
    });
    mainWindow.setBrowserView(collectorView);
    const b = mainWindow.getBounds();
    collectorView.setBounds({ x: 0, y: 0, width: b.width, height: b.height - 50 });
    collectorView.webContents.loadURL(url);
    collectorView.webContents.on('did-navigate', () => {
      mainWindow.webContents.send('url-changed', collectorView.webContents.getURL());
    });
    collectorView.setAutoResize({ width: true, height: true });
  });

  ipcMain.handle('close-browser', async () => {
    if (collectorView) { mainWindow.removeBrowserView(collectorView); collectorView.destroy(); collectorView = null; }
  });
}

// ═══════════════════════════════════════════
// 窗口创建
// ═══════════════════════════════════════════

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280, height: 900, minWidth: 900, minHeight: 600,
    title: '神机数探 — DataProbe',
    icon: path.join(__dirname, '..', 'icons', 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false, contextIsolation: true,
    },
    frame: true, show: false,
  });

  if (isDev) mainWindow.loadURL(`http://localhost:${VITE_PORT}`);
  else mainWindow.loadFile(path.join(__dirname, '..', 'dist', 'index.html'));

  mainWindow.once('ready-to-show', () => mainWindow.show());
  mainWindow.on('closed', () => { mainWindow = null; collectorView = null; });

  tray = new Tray(nativeImage.createEmpty());
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: '显示窗口', click: () => mainWindow?.show() },
    { type: 'separator' },
    { label: '退出', click: () => app.quit() },
  ]));
  tray.setToolTip('DataProbe — 数据开采对抗平台');
  tray.on('click', () => mainWindow?.show());
}

// ═══════════════════════════════════════════
// 应用生命周期
// ═══════════════════════════════════════════

app.whenReady().then(async () => {
  setupIPC();
  createWindow();
  const ok = await startDataProbe();
  console.log(`[AT] DataProbe: ${ok ? '✅' : '❌'}`);
  app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });
});

app.on('window-all-closed', () => { stopDataProbe(); if (process.platform !== 'darwin') app.quit(); });
app.on('before-quit', () => { stopDataProbe(); });
