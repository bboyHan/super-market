/**
 * Oracle — Hook send/recv 捕获解密后数据（方案 B）
 *
 * 原理: Hook ws2_32.dll 的 send/recv，在数据发出或收到时打印内容。
 *       不依赖特定 TLS 库，适用于任何网络通信。
 *
 * 用法: frida -p <PID> -l hook_send_recv.js
 */

'use strict';

function log(msg) {
    console.log('[Oracle] ' + msg);
}

function hexDump(buf, maxLen) {
    var arr = new Uint8Array(buf);
    var len = Math.min(arr.length, maxLen || 256);
    var hex = '', ascii = '';
    for (var i = 0; i < len; i++) {
        if (i > 0 && i % 16 === 0) {
            hex += ' ' + ascii;
            ascii = '';
        }
        var b = arr[i];
        hex += (b < 16 ? '0' : '') + b.toString(16);
        ascii += (b >= 32 && b <= 126) ? String.fromCharCode(b) : '.';
    }
    return hex + ' ' + ascii;
}

function isAscii(buf) {
    var arr = new Uint8Array(buf);
    var ascii = 0, total = Math.min(arr.length, 512);
    for (var i = 0; i < total; i++) {
        if (arr[i] >= 32 && arr[i] <= 126) ascii++;
    }
    return ascii > total * 0.8;
}

function hookSend() {
    var funcPtr = Module.findExportByName('ws2_32.dll', 'send');
    if (!funcPtr) {
        log('send not found in ws2_32.dll');
        return false;
    }

    Interceptor.attach(funcPtr, {
        onEnter: function(args) {
            var buf = args[1];
            var len = args[2].toInt32();
            if (len < 10 || len > 50000) return;

            try {
                var data = buf.readByteArray(len);
                if (isAscii(data)) {
                    var str = String.fromCharCode.apply(null, new Uint8Array(data));
                    // Only show HTTP-like data
                    if (str.startsWith('GET ') || str.startsWith('POST ') ||
                        str.startsWith('HTTP/') || str.includes('HTTP/1.1') ||
                        str.startsWith('{') || str.startsWith('[')) {
                        log('[SEND] ' + str.substring(0, 500));
                    }
                }
            } catch (e) {}
        }
    });
    log('send hooked');
    return true;
}

function hookRecv() {
    var funcPtr = Module.findExportByName('ws2_32.dll', 'recv');
    if (!funcPtr) {
        log('recv not found in ws2_32.dll');
        return false;
    }

    Interceptor.attach(funcPtr, {
        onLeave: function(retval) {
            var len = retval.toInt32();
            if (len <= 0) return;

            try {
                var buf = this.context.rcx || this.context.r1 || this.context.arg1;
                // Simplified - not all architectures read the same
                var data = this._buf;
                if (!data) return;

                var bytes = data.readByteArray(Math.min(len, 2000));
                if (isAscii(bytes)) {
                    var str = String.fromCharCode.apply(null, new Uint8Array(bytes));
                    if (str.startsWith('{') || str.startsWith('[') ||
                        str.includes('weixin') || str.includes('openid') ||
                        str.includes('pay') || str.includes('result_url')) {
                        log('[RECV] ' + str.substring(0, 1000));
                    }
                }
            } catch (e) {}
        },
        onEnter: function(args) {
            this._buf = args[1];
        }
    });
    log('recv hooked');
    return true;
}

function main() {
    log('Hook send/recv loaded');

    if (!hookSend()) {
        log('send hook failed - ws2_32.dll may not be loaded yet');
    }
    if (!hookRecv()) {
        log('recv hook failed');
    }

    log('Ready - watching network traffic...');
    log('Look for JSON responses containing payment data');
}

main();
