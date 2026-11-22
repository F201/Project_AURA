const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('auraDesktop', {
  setIgnoreMouse: (ignore) => ipcRenderer.send('set-ignore-mouse', ignore),
  setStreamVisible: (visible) => ipcRenderer.send('set-stream-visible', visible),
  setHitBox: (box) => ipcRenderer.send('set-hit-box', box),
  startDrag: () => ipcRenderer.send('start-drag'),
  stopDrag: () => ipcRenderer.send('stop-drag'),
  moveWindowBy: (dx, dy) => ipcRenderer.send('move-window-by', { dx, dy }),
  moveWindowTo: (x, y) => ipcRenderer.send('move-window-to', { x, y }),
  resizeWindow: (width, height) => ipcRenderer.send('resize-window', { width, height }),
  getBounds: () => ipcRenderer.invoke('get-bounds'),
  getScreenSize: () => ipcRenderer.invoke('get-screen-size'),
  openFolder: (kind) => ipcRenderer.send('open-folder', kind),
  onCursorPos: (cb) => {
    const handler = (_, data) => cb(data)
    ipcRenderer.on('cursor-pos', handler)
    return () => ipcRenderer.removeListener('cursor-pos', handler)
  },
  onHotkey: (cb) => {
    const handler = (_, action) => cb(action)
    ipcRenderer.on('hotkey', handler)
    return () => ipcRenderer.removeListener('hotkey', handler)
  },
})

// Keep legacy bridge for backward compatibility with StageApp / DragHandle
contextBridge.exposeInMainWorld('electronAPI', {
  moveWindow: (x, y) => ipcRenderer.send('move-window', { x, y }),
  getScreenSize: () => ipcRenderer.invoke('get-screen-size'),
})
