/**
 * Oracle — Hook send/recv v2 (Frida 17.x compat)
 */
'use strict';

function log(m) { console.log('[Oracle] ' + m); }

function findExport(modName, name) {
    try {
        var mod = Process.getModuleByName(modName);
        var exports = mod.enumerateExports();
        for (var i = 0; i < exports.length; i++) {
            if (exports[i].name === name || exports[i].name.indexOf(name) >= 0) {
                log('Found ' + modName + '!' + exports[i].name + ' @ ' + exports[i].address);
                return exports[i].address;
            }
        }
    } catch(e) { log('Enum err: ' + e); }
    return null;
}

function isAscii(buf) {
    var arr = new Uint8Array(buf);
    var ascii = 0, n = Math.min(arr.length, 512);
    for (var i = 0; i < n; i++) { if (arr[i] >= 32 && arr[i] <= 126) ascii++; }
    return ascii > n * 0.8;
}

function hookSend() {
    var p = findExport('ws2_32.dll', 'send');
    if (!p) { log('send not found'); return; }
    Interceptor.attach(p, {
        onEnter: function(args) {
            var len = args[2].toInt32();
            if (len < 20 || len > 100000) return;
            try {
                var d = args[1].readByteArray(len);
                if (!isAscii(d)) return;
                var s = String.fromCharCode.apply(null, new Uint8Array(d));
                if (s.includes('{') || s.includes('weixin') || s.includes('openid') ||
                    s.includes('.qq.com') || s.includes('tenpay') || s.includes('pay')) {
                    log('>>> SEND ' + len + 'b\n' + s.substring(0, 1500));
                }
            } catch(e) {}
        }
    });
}

function hookRecv() {
    var p = findExport('ws2_32.dll', 'recv');
    if (!p) { log('recv not found'); return; }
    Interceptor.attach(p, {
        onEnter: function(a) { this.buf = a[1]; },
        onLeave: function(r) {
            var len = r.toInt32();
            if (len <= 0 || !this.buf) return;
            try {
                var d = this.buf.readByteArray(Math.min(len, 2000));
                if (!isAscii(d)) return;
                var s = String.fromCharCode.apply(null, new Uint8Array(d));
                if (s.includes('{') || s.includes('weixin') || s.includes('openid') ||
                    s.includes('.qq.com') || s.includes('tenpay') || s.includes('pay')) {
                    log('<<< RECV ' + len + 'b\n' + s.substring(0, 1500));
                }
            } catch(e) {}
        }
    });
}

function main() {
    log('=== Network Hook ===');
    hookSend();
    hookRecv();
    log('Ready!');
}

main();
