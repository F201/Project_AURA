/**
 * Electron preload — contextBridge exposes a minimal safe API to the renderer.
 * Only the functions explicitly listed here are accessible from renderer code.
 */
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  /** Move the OS-level window to (x, y) — used for autonomous walking. */
  moveWindow: (x, y) => ipcRenderer.send('move-window', { x, y }),

  /** Returns { width, height } of the primary display work area. */
  getScreenSize: () => ipcRenderer.invoke('get-screen-size'),
})
