/**
 * AURA Desktop — Electron Main Process
 * Transparent, frameless, always-on-top desktop companion overlay with:
 *  - 60Hz main-process silhouette hit-testing (clicks pass through empty space to games/apps)
 *  - DPI-proof 125Hz native dragging with persisted window bounds
 *  - Windows 11 HRGN top clip (SetWindowRgn) to prevent unfocused DWM ghost titlebars
 *  - 30Hz global cursor broadcasting for smooth eye/head tracking
 *  - Global hotkeys: Ctrl+Shift+M (Mute), Ctrl+Shift+B (Blind/Privacy),
 *                    Ctrl+Shift+H (Hide/Show), Ctrl+Shift+X (Interrupt)
 *  - System Tray controls + live OBS / Discord screen-share visibility toggle
 */

const { app, BrowserWindow, ipcMain, Menu, Tray, screen, globalShortcut, shell } = require('electron')
const path = require('path')
const fs = require('fs')

const WIN_W = 640
const WIN_H = 860
const TOP_CLIP = 36 // Physically clips off Windows 11's 0..31px unfocused DWM ghost titlebar via SetWindowRgn

let win = null
let tray = null
let cursorTimer = null
let dragTimer = null
let isDraggingWin = false
let uiForceInteractive = false
let lastIgnoreState = null
let clickThroughLocked = false
let streamVisible = true // Visible in OBS / Discord Screen Share by default
let hitBox = { x: 80, y: 120, w: 400, h: 610 }

const isDev = process.argv.includes('--dev') || process.env.VITE_DEV === '1'
const BOUNDS_FILE = path.join(app.getPath('userData'), 'aura-window-bounds.json')

function loadSavedBounds() {
  const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
  const defaultBounds = {
    width: WIN_W,
    height: WIN_H,
    x: Math.round(sw - WIN_W - 20),
    y: Math.round(sh - WIN_H),
  }
  try {
    if (fs.existsSync(BOUNDS_FILE)) {
      const parsed = JSON.parse(fs.readFileSync(BOUNDS_FILE, 'utf-8'))
      if (parsed && typeof parsed.x === 'number' && typeof parsed.y === 'number') {
        return {
          width: WIN_W,
          height: WIN_H,
          x: Math.max(-220, Math.min(sw - 120, parsed.x)),
          y: Math.max(-120, Math.min(sh - 140, parsed.y)),
        }
      }
    }
  } catch { /* ignore */ }
  return defaultBounds
}

function saveBounds() {
  if (!win || win.isDestroyed()) return
  try {
    const b = win.getBounds()
    fs.writeFileSync(BOUNDS_FILE, JSON.stringify(b))
  } catch { /* ignore */ }
}

