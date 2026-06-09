/// <reference types="vite/client" />

interface ElectronAPI {
  BACKEND_URL: string
  openFileDialog: (options?: {
    filters?: Array<{ name: string; extensions: string[] }>
  }) => Promise<string[]>
  platform: string
}

interface Window {
  electronAPI: ElectronAPI
}
