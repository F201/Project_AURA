/**
 * Electron main process — Phase 4
 * Creates a transparent, frameless, always-on-top window for the AURA desktop overlay.
 * Window position is controlled via IPC so the renderer can drive autonomous walking.
 */

const { app, BrowserWindow, ipcMain, Menu, Tray, screen } = require('electron')
const path = require('path')

let win
let tray

const isDev = process.env.NODE_ENV === 'development' || !app.isPackaged

app.whenReady().then(() => {
  win = new BrowserWindow({
    width:       400,
    height:      620,
    transparent: true,
    frame:       false,
    alwaysOnTop: true,
    skipTaskbar: false,
    hasShadow:   false,
    resizable:   false,
    // Start near bottom-centre of primary display
    ...getInitialPosition(),
    webPreferences: {
      preload:          path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration:  false,
    },
  })

  // Windows 11: stay above fullscreen apps (game windows, etc.)
  win.setAlwaysOnTop(true, 'screen-saver')

  if (isDev) {
    win.loadURL('http://localhost:5174')
    // win.webContents.openDevTools({ mode: 'detach' })  // uncomment to debug
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  // ── Tray icon ─────────────────────────────────────────────────────────────
  const iconPath = path.join(__dirname, '../assets/icon.ico')
  tray = new Tray(iconPath)
  tray.setToolTip('AURA Desktop')
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Show / Hide',  click: () => win.isVisible() ? win.hide() : win.show() },
    { type: 'separator' },
    { label: 'Quit AURA',   click: () => app.quit() },
  ]))
  tray.on('double-click', () => win.isVisible() ? win.hide() : win.show())
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// ── IPC: window movement for autonomous walking ────────────────────────────
ipcMain.on('move-window', (_, { x, y }) => {
  if (win) win.setPosition(Math.round(x), Math.round(y), true)
})

ipcMain.handle('get-screen-size', () => {
  return screen.getPrimaryDisplay().workAreaSize
})

// ── Helpers ────────────────────────────────────────────────────────────────
function getInitialPosition() {
  const { width, height } = screen.getPrimaryDisplay().workAreaSize
  return {
    x: Math.round(width / 2 - 200),   // horizontally centred
    y: Math.round(height - 640),       // near bottom of screen
  }
}
