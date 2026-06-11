/**
 * Oracle — 绕过微信证书固定 (Certificate Pinning)
 *
 * 原理: Hook schannel.dll 的 CertVerifyCertificateChainPolicy
 *       让微信接受 Oracle 伪造的中间人证书
 *
 * 用法:
 *   1. 安装 Frida: pip install frida-tools
 *   2. 微信先登录好
 *   3. 启动 Oracle 引擎
 *   4. 执行: frida -n WeChat.exe -l bypass_pinning.js
 *   5. 在微信里操作支付
 *
 * 注意: Frida 需要管理员权限 + Windows 处于测试签名模式
 *       或 Frida 驱动已安装
 */

'use strict';

// ── 配置 ──────────────────────────────────────
const TARGET_MODULE = 'schannel.dll';
const TARGET_FUNCTION = 'CertVerifyCertificateChainPolicy';

// ── 日志 ──────────────────────────────────────
function log(msg) {
    console.log(`[Oracle] ${msg}`);
}

function logHex(buf) {
    const arr = new Uint8Array(buf);
    const hex = Array.from(arr).map(b => b.toString(16).padStart(2, '0')).join('');
    return hex.substring(0, 64) + (hex.length > 64 ? '...' : '');
}

// ── Hook: CertVerifyCertificateChainPolicy ─────
//
// BOOL CertVerifyCertificateChainPolicy(
//   LPCSTR                   pszPolicyOID,   // 策略 OID
//   PCCERT_CHAIN_CONTEXT     pChainContext,  // 证书链
//   PCERT_CHAIN_POLICY_PARA  pPolicyPara,    // 策略参数
//   PCERT_CHAIN_POLICY_STATUS pPolicyStatus   // [out] 状态
// );

function hookCertVerify() {
    const module = Process.findModuleByName(TARGET_MODULE);
    if (!module) {
        log(`[!] Module ${TARGET_MODULE} not found`);
        return false;
    }

    const funcPtr = Module.findExportByName(TARGET_MODULE, TARGET_FUNCTION);
    if (!funcPtr) {
        log(`[!] Export ${TARGET_FUNCTION} not found in ${TARGET_MODULE}`);
        return false;
    }

    log(`Hooking ${TARGET_MODULE}!${TARGET_FUNCTION} @ ${funcPtr}`);

    Interceptor.attach(funcPtr, {
        onEnter: function(args) {
            // args[0] = policy OID
            const oid = args[0].readCString();
            // args[1] = chain context
            // args[3] = policy status (output)

            // Log certificate validation attempts for payment domains
            if (oid && (oid.includes('AUTH') || oid.includes('HTTPS'))) {
                log(`CertVerify: ${oid}`);
                this.shouldOverride = true;
            } else {
                this.shouldOverride = false;
            }
        },
        onLeave: function(retval) {
            // Override: always return TRUE (success)
            // This bypasses certificate pinning checks
            if (this.shouldOverride) {
                retval.replace(1); // TRUE
                log('  → Bypassed certificate validation');
            }
        }
    });

    return true;
}

// ── Hook: CertGetCertificateChain ─────────────
// Hook this to log which certificates are being validated

function hookCertGetChain() {
    const funcPtr = Module.findExportByName(TARGET_MODULE, 'CertGetCertificateChain');
    if (!funcPtr) {
        log('[!] CertGetCertificateChain not found');
        return false;
    }

    log(`Hooking ${TARGET_MODULE}!CertGetCertificateChain`);

    Interceptor.attach(funcPtr, {
        onEnter: function(args) {
            // args[1] = certificate context
            const certCtx = ptr(args[1]);
            if (certCtx.isNull()) return;

            try {
                // Read subject name from CERT_CONTEXT
                const certInfo = certCtx.add(Process.pointerSize).readPointer();
                if (!certInfo.isNull()) {
                    // Try to read subject
                    const subjectBlob = certInfo.add(12); // offset of Subject in CERT_INFO
                    const dataPtr = subjectBlob.readPointer();
                    const dataLen = subjectBlob.add(Process.pointerSize).readU32();
                    if (dataLen > 0 && dataLen < 256) {
                        const name = dataPtr.readCString(dataLen);
                        if (name.includes('qq') || name.includes('tencent') || name.includes('weixin') || name.includes('tenpay')) {
                            log(`Cert chain for: ${name}`);
                        }
                    }
                }
            } catch (e) {
                // Ignore parse errors
            }
        }
    });

    return true;
}

// ── 主函数 ────────────────────────────────────

function main() {
    log('Frida script loaded - Attaching to WeChat...');

    // Check if schannel.dll is loaded
    if (Process.findModuleByName(TARGET_MODULE)) {
        log(`${TARGET_MODULE} already loaded, installing hooks...`);
        hookCertVerify();
        hookCertGetChain();
    } else {
        log(`${TARGET_MODULE} not yet loaded - hooks will activate when loaded`);
    }

    // Try hooks immediately (they'll work if module is loaded)
    var hooked = hookCertVerify();
    hookCertGetChain();

    if (!hooked) {
        log('[!] CertVerify not available yet - retrying in 3 seconds...');
        // Frida-compatible delay using NativeFunction
        var sleep = new NativeFunction(
            Module.findExportByName('kernel32.dll', 'Sleep'),
            'void', ['uint32']
        );
        sleep(3000);
        if (!hookCertVerify()) {
            log('[!] Still not available, schannel.dll may not be used by this process');
        } else {
            hookCertGetChain();
        }
    }
}

main();
