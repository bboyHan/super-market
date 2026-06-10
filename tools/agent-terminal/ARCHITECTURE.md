# Agent Terminal — 技术选型与架构决策

> 状态: 产品经理 vs 架构师 深度对抗后输出

---

## 第一轮：正面交锋

### 产品经理开场

> "我要一个漂亮的、代理商拿到就能用的工具。双击安装，打开就能干活。界面得像现代桌面软件，不要像程序员写的内部工具。更新要丝滑，不要让我去群里发安装包。"

### 架构师回应

> "底层全是重型武器——Playwright 控制浏览器、mitmproxy 抓包、ADB 操模拟器。这些都是 Python 生态的。强行用别的东西包一层，除了增加复杂度没有好处。咱们先看看技术栈的依赖关系。"

---

## 第二轮：技术依赖分析

### 核心依赖图谱

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Terminal                          │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                  UI 表示层                            │   │
│  │  需要: 现代化UI / 内嵌浏览器 / 日志实时滚动            │   │
│  │  选择: ❓ 待定                                        │   │
│  └────────────────────┬─────────────────────────────────┘   │
│                       │                                      │
│  ┌────────────────────▼─────────────────────────────────┐   │
│  │               业务逻辑层                               │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │ 采集引擎  │ │ 同步引擎  │ │ 账号管理  │ │ 策略引擎  │ │   │
│  │  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ │   │
│  └───────┼────────────┼────────────┼────────────┼───────┘   │
│           │            │            │            │           │
│  ┌────────▼────────────▼────────────▼────────────▼───────┐   │
│  │                  基础设施层                             │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │   │
│  │  │Playwright│ │ mitmproxy│ │   ADB    │ │ SQLite   │ │   │
│  │  │浏览器自动 │ │ 抓包代理  │ │ 模拟器控制│ │ 本地存储  │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                             │
│  所有基础设施层 → Python 生态                               │
│  业务逻辑层 → 密集调用 Python 库                             │
│  UI 表示层 → ❓ 选择空间                                    │
└─────────────────────────────────────────────────────────────┘
```

**结论：底层 100% 是 Python 生态。** 不管 UI 用什么，Python 进程必须存在。

---

## 第三轮：UI 方案对抗

### 备选方案

| 方案 | 技术栈 | 安装包大小 | UI 美观度 | 开发效率 | Python 调用方式 |
|------|--------|-----------|----------|---------|---------------|
| **A. PyQt6/PySide6** | 纯 Python | 60-100MB | ⭐⭐⭐ | ⭐⭐⭐ | 直接 import |
| **B. Electron + Python 侧车** | JS + Python | 150-200MB | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | HTTP/WS IPC |
| **C. Tauri + Python 侧车** | Rust + JS + Python | 20-50MB | ⭐⭐⭐⭐⭐ | ⭐⭐ | HTTP/WS IPC |
| **D. 本地 Web 服务器 + 浏览器** | FastAPI + HTML | 50-80MB | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 直接调用 |
| **E. Go 重写全栈** | Go + Web UI | 15-30MB | ⭐⭐⭐⭐ | ⭐ | 放弃 Python 生态 |

### 对抗焦点

#### 架构师力推 A（PyQt6）

```
理由：
  1. 零 IPC 开销——所有代码在一个进程
  2. 直接 import playwright、mitmproxy、adb
  3. 信号槽机制天然适合异步事件（采集进度、日志）
  4. Python 打包有 PyInstaller / Nuitka 成熟方案
  5. 维护一个代码库就够了

弱点（产品经理暴击）：
  PyQt6 的美观度天花板很低。QSS 再怎么调，也做不出 Notion/Linear 那种质感。
  内嵌 Chromium 浏览器看齐 Electron 的体积，不内嵌又没法展示网页。
  对代理商来说，"好看" = "信任"，一个丑的工具没人愿意用。
```

#### 产品经理力推 B（Electron + Python 侧车）

```
理由：
  1. UI 质量没有上限——Tailwind/Shadcn 随便用
  2. 可以内嵌 Chromium 浏览器窗口（Playwright 操作可见）
  3. 自动更新有成熟方案（electron-updater）
  4. 开发效率高——前端生态秒杀 PyQt
  5. Python 侧车只做重型计算，UI 响应不阻塞

