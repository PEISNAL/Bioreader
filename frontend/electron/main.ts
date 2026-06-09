/**
 * BioReader — Electron 主进程
 *
 * 职责：
 * 1. 通过 child_process 拉起 Python FastAPI 后端微服务
 * 2. 管理后端生命周期（启动 / 健康检查 / 退出清理）
 * 3. 创建 BrowserWindow 并加载渲染进程
 *
 * 架构规范：
 * - 零网络依赖：运行期不发起任何外部网络请求
 * - 前后端分离：渲染进程通过 127.0.0.1 HTTP 与后端通信
 * - 单实例后端：端口固定 18000，避免与其他服务冲突
 */

import { app, shell, BrowserWindow } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import { ChildProcess, spawn } from 'child_process'
import * as http from 'http'

// -------------------- 常量 --------------------

const BACKEND_PORT = 18000
const BACKEND_HOST = '127.0.0.1'
const BACKEND_URL = `http://${BACKEND_HOST}:${BACKEND_PORT}`

/** 后端启动最大等待时间 (ms) */
const BACKEND_STARTUP_TIMEOUT = 30_000
/** 健康检查轮询间隔 (ms) */
const HEALTH_CHECK_INTERVAL = 500

// -------------------- 后端子进程管理 --------------------

let pythonProcess: ChildProcess | null = null

/** 获取 Python 可执行文件路径（优先使用虚拟环境中的 python） */
function getPythonExe(): string {
  const isDev = !app.isPackaged
  if (isDev) {
    // 开发模式：使用 backend/venv 中的 python
    const venvPython = join(app.getAppPath(), '..', 'backend', 'venv', 'Scripts', 'python.exe')
    return venvPython
  }
  // 生产模式：使用打包后的 python（后续由 electron-builder 配置）
  const bundledPython = join(process.resourcesPath, 'backend', 'venv', 'Scripts', 'python.exe')
  return bundledPython
}

/** 获取后端入口脚本路径 */
function getBackendEntry(): string {
  const isDev = !app.isPackaged
  if (isDev) {
    return join(app.getAppPath(), '..', 'backend', 'app', 'main.py')
  }
  return join(process.resourcesPath, 'backend', 'app', 'main.py')
}

/** 启动 Python 后端微服务 */
function startPythonBackend(): Promise<void> {
  return new Promise((resolve, reject) => {
    const pythonExe = getPythonExe()
    const backendEntry = getBackendEntry()

    console.log(`[BioReader] 启动后端: ${pythonExe}`)
    console.log(`[BioReader] 入口脚本: ${backendEntry}`)

    // uvicorn 直接运行 FastAPI app
    pythonProcess = spawn(pythonExe, [
      '-m', 'uvicorn',
      'app.main:app',
      '--host', BACKEND_HOST,
      '--port', String(BACKEND_PORT),
      '--log-level', 'info'
    ], {
      cwd: join(backendEntry, '..', '..'),  // backend/ 目录
      stdio: ['ignore', 'pipe', 'pipe'],
      env: {
        ...process.env,
        PYTHONUNBUFFERED: '1'  // 确保日志实时输出
      }
    })

    // 转发 stdout / stderr 到 Electron 控制台
    pythonProcess.stdout?.on('data', (data: Buffer) => {
      console.log(`[Python:out] ${data.toString().trimEnd()}`)
    })

    pythonProcess.stderr?.on('data', (data: Buffer) => {
      console.error(`[Python:err] ${data.toString().trimEnd()}`)
    })

    pythonProcess.on('error', (err) => {
      console.error('[BioReader] 后端进程启动失败:', err.message)
      reject(new Error(`无法启动 Python 后端: ${err.message}`))
    })

    pythonProcess.on('exit', (code, signal) => {
      console.log(`[BioReader] 后端进程退出 (code=${code}, signal=${signal})`)
      pythonProcess = null
    })

    // 轮询等待后端就绪
    const startTime = Date.now()
    const checkHealth = (): void => {
      if (Date.now() - startTime > BACKEND_STARTUP_TIMEOUT) {
        killPythonBackend()
        reject(new Error(`后端启动超时 (${BACKEND_STARTUP_TIMEOUT / 1000}s)`))
        return
      }

      http.get(`${BACKEND_URL}/health`, (res) => {
        let body = ''
        res.on('data', (chunk: string) => { body += chunk })
        res.on('end', () => {
          try {
            const data = JSON.parse(body)
            if (data.status === 'healthy') {
              console.log('[BioReader] 后端就绪:', JSON.stringify(data))
              resolve()
            } else {
              setTimeout(checkHealth, HEALTH_CHECK_INTERVAL)
            }
          } catch {
            setTimeout(checkHealth, HEALTH_CHECK_INTERVAL)
          }
        })
      }).on('error', () => {
        // 后端尚未就绪，继续等待
        setTimeout(checkHealth, HEALTH_CHECK_INTERVAL)
      })
    }

    // 给子进程一点启动时间后开始健康检查
    setTimeout(checkHealth, 1000)
  })
}

/** 停止 Python 后端 */
function killPythonBackend(): void {
  if (!pythonProcess) return

  console.log('[BioReader] 正在关闭后端进程...')

  // Windows 上 SIGTERM 可能无效，使用 taskkill 确保清理
  if (process.platform === 'win32') {
    try {
      const { execSync } = require('child_process')
      execSync(`taskkill /pid ${pythonProcess.pid} /T /F 2>nul`, { stdio: 'ignore' })
    } catch {
      // taskkill 可能因进程已退出而报错，忽略
    }
  } else {
    pythonProcess.kill('SIGTERM')
  }

  pythonProcess = null
  console.log('[BioReader] 后端进程已关闭')
}

// -------------------- 窗口管理 --------------------

function createWindow(): void {
  const mainWindow = new BrowserWindow({
    width: 1280,
    height: 800,
    minWidth: 900,
    minHeight: 600,
    show: false,
    title: 'BioReader — 生命科学文献阅读器',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.webContents.setWindowOpenHandler((details) => {
    shell.openExternal(details.url)
    return { action: 'deny' }
  })

  // 开发模式用 HMR URL，生产模式加载打包文件
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// -------------------- 应用生命周期 --------------------

app.whenReady().then(async () => {
  electronApp.setAppUserModelId('com.bioreader.app')

  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // 1. 先启动 Python 后端
  try {
    await startPythonBackend()
  } catch (err) {
    console.error('[BioReader] 后端启动失败:', (err as Error).message)
    // 即使后端失败也创建窗口，让前端显示错误状态
  }

  // 2. 创建窗口
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 退出前清理后端子进程
app.on('before-quit', () => {
  killPythonBackend()
})

app.on('will-quit', () => {
  killPythonBackend()
})
