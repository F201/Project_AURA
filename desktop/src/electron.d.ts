// Type declarations for the contextBridge API exposed in preload.js
interface ElectronAPI {
  moveWindow(x: number, y: number): void
  getScreenSize(): Promise<{ width: number; height: number }>
}

declare global {
  interface Window {
    electronAPI?: ElectronAPI
  }
}

export {}
