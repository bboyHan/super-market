"""统一流量捕获引擎 — 支付采集器的核心。

对标 Fiddler/Wireshark 的理念：
- 启动后透明拦截系统 HTTP/HTTPS 流量
- 自动识别支付相关请求/响应
- 提取支付凭证（支付链接/Token/二维码）
- 用户无需选择采集模式
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from models import Credential, CredentialType, CredentialStatus

logger = logging.getLogger("agent-terminal.capture")


class CaptureEngine:
    """统一流量捕获引擎。

    职责：
    1. 管理 mitmproxy 进程（启动/停止/状态）
    2. 接收来自各渠道的原始采集数据
    3. 平台适配器识别 → 凭证结构化
    4. 触发凭证处理流水线
    """

    def __init__(self, mitm_port: int = 8802, backend_port: int = 8800):
        self._mitm_port = mitm_port
        self._backend_port = backend_port
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._capture_count = 0
        self._start_time: Optional[float] = None
        self._on_credential: Optional[Callable] = None
        self._platform_adapters: list = []
        self._sse_queues: list[asyncio.Queue] = []

    @property
    def is_running(self) -> bool:
        return self._running and (self._process is not None and self._process.poll() is None)

    @property
    def capture_count(self) -> int:
        return self._capture_count

    @property
    def uptime(self) -> float:
        if self._start_time and self.is_running:
            return time.time() - self._start_time
        return 0.0

    # ── 生命周期 ─────────────────────────────────────

    # 系统代理备份（用于恢复）
    _saved_proxy = None

    def set_callback(self, callback: Callable):
        """设置凭证回调（由上层注入处理器链）。"""
        self._on_credential = callback

    def register_adapter(self, adapter):
        """注册平台适配器。"""
        self._platform_adapters.append(adapter)
        logger.info(f"Platform adapter registered: {adapter.platform_name}")

    @staticmethod
    def _install_mitm_cert():
        """安装 mitmproxy CA 证书到系统受信任根证书颁发机构。"""
        try:
            import shutil
            home = os.path.expanduser("~")
            cert_src = os.path.join(home, ".mitmproxy", "mitmproxy-ca-cert.cer")
            if not os.path.isfile(cert_src):
                logger.info("mitmproxy CA cert not yet generated, waiting for mitmproxy to start...")
                # mitmproxy 首次启动会自动生成证书
                return False

            # 安装到 Windows 受信任根证书存储
            import subprocess
            result = subprocess.run(
                ["certutil", "-addstore", "-f", "Root", cert_src],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                logger.info("mitmproxy CA cert installed to Trusted Root Store")
                return True
            else:
                logger.warning(f"Cert install failed: {result.stderr.strip()}")
                return False
        except Exception as e:
            logger.warning(f"Failed to install mitmproxy CA cert: {e}")
            return False

    @staticmethod
    def _set_system_proxy(enable: bool, server: str = ""):
        """配置 Windows 系统代理。不影响用户原有设置，启动时设置，停止时恢复。"""
        try:
            import winreg
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS) as key:
                if enable:
                    # 备份当前代理服务器设置
                    try:
                        old_server, _ = winreg.QueryValueEx(key, "ProxyServer")
                    except FileNotFoundError:
                        old_server = ""
                    CaptureEngine._saved_proxy = old_server

                    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
                    logger.info(f"System proxy set to {server}")
                else:
                    winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
                    # 恢复备份的代理服务器
                    if CaptureEngine._saved_proxy:
                        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ,
                                          CaptureEngine._saved_proxy)
                        CaptureEngine._saved_proxy = None
                    logger.info("System proxy restored")

            # 通知系统代理变更（可选，某些系统需要）
            ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)  # INTERNET_OPTION_SETTINGS_CHANGED
            ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)  # INTERNET_OPTION_REFRESH
        except Exception as e:
            logger.warning(f"Failed to set system proxy: {e}")

    async def start(self) -> bool:
        """启动捕获引擎（启动 mitmproxy 子进程）。"""
        if self.is_running:
            logger.warning("Capture engine already running")
            return True

        # 查找 mitmdump 路径
        mitm_paths = self._find_mitm_paths()
        script_path = self._find_script_path()

        if not mitm_paths:
            logger.error("mitmdump not found. Check mitmproxy installation.")
            return False

        if not script_path:
            logger.error("mitmproxy script not found")
            return False

        mitm_path = mitm_paths[0]
        logger.info(f"Starting mitmdump: {mitm_path}")

        try:
            self._process = subprocess.Popen(
                [
                    mitm_path,
                    "-s", script_path,
                    "--listen-host", "0.0.0.0",
                    "--listen-port", str(self._mitm_port),
                    "--ssl-insecure",
                    "-q",  # quiet mode
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env={
                    **os.environ,
                    "BACKEND_URL": f"http://127.0.0.1:{self._backend_port}",
                },
            )
            self._running = True
            self._start_time = time.time()

            # CDP 模式不需要系统代理，代理模式请手动启用：
            # self._set_system_proxy(True, f"127.0.0.1:{self._mitm_port}")
            # self._install_mitm_cert()

            logger.info(f"Capture engine started on port {self._mitm_port}")
            return True
        except FileNotFoundError:
            logger.error(f"mitmdump not found at {mitm_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to start capture engine: {e}")
            return False

    async def stop(self) -> bool:
        """停止捕获引擎。"""
        if self._process:
            try:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            except Exception:
                pass
            self._process = None
        self._running = False
        # 恢复系统代理
        self._set_system_proxy(False)
        logger.info("Capture engine stopped")
        return True

    async def restart(self) -> bool:
        """重启捕获引擎。"""
        await self.stop()
        await asyncio.sleep(1)
        return await self.start()

    def get_status(self) -> dict:
        """获取引擎状态。"""
        return {
            "running": self.is_running,
            "port": self._mitm_port,
            "uptime_seconds": self.uptime,
            "capture_count": self._capture_count,
            "adapter_count": len(self._platform_adapters),
        }

    # ── 凭证接收 ─────────────────────────────────────

    async def ingest(self, raw_data: dict) -> Optional[Credential]:
        """接收原始采集数据 → 平台适配器识别 → 产出结构化凭证。

        这是所有采集渠道的唯一入口（mitmproxy / content.js / 手动输入）。
        """
        if not raw_data or not raw_data.get("value"):
            return None

        value = raw_data["value"]
        source = raw_data.get("source", "unknown")

        # Step 1: 平台适配器识别
        matched_adapter = None
        matched_result = None
        for adapter in self._platform_adapters:
            if adapter.match(raw_data):
                result = adapter.extract(raw_data)
                if result:
                    matched_adapter = adapter
                    matched_result = result
                    break

        if matched_result:
            # 适配器识别成功
            credential = self._build_credential(
                value=matched_result.get("value", value),
                cred_type=CredentialType(matched_result.get("type", "raw_data")),
                platform=matched_adapter.platform_name if matched_adapter else raw_data.get("platform", "unknown"),
                product_id=matched_result.get("product_id", ""),
                source_pipeline=source,
                raw_data=raw_data,
                metadata=matched_result.get("metadata", {}),
                account_id=matched_result.get("account_id"),
                account_name=matched_result.get("account_name", ""),
            )
            # 确保 account 信息也写入 metadata（供存储用）
            if matched_result.get("account_name"):
                credential.metadata["account_name"] = matched_result["account_name"]
            if matched_result.get("account_id"):
                credential.metadata["account_id"] = matched_result["account_id"]
        else:
            # 未识别 → 按原始类型粗略归类
            raw_type = raw_data.get("type", "")
            cred_type = self._infer_type(raw_type, value)
            credential = self._build_credential(
                value=value,
                cred_type=cred_type,
                platform=raw_data.get("platform", "unknown"),
                source_pipeline=source,
                raw_data=raw_data,
            )

        self._capture_count += 1

        # DEBUG: 打印凭证内容
        cd = credential.to_dict()
        logger.info(f"CREDENTIAL type={cd.get('type')} account={cd.get('account_name')} "
                    f"meta={json.dumps(cd.get('metadata', {}), ensure_ascii=False)[:200]}")

        # 推送到 SSE 队列
        await self._broadcast({"type": "captured", "credential": cd})

        # 触发处理器链
        if self._on_credential:
            await self._on_credential(credential)

        return credential

    # ── 内部方法 ─────────────────────────────────────

    def _build_credential(
        self,
        value: str,
        cred_type: CredentialType,
        platform: str,
        product_id: str = "",
        source_pipeline: str = "",
        raw_data: dict = None,
        metadata: dict = None,
        account_id: int = None,
        account_name: str = "",
    ) -> Credential:
        return Credential(
            type=cred_type,
            value=value,
            platform=platform,
            product_id=product_id,
            source_pipeline=source_pipeline,
            account_id=account_id,
            account_name=account_name,
            raw_data=raw_data or {},
            metadata=metadata or {},
        )

    @staticmethod
    def _infer_type(raw_type: str, value: str) -> CredentialType:
        """根据原始类型和值推断凭证类型。"""
        type_map = {
            "payment_url": CredentialType.PAYMENT_URL,
            "payment_params": CredentialType.PAYMENT_PARAMS,
            "payment_params_raw": CredentialType.PAYMENT_PARAMS,
            "qr_image": CredentialType.QR_IMAGE,
            "access_token": CredentialType.ACCESS_TOKEN,
            "card_key": CredentialType.CARD_KEY,
        }
        if raw_type in type_map:
            return type_map[raw_type]

        # 启发式推断
        v = value.strip()
        if v.startswith("http://") or v.startswith("https://"):
            return CredentialType.PAYMENT_URL
        if v.startswith("data:image"):
            return CredentialType.QR_IMAGE
        if len(v) > 20 and ("openid" in v.lower() or "token" in v.lower()):
            return CredentialType.ACCESS_TOKEN

        return CredentialType.RAW_DATA

    @staticmethod
    def _find_mitm_paths() -> list[str]:
        """查找可用的 mitmdump 路径。优先检查 venv 中的安装。"""
        import sys
        import shutil

        candidates = []

        # 1. 先检查 venv 中的 mitmdump（本项目的虚拟环境）
        venv_base = os.path.dirname(os.path.dirname(sys.executable))
        candidates.append(os.path.join(venv_base, "Scripts", "mitmdump.exe"))
        candidates.append(os.path.join(venv_base, "bin", "mitmdump"))

        # 2. 再检查系统 PATH
        which = shutil.which("mitmdump")
        if which:
            candidates.append(which)

        # 3. 常见路径兜底
        candidates.append(os.path.expanduser("~/.local/bin/mitmdump"))
        candidates.append("/usr/local/bin/mitmdump")
        candidates.append("/usr/bin/mitmdump")

        # 只返回实际存在的文件
        return [p for p in candidates if os.path.isfile(p)]

    @staticmethod
    def _find_script_path() -> Optional[str]:
        """查找 mitmproxy 内联脚本路径。"""
        candidates = [
            os.path.join(os.path.dirname(__file__), "mitm_script.py"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "mitmproxy", "pay_collector.py"),
        ]
        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    # ── SSE 广播 ────────────────────────────────────

    async def _broadcast(self, event: dict):
        """广播事件到所有 SSE 监听器。"""
        for q in self._sse_queues:
            await q.put(event)

    def add_sse_queue(self, queue: asyncio.Queue):
        self._sse_queues.append(queue)

    def remove_sse_queue(self, queue: asyncio.Queue):
        if queue in self._sse_queues:
            self._sse_queues.remove(queue)


# 全局捕获引擎单例
engine = CaptureEngine()