function createWindow() {
  const bounds = loadSavedBounds()

  win = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    x: bounds.x,
    y: bounds.y,
    title: '',
    transparent: true,
    frame: false,
    thickFrame: false,
    roundedCorners: false,
    autoHideMenuBar: true,
    alwaysOnTop: true,
    skipTaskbar: false,
    hasShadow: false,
    resizable: false,
    minWidth: 240,
    minHeight: 340,
    maxWidth: 880,
    maxHeight: 980,
    backgroundColor: '#00000000',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  })

  win.setMenu(null)

  // Keep AURA above borderless-windowed games & apps
  win.setAlwaysOnTop(true, 'screen-saver', 1)
  win.setVisibleOnAllWorkspaces(true, { visibleOnFullScreen: true })

  // Default visible in OBS / Discord Screen Share; toggleable in Drawer or System Tray
  win.setContentProtection(!streamVisible)

  // Kernel-level HRGN clip (y=36..WIN_H): prevents Windows 11 DWM from painting
  // an unfocused titlebar strip above the transparent frameless overlay
  const applyCleanShape = () => {
    if (!win || win.isDestroyed()) return
    try {
      if (typeof win.setShape === 'function') {
        win.setShape([{ x: 0, y: TOP_CLIP, width: WIN_W, height: WIN_H - TOP_CLIP }])
      }
    } catch { /* ignore */ }
  }
  win.once('ready-to-show', applyCleanShape)
  win.on('show', applyCleanShape)
  win.on('blur', applyCleanShape)
  setTimeout(applyCleanShape, 250)

  // Start interactive; 60Hz main-process hit-test toggles click-through cleanly when cursor leaves the avatar
  win.setIgnoreMouseEvents(false)
  lastIgnoreState = false

  if (isDev) {
    win.loadURL('http://localhost:5174')
  } else {
    win.loadFile(path.join(__dirname, '../dist/index.html'))
  }

  win.on('moved', saveBounds)

  // 60Hz main-process cursor loop:
  //   1) Reliable click-through toggle matching the scaled avatar silhouette
  //   2) Global cursor position broadcast at ~30Hz for eye/head gaze tracking
  let tickCount = 0
  cursorTimer = setInterval(() => {
    if (!win || win.isDestroyed() || !win.isVisible()) return
    try {
      const pt = screen.getCursorScreenPoint()
      const b = win.getBounds()

      const relX = pt.x - b.x
      const relY = pt.y - b.y
      const inside =
        relX >= hitBox.x &&
        relX <= hitBox.x + hitBox.w &&
        relY >= Math.max(TOP_CLIP, hitBox.y) &&
        relY <= hitBox.y + hitBox.h

      const wantIgnore = clickThroughLocked
        ? true
        : !(isDraggingWin || uiForceInteractive || inside)

      if (wantIgnore !== lastIgnoreState) {
        lastIgnoreState = wantIgnore
        win.setIgnoreMouseEvents(wantIgnore)
      }

      tickCount++
      // Every ~1.5s re-assert screen-saver always-on-top so borderless-windowed games do not bury the overlay
      if (tickCount % 90 === 0 && !win.isFocused()) {
        win.setAlwaysOnTop(true, 'screen-saver', 1)
        win.moveTop()
      }
      if (tickCount % 2 === 0) {
        const disp = screen.getDisplayNearestPoint(pt)
        win.webContents.send('cursor-pos', {
          screenX: pt.x,
          screenY: pt.y,
          winX: b.x,
          winY: b.y,
          winW: b.width,
          winH: b.height,
          dispW: disp.bounds.width,
          dispH: disp.bounds.height,
        })
      }
    } catch { /* ignore */ }
  }, 16)

  // Tray icon
  const iconPath = path.join(__dirname, '../assets/icon.ico')
  if (fs.existsSync(iconPath)) {
    tray = new Tray(iconPath)
    tray.setToolTip('AURA — Live Desktop Companion')
    tray.setContextMenu(
      Menu.buildFromTemplate([
        {
          label: 'Show / Hide AURA (Ctrl+Shift+H)',
          click: () => toggleVisible(),
        },
        {
          label: 'Open Companion Settings Drawer',
          click: () => {
            if (win && !win.isVisible()) win.show()
            win?.webContents.send('hotkey', 'toggle-drawer')
          },
        },
        {
          label: 'Toggle Mic Mute (Ctrl+Shift+M)',
          click: () => win?.webContents.send('hotkey', 'toggle-mute'),
        },
        {
          label: 'Toggle Blind / Privacy Mode (Ctrl+Shift+B)',
          click: () => win?.webContents.send('hotkey', 'toggle-blind'),
        },
        {
          label: 'Visible in OBS / Discord Share',
          type: 'checkbox',
          checked: streamVisible,
          click: (menuItem) => {
            streamVisible = Boolean(menuItem.checked)
            if (win && !win.isDestroyed()) {
              win.setContentProtection(!streamVisible)
            }
          },
        },
        { type: 'separator' },
        {
          label: 'Reset Position',
          click: () => {
            const { width: sw, height: sh } = screen.getPrimaryDisplay().workAreaSize
            win?.setBounds({ width: WIN_W, height: WIN_H, x: Math.round(sw - WIN_W - 20), y: Math.round(sh - WIN_H) })
            saveBounds()
          },
        },
        {
          label: 'Open 3D Models Folder',
          click: () => {
            const dir = path.join(__dirname, '../public/models/3d')
            fs.mkdirSync(dir, { recursive: true })
            shell.openPath(dir)
          },
        },
        {
          label: 'Open Voice Clones Folder',
          click: () => {
            const dir = path.join(__dirname, '../../voice-agent/resources/voice')
            fs.mkdirSync(dir, { recursive: true })
            shell.openPath(dir)
          },
        },
        { type: 'separator' },
        { label: 'Quit AURA Desktop', click: () => app.quit() },
      ])
    )
    tray.on('double-click', toggleVisible)
  }

  // Register global hotkeys (work while gaming or using other apps)
  globalShortcut.register('CommandOrControl+Shift+M', () => {
    win?.webContents.send('hotkey', 'toggle-mute')
  })
  globalShortcut.register('CommandOrControl+Shift+B', () => {
    win?.webContents.send('hotkey', 'toggle-blind')
  })
  globalShortcut.register('CommandOrControl+Shift+H', () => {
    toggleVisible()
  })
  globalShortcut.register('CommandOrControl+Shift+X', () => {
    win?.webContents.send('hotkey', 'interrupt')
  })
}

