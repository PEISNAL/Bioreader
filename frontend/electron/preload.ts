/**
 * BioReader — Preload 脚本
 *
 * 通过 contextBridge 向渲染进程暴露安全的 API。
 * 渲染进程对后端的 HTTP 请求直接通过 fetch 发往 127.0.0.1，
 * 不走 IPC（符合 "前后端通过本地环回直接通信" 的规范）。
 * 仅文件对话框等需要原生能力时才走 IPC。
 */

import { contextBridge, ipcRenderer } from 'electron'

const electronAPI = {
  // ========== 后端通信 ==========
  /** 后端基地址 (仅供渲染进程拼接路径使用) */
  BACKEND_URL: 'http://127.0.0.1:18000',

  // ========== 原生对话框 (预留) ==========
  /** 打开文件选择对话框，返回文件路径数组 */
  openFileDialog: (options?: {
    filters?: Array<{ name: string; extensions: string[] }>
  }): Promise<string[]> => {
    return ipcRenderer.invoke('dialog:openFile', options)
  },

  // ========== 平台信息 ==========
  platform: process.platform
}

contextBridge.exposeInMainWorld('electronAPI', electronAPI)
