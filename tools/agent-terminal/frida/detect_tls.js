/**
 * Oracle — 检测微信用什么 TLS 库验证证书
 * 用法: frida -p <PID> -l detect_tls.js
 */

'use strict';

function log(msg) { console.log('[DETECT] ' + msg); }

function checkModule(name) {
    var mod = Process.findModuleByName(name);
    if (mod) {
        log('Found: ' + name + ' @ ' + mod.base + ' size=' + mod.size);
    }
}

function checkExport(module, func) {
    try {
        var ptr = Module.findExportByName(module, func);
        if (ptr) {
            log('  ' + module + '!' + func + ' @ ' + ptr);
        }
    } catch (e) {}
}

function main() {
    log('=== TLS Libraries Check ===');
    checkModule('schannel.dll');
    checkModule('bcrypt.dll');
    checkModule('ncrypt.dll');
    checkModule('sspicli.dll');
    checkModule('libcrypto-3.dll');
    checkModule('libssl-3.dll');

    log('');
    log('=== Certificate Verification Exports ===');
    var exports = [
        'CertVerifyCertificateChainPolicy',
        'CertGetCertificateChain',
        'CertVerifySubjectCertificateContext',
        'CertVerifyTimeValidity',
        'CertVerifyCRLTimeValidity',
        'CertCheckAuthenticodeSignature',
        'SSL_CTX_set_verify',
        'X509_verify_cert',
        'SSL_get_verify_result',
    ];

    var modules = ['schannel.dll', 'bcrypt.dll', 'ncrypt.dll', 'sspicli.dll'];
    modules.forEach(function(mod) {
        if (Process.findModuleByName(mod)) {
            exports.forEach(function(func) {
                checkExport(mod, func);
            });
        }
    });

    log('');
    log('=== Other crypto modules ===');
    Process.enumerateModules({
        onMatch: function(mod) {
            var name = mod.name.toLowerCase();
            if (name.includes('ssl') || name.includes('crypto') ||
                name.includes('cert') || name.includes('tls') ||
                name.includes('schannel') || name.includes('libressl') ||
                name.includes('openssl') || name.includes('boring')) {
                log('  Loaded: ' + mod.name + ' (' + mod.path + ')');
            }
        },
        onComplete: function() {}
    });

    log('[DONE] Check complete');
}

main();