弱点（架构师暴击）：
  两个进程之间走 HTTP/WS IPC，采集进度要序列化反序列化。
  部署要打包两个运行时（Node + Python），安装包 200MB+。
  Python 侧车崩溃了 UI 还不知道，状态同步容易出 bug。
  维护两个代码库的成本。
```

#### 架构师反击方案 C（Tauri + Python 侧车）

```
修正 Electron 的缺点：
  1. 安装包 20-50MB（Tauri = 系统 WebView，不捆绑 Chromium）
  2. Rust 侧启动 Python 子进程更可靠
  3. UI 质量一样高
  4. 自动更新也有

弱点（双方共识）：
  Rust → Python IPC 链路更复杂。
  团队 Rust 能力 + Python 能力双重要求。
  出问题排查链路长：UI 层 → Rust 层 → Python 层。
  P0 功能还没做就先搭了三层架构。
```

#### 架构师提出方案 D（本地 Web + 浏览器）

```
破局思路：
  1. FastAPI 启动一个本地服务器（localhost:8800）
  2. 用户用浏览器打开 http://localhost:8800
  3. Python 全栈，零 IPC
  4. 前端 Vue/React 随便选
  5. 打包可以用 PyInstaller + 内嵌浏览器

弱点：
  用户要"打开浏览器访问 localhost"——体验不够桌面化。
  没有系统托盘，最小化不方便。
  不过可以用 PyWebView 或 electron 壳包装一下。
```

---

## 第四轮：最优解诞生

### 对抗结论：**方案 E — Python 本地服务 + Electron 薄壳**

```
这不是上面任何一个选项，而是吸收了各自优点的混合方案。

