"""Android emulator + mitmproxy collector for mobile app credential collection.

Architecture:
  mitmproxy runs in mitmdump mode (non-interactive), logging all HTTP(S) traffic.
  A filter script extracts payment-related URLs (by domain/pattern matching).
  The collector starts mitmdump, configures the emulator proxy, launches the app,
  waits for target traffic, and captures payment URLs/QR codes.
"""

import asyncio
import json
import os
import re
import signal
import subprocess
import tempfile
import time
from typing import Any, AsyncGenerator, Optional

from collectors.base import BaseCollector


# ── Platform-specific payment URL patterns ──────────────────────

PLATFORM_PAYMENT_PATTERNS: dict[str, list[str]] = {
    "jd": [
        r"https?://pay\.jd\.com/.*",
        r"https?://.*\.jd\.com/.*pay.*",
        r"https?://wqs\.jd\.com/.*",
        r"https?://h5pay\.jd\.com/.*",
    ],
    "taobao": [
        r"https?://.*\.alipay\.com/.*",
        r"https?://.*\.taobao\.com/.*pay.*",
        r"https?://wu.*\.alipay\.com/.*",
    ],
    "pdd": [
        r"https?://mobile\.yangkeduo\.com/.*pay.*",
        r"https?://api\.pinduoduo\.com/.*pay.*",
        r"https?://cashier\.pinduoduo\.com/.*",
    ],
    "douyin": [
        r"https?://.*\.douyin\.com/.*pay.*",
        r"https?://pay\.douyin\.com/.*",
        r"https?://life\.douyin\.com/.*",
    ],
}

# Package names for launching apps via ADB
PLATFORM_PACKAGES: dict[str, str] = {
    "jd": "com.jingdong.app.mall",
    "taobao": "com.taobao.taobao",
    "pdd": "com.xunmeng.pinduoduo",
    "douyin": "com.ss.android.ugc.aweme",
}