function toggleVisible() {
  if (!win || win.isDestroyed()) return
  if (win.isVisible()) {
    win.hide()
  } else {
    win.show()
    win.setAlwaysOnTop(true, 'screen-saver')
  }
}

app.whenReady().then(createWindow)

app.on('will-quit', () => {
  globalShortcut.unregisterAll()
  if (cursorTimer) clearInterval(cursorTimer)
  stopNativeDrag()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit()
})

// ── IPC Handlers ─────────────────────────────────────────────────────────────
ipcMain.on('set-ignore-mouse', (_, ignore) => {
  uiForceInteractive = !ignore
  if (uiForceInteractive && win && !win.isDestroyed() && lastIgnoreState !== false) {
    lastIgnoreState = false
    win.setIgnoreMouseEvents(false)
  }
})

// DPI-proof 125Hz main-process dragging using native screen.getCursorScreenPoint()
ipcMain.on('start-drag', () => {
  if (!win || win.isDestroyed()) return
  stopNativeDrag()
  isDraggingWin = true
  win.setIgnoreMouseEvents(false)
  const startCursor = screen.getCursorScreenPoint()
  const startBounds = win.getBounds()
  dragTimer = setInterval(() => {
    if (!win || win.isDestroyed() || !isDraggingWin) {
      stopNativeDrag()
      return
    }
    const pt = screen.getCursorScreenPoint()
    const nx = Math.round(startBounds.x + (pt.x - startCursor.x))
    const ny = Math.round(startBounds.y + (pt.y - startCursor.y))
    // Use setBounds with fixed width/height to prevent Windows DPI window-shrink bug
    win.setBounds({ x: nx, y: ny, width: startBounds.width, height: startBounds.height })
  }, 8)
})

ipcMain.on('stop-drag', () => {
  stopNativeDrag()
  saveBounds()
})

function stopNativeDrag() {
  isDraggingWin = false
  if (dragTimer) {
    clearInterval(dragTimer)
    dragTimer = null
  }
}

ipcMain.on('move-window-by', (_, { dx, dy }) => {
  if (!win || win.isDestroyed()) return
  const b = win.getBounds()
  win.setBounds({
    x: Math.round(b.x + dx),
    y: Math.round(b.y + dy),
    width: b.width,
    height: b.height,
  })
})

ipcMain.on('move-window-to', (_, { x, y }) => {
  if (!win || win.isDestroyed()) return
  const b = win.getBounds()
  win.setBounds({
    x: Math.round(x),
    y: Math.round(y),
    width: b.width,
    height: b.height,
  })
})

// Backward compatibility with legacy StageApp/DragHandle IPC
ipcMain.on('move-window', (_, { x, y }) => {
  if (!win || win.isDestroyed()) return
  const b = win.getBounds()
  win.setBounds({
    x: Math.round(x),
    y: Math.round(y),
    width: b.width,
    height: b.height,
  })
})

ipcMain.on('set-stream-visible', (_, visible) => {
  streamVisible = Boolean(visible)
  if (win && !win.isDestroyed()) {
    win.setContentProtection(!streamVisible)
  }
})

ipcMain.on('set-hit-box', (_, box) => {
  if (box && typeof box.x === 'number') {
    hitBox = {
      x: Math.max(0, box.x),
      y: Math.max(TOP_CLIP, box.y),
      w: Math.max(80, box.w),
      h: Math.max(100, box.h),
    }
  }
})

ipcMain.on('resize-window', () => {
  // Scaling is handled smoothly in-canvas via avatarScale so OS window chrome is never mutated
})

ipcMain.handle('get-bounds', () => {
  if (!win || win.isDestroyed()) return { x: 0, y: 0, width: WIN_W, height: WIN_H }
  return win.getBounds()
})

ipcMain.handle('get-screen-size', () => {
  return screen.getPrimaryDisplay().workAreaSize
})

ipcMain.on('open-folder', (_, kind) => {
  const dir =
    kind === '3d'
      ? path.join(__dirname, '../public/models/3d')
      : path.join(__dirname, '../../voice-agent/resources/voice')
  fs.mkdirSync(dir, { recursive: true })
  shell.openPath(dir)
})