┌─────────────────────────────────────────────────────────────┐
│                    Agent Terminal                           │
│                                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Electron 薄壳（仅 UI）                   │   │
│  │  - 只负责渲染前端页面                                 │   │
│  │  - 内嵌 Chromium（自带）                              │   │
│  │  - 系统托盘、自动更新                                 │   │
│  │  - 启动时自动拉起 Python 后端                         │   │
│  │  - 关闭时发送 SIGTERM                                 │   │
│  │  - 崩溃时自动重启 Python 后端                         │   │
│  └────────────────────────┬────────────────────────────┘   │
│                           │ HTTP (localhost:8800)           │
│  ┌────────────────────────▼────────────────────────────┐   │
│  │           Python 后端（FastAPI + Uvicorn）            │   │
│  │                                                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────┐ │   │
│  │  │ 采集引擎  │ │ 同步引擎  │ │ 账号管理  │ │ WebSocket│ │   │
│  │  │Playwright│ │ 上传/同步 │ │ Cookie   │ │ 平台通讯 │ │   │
│  │  │ mitmproxy│ │ SQLite   │ │ 加密存储  │ │         │ │   │
│  │  │ ADB      │ │          │ │          │ │         │ │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └────────┘ │   │
│  │                                                      │   │
│  │  端口: 8800 (仅监听 localhost)                        │   │
│  │  API: REST + Server-Sent Events (SSE) 推日志        │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                            │
│  数据流:                                                    │
│  用户点击 UI → HTTP 请求 → Python 执行 → SSE 推回进度      │
└─────────────────────────────────────────────────────────────┘
```

### 为什么这是最优解

#### 对产品经理（赢了 UI）

| 诉求 | 满足方式 |
|------|---------|
| 现代化漂亮 UI | 前端技术栈无限制，Vue/React + Tailwind + Shadcn |
| 双击安装就用 | electron-builder 打包 NSIS 安装包 |
| 自动更新 | electron-updater，发新版自动提示更新 |
| 内嵌浏览器窗口 | Electron 自带 Chromium |
| 系统托盘 | electron 原生支持托盘 |
| 安装包别太大 | 50-80MB（不含 Python，打包时嵌入最小化 Python 环境） |

#### 对架构师（赢了架构）

| 诉求 | 满足方式 |
|------|---------|
| Python 生态全利用 | Playwright / mitmproxy / ADB 全部直接 Python import |
| 零 IPC 心智负担 | 前端只管发 HTTP 请求、收 SSE 事件，无复杂 IPC |
| Python 进程管理 | Electron 直接管理子进程生命周期 |
| 调试容易 | 后端可以独立启动、独立调试 `uvicorn agent_server:app` |
| 测试容易 | 所有业务逻辑在 Python 侧，标准 pytest |
| 崩溃恢复 | Python 进程挂了 → Electron 检测到 → 自动重启 |

### 技术选型详情

| 层面 | 选择 | 理由 |
|------|------|------|
| **UI 框架** | Electron + Vue 3 + Tailwind CSS | 与平台前端技术栈一致，复用工具体验 |
| **UI 组件库** | Shadcn Vue | 高质量、可定制的组件 |
| **后端框架** | FastAPI + Uvicorn | 异步、高性能、自动文档 |
| **后端语言** | Python 3.12+ | Playwright/mitmproxy/ADB 全部原生 |
| **浏览器自动化** | Playwright (Python) | 比 Selenium 快 10 倍，自动等待，反检测 |
| **抓包代理** | mitmproxy | 纯 Python，可编程，支持 HTTPS 解密 |
| **模拟器控制** | ADB (subprocess) + Pure Python SDK | 最稳定，无需额外库 |
| **CDP 集成** | Playwright CDP Session | Playwright 内置 CDP 支持 |
| **本地数据库** | SQLite + SQLCipher (加密) | 零配置，加密存储 Cookie |
| **实时推送** | SSE (Server-Sent Events) | 比 WebSocket 轻量，浏览器原生支持 |
| **打包分发** | electron-builder + PyInstaller | 成熟的打包方案 |
| **自动更新** | electron-updater | 业界标准 |
| **进程管理** | Node.js child_process + 健康检查 | 内置方案，零依赖 |

### 目录结构（预设计）

```
tools/agent-terminal/
├── electron/                    # Electron 壳
│   ├── main.ts                  # 主进程（启动 Python、管理窗口）
│   ├── preload.ts               # 预加载脚本
│   ├── updater.ts               # 自动更新
│   └── package.json
├── src/                         # UI 前端 (Vue 3)
│   ├── App.vue
│   ├── pages/
│   │   ├── dashboard.vue
│   │   ├── tasks.vue            # 采集任务（核心页面）
│   │   ├── inventory.vue
│   │   ├── accounts.vue
│   │   └── logs.vue
│   ├── components/
│   │   ├── TaskProgress.vue     # 采集进度组件
│   │   ├── StepLog.vue          # 步骤级日志
│   │   └── BrowserView.vue      # 内嵌浏览器
│   └── stores/
├── server/                      # Python 后端
│   ├── main.py                  # FastAPI 入口
│   ├── routers/
│   │   ├── tasks.py             # 采集任务 API
│   │   ├── inventory.py         # 库存管理 API
│   │   ├── accounts.py          # 账号管理 API
│   │   └── platform.py          # 平台通讯 API
│   ├── collectors/              # 采集引擎（核心）
│   │   ├── base.py              # 抽象采集器
│   │   ├── browser.py           # 浏览器自动化
│   │   ├── emulator.py          # 模拟器抓包
│   │   ├── cdp_helper.py        # CDP 辅助捕获
│   │   └── manual.py            # 手动录入
│   ├── adapters/                # 平台适配器
│   │   ├── jd.py                # 京东
│   │   ├── tb.py                # 淘宝
│   │   └── dy.py                # 抖音
│   ├── services/
│   │   ├── sync.py              # 平台同步
│   │   ├── account.py           # 账号管理
│   │   └── strategy.py          # 策略引擎
│   └── storage/
│       ├── db.py                # SQLite
│       └── crypto.py            # 加密
├── requirements.txt
├── package.json                 # Electron + Vue
└── README.md                    # 产品设计文档
```

---

## 架构师最终点评

```
这套方案的核心优势在于"分离但不分割"：

  Electron 只做两件事：
    1. 画 UI（它最擅长的）
    2. 管进程（它擅长的）

  Python 后端正经事：
    1. 控制浏览器（Playwright）
    2. 抓网络包（mitmproxy）
    3. 操模拟器（ADB）
    4. 管数据库（SQLite）
    5. 跟平台通讯（HTTP + WS）

  中间就一层 HTTP REST + SSE，没有任何花哨的 IPC。
  每一层都可以独立开发、独立测试、独立部署。

  风险点：
    1. Python 环境打包体积（~50MB 压缩）
       → 用 embeddable Python + 按需安装依赖
    2. Electron 内存占用（~200MB 基线）
       → 对桌面工具可接受，用户电脑通常 8G+
    3. Python 后端崩溃检测延迟
       → 每 5 秒健康检查，失败自动重启
```

---

> 下一步：基于此架构产出原型交互 HTML，供产品体验后确认方向。