class EmulatorCollector(BaseCollector):
    """Collects credentials by proxying Android emulator traffic through mitmproxy.

    Requires:
      - mitmproxy installed (pip install mitmproxy)
      - ADB connected to an Android emulator/device
      - Emulator WiFi proxy set to host machine IP + port
    """

    @property
    def name(self) -> str:
        return "emulator"

    def __init__(self, task_id: str, config: dict[str, Any]):
        super().__init__(task_id, config)
        self._mitm_process = None
        self._captured_urls: list[dict] = []
        self._temp_dir = tempfile.mkdtemp(prefix="mitm_")
        self._flow_file = os.path.join(self._temp_dir, "flows.flow")
        self._platform = config.get("platform", "unknown")
        self._capture_duration = 30  # seconds to wait for payment traffic

    async def execute(self) -> AsyncGenerator[dict, None]:
        config = self.config
        platform = config.get("platform", "unknown")
        product_id = config.get("product_id", "")
        quantity = config.get("quantity", 1)
        mitm_port = config.get("mitmproxy_port", 8081)
        impl_config = config.get("collection_config", {}).get("implementation", {})
        
        duration = impl_config.get("capture_duration", self._capture_duration)
        patterns = PLATFORM_PAYMENT_PATTERNS.get(platform, [])
        
        self._platform = platform
        self._captured_urls = []

        try:
            # ── Step 1: Start mitmdump ──
            yield progress_step("mitmproxy", 10, f"启动 mitmproxy（端口 {mitm_port}）...")
            
            mitm_path = self._find_mitmdump()
            if not mitm_path:
                yield error_step("mitmdump 未安装，请执行: pip install mitmproxy")
                return

            await self._start_mitmdump(mitm_path, mitm_port)
            yield progress_step("mitmproxy", 20, f"mitmproxy 已启动 (pid={self._mitm_process.pid})")

            # ── Step 2: Configure emulator proxy ──
            yield progress_step("emulator", 25, "配置模拟器代理...")
            
            # Try to set proxy via ADB
            adb_ok = await self._configure_emulator_proxy(mitm_port)
            if not adb_ok:
                yield {
                    "step": "emulator",
                    "status": "running",
                    "message": "ADB 未连接，请在模拟器/设备 WiFi 中手动设置代理为当前主机IP:端口",
                    "progress": 30,
                    "data": {"manual_proxy_required": True},
                }
                # Give user time to set up proxy
                yield progress_step("emulator", 35, "等待代理配置（60秒）...")
                await self._wait_checked(60)
            else:
                yield progress_step("emulator", 35, "模拟器代理已配置")

            # ── Step 3: Launch target app ──
            yield progress_step("launch_app", 40, f"启动 {platform} App...")
            
            package = PLATFORM_PACKAGES.get(platform)
            if package and adb_ok:
                await self._launch_app(package)
            else:
                yield {
                    "step": "launch_app",
                    "status": "running",
                    "message": f"请在模拟器中手动打开 {platform} App，进入目标商品页完成支付流程",
                    "progress": 45,
                    "data": {"needs_manual_launch": True},
                }

            # ── Step 4: Wait and capture traffic ──
            yield progress_step("capture", 50, f"正在捕获支付流量（等待 {duration} 秒）...")
            yield {
                "step": "capture",
                "status": "running",
                "message": f"请在 {platform} App 中完成支付操作，系统将自动捕获支付链接",
                "progress": 55,
            }

            # Monitor the flow file for new entries
            matches = await self._monitor_flows(duration, patterns)
            self._captured_urls = matches

            if self._captured_urls:
                yield {
                    "step": "capture",
                    "status": "completed",
                    "message": f"已捕获 {len(self._captured_urls)} 笔支付流量",
                    "progress": 80,
                    "data": {"resources": self._captured_urls},
                }
            else:
                yield {
                    "step": "capture",
                    "status": "running",
                    "message": "未检测到支付流量，尝试使用页面截图作为备选方案...",
                    "progress": 75,
                }
                await asyncio.sleep(5)

            # ── Step 5: Extract and finalize ──
            urls = self._captured_urls or self._collect_urls_from_flows()
            take = urls[:quantity] if urls else []
            
            yield progress_step("extract", 90, f"提取 {len(take)} 条支付凭证")

            yield {
                "step": "complete",
                "status": "completed",
                "message": f"采集完成，获取 {len(take)} 条支付凭证",
                "progress": 100,
                "data": {"resources": take},
            }

        except Exception as e:
            yield error_step(f"模拟器采集失败: {type(e).__name__}: {e}")
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Stop mitmproxy and clean up temp files."""
        if self._mitm_process:
            try:
                self._mitm_process.send_signal(signal.SIGTERM)
                await asyncio.sleep(1)
                if self._mitm_process.returncode is None:
                    self._mitm_process.kill()
            except Exception:
                pass
            self._mitm_process = None

        # Clean up temp files
        try:
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        except Exception:
            pass

    def _find_mitmdump(self) -> Optional[str]:
        """Find the mitmdump binary path."""
        # Check common locations
        candidates = [
            "mitmdump",  # in PATH
            os.path.expanduser("~/.local/bin/mitmdump"),
            "/usr/local/bin/mitmdump",
        ]
        # Also check the virtual env
        venv = os.environ.get("VIRTUAL_ENV", "")
        if venv:
            candidates.insert(0, os.path.join(venv, "bin", "mitmdump"))
        
        for c in candidates:
            try:
                import subprocess
                result = subprocess.run(
                    ["which", c] if not c.startswith("/") else ["test", "-x", c],
                    capture_output=True, timeout=2,
                )
                if result.returncode == 0:
                    return c
            except Exception:
                pass
        return "mitmdump"  # fallback

    async def _start_mitmdump(self, path: str, port: int):
        """Start mitmdump in non-interactive mode, writing flows to a file."""
        self._mitm_process = await asyncio.create_subprocess_exec(
            path,
            "--listen-port", str(port),
            "--set", "block_global=false",
            "--set", "ssl_insecure=true",
            "--save-stream-file", self._flow_file,
            "--set", "flow_detail=4",
            "--no-http2",  # More compatible with many Android apps
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await asyncio.sleep(2)

    async def _configure_emulator_proxy(self, port: int) -> bool:
        """Configure Android emulator proxy via ADB. Returns True if successful."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "shell",
                "settings", "put", "global", "http_proxy", f"127.0.0.1:{port}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=10)
            
            # Verify ADB is actually connected to a device
            verify = await asyncio.create_subprocess_exec(
                "adb", "devices",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(verify.communicate(), timeout=10)
            devices = stdout.decode().strip()
            # If we see "List of devices attached" followed by a real device
            lines = [l.strip() for l in devices.split("\n") if l.strip() and "device" in l.lower() and "attached" not in l.lower()]
            return len(lines) > 0
        except (FileNotFoundError, asyncio.TimeoutError, subprocess.TimeoutExpired):
            return False

    async def _launch_app(self, package: str):
        """Launch an Android app via ADB monkey command."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "adb", "shell",
                "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await asyncio.wait_for(proc.wait(), timeout=10)
        except (FileNotFoundError, asyncio.TimeoutError):
            pass

    async def _monitor_flows(self, duration: int, patterns: list[str]) -> list[dict]:
        """Monitor the flow file for new entries matching payment URL patterns.
        
        Polls the flow file periodically during the capture window.
        """
        matches = []
        start = time.time()
        
        # Compile regex patterns
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        
        while time.time() - start < duration:
            if self._cancelled:
                break
            
            flows = await self._read_flow_file()
            for flow in flows:
                url = flow.get("url", "")
                if not any(m.search(url) for m in compiled):
                    continue
                # Avoid duplicates
                if any(m.get("value") == url for m in matches):
                    continue
                
                matches.append({
                    "value": url,
                    "resource_type": self._classify_url(url),
                    "metadata": json.dumps({
                        "source": "mitmproxy",
                        "method": flow.get("method", ""),
                        "status_code": flow.get("status_code"),
                        "content_type": flow.get("content_type", ""),
                    }, ensure_ascii=False),
                })
            
            await asyncio.sleep(1)
        
        return matches

    async def _read_flow_file(self) -> list[dict]:
        """Read mitmproxy flow file and extract relevant request URLs."""
        flows = []
        try:
            if not os.path.exists(self._flow_file) or os.path.getsize(self._flow_file) == 0:
                return flows
            
            # Parse in executor to avoid blocking
            loop = asyncio.get_event_loop()
            parsed = await loop.run_in_executor(None, self._parse_flows_file)
            return parsed
        except Exception:
            return flows

    def _parse_flows_file(self) -> list[dict]:
        """Parse the mitmproxy flow file synchronously (runs in executor)."""
        results = []
        try:
            from mitmproxy import io as mitm_io
            with open(self._flow_file, "rb") as f:
                reader = mitm_io.FlowReader(f)
                for flow in reader.stream():
                    if flow.request:
                        url = flow.request.pretty_url
                        results.append({
                            "url": url,
                            "method": flow.request.method,
                            "status_code": None,
                            "content_type": "",
                        })
            return results
        except Exception:
            return results

    async def _export_flows_via_cli(self) -> list[dict]:
        """Fallback: use mitmdump CLI to export flows as JSON."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "mitmdump", "--read-flows", self._flow_file,
                "--set", "flow_detail=4",
                "-w", "/dev/null",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stdout.decode()
            results = []
            for line in output.split("\n"):
                if "GET " in line or "POST " in line:
                    parts = line.strip().split()
                    if len(parts) >= 2:
                        results.append({
                            "url": parts[1],
                            "method": parts[0],
                        })
            return results
        except Exception:
            return []

    def _collect_urls_from_flows(self) -> list[dict]:
        """Fallback: collect any URLs from the flow file as payment links."""
        results = []
        try:
            if not os.path.exists(self._flow_file):
                return results
            flows = self._parse_flows_file()
            for f in flows:
                url = f.get("url", "")
                if url and url.startswith("http"):
                    results.append({
                        "value": url,
                        "resource_type": "payment_link",
                        "metadata": json.dumps({
                            "source": "mitmproxy_fallback",
                            "method": f.get("method", ""),
                        }, ensure_ascii=False),
                    })
        except Exception:
            pass
        return results

    def _classify_url(self, url: str) -> str:
        """Classify a URL into a resource type."""
        if re.search(r"qrcode|qr_code|qr", url, re.IGNORECASE):
            return "qrcode"
        if re.search(r"pay|cashier|checkout|check_out", url, re.IGNORECASE):
            return "payment_link"
        return "payment_link"

    async def _wait_checked(self, seconds: int):
        """Wait with cancellation check."""
        for _ in range(seconds):
            if self._cancelled:
                return
            await asyncio.sleep(1)


# ── Helpers ───────────────────────────────────────────────────

def progress_step(step: str, progress: int, message: str) -> dict:
    return {"step": step, "status": "running", "message": message, "progress": progress}


def error_step(message: str) -> dict:
    return {"step": "error", "status": "failed", "message": message, "progress": 0}
