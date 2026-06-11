/*=============================================================
 * Oracle WFP Callout — QUIC Block Driver
 *
 * 功能: 在 WFP ALE 连接层阻止 QUIC (UDP 443) 连接，
 *       强制应用回退到 TCP，以便被 TLS 代理捕获。
 *
 * 编译: 需要 WDK (Windows Driver Kit)
 *   cl.exe /W4 /WX /kernel quic_block.c /Fequic_block.sys
 *     /link /subsystem:native /driver /entry:DriverEntry
 *
 * 安装:
 *   sc create OracleQuicBlock type=kernel binPath=<path>\quic_block.sys
 *   sc start OracleQuicBlock
 *
 * 卸载:
 *   sc stop OracleQuicBlock
 *   sc delete OracleQuicBlock
 *=============================================================*/

#include <ntddk.h>
#include <fwpsk.h>
#include <fwpmk.h>
#include <initguid.h>

#pragma comment(lib, "fwpkclnt.lib")

/* ── 驱动标识 ─────────────────────────────── */

#define POOL_TAG 'QBOR'
#define DRIVER_NAME "OracleQuicBlock"

PDEVICE_OBJECT g_deviceObject = NULL;
HANDLE g_engineHandle = NULL;
HANDLE g_calloutRegistration = NULL;
UINT32 g_calloutId = 0;

/* ── Callout GUID (每次生成唯一) ──────────── */

// {B1A7F0A0-1A2B-3C4D-5E6F-7890ABCDEF01}
DEFINE_GUID(
    OracleQuicCalloutGuid,
    0xB1A7F0A0, 0x1A2B, 0x3C4D, 0x5E, 0x6F,
    0x78, 0x90, 0xAB, 0xCD, 0xEF, 0x01
);

// Sublayer GUID
DEFINE_GUID(
    OracleQuicSublayerGuid,
    0xB1A7F0A0, 0x1A2B, 0x3C4D, 0x5E, 0x6F,
    0x78, 0x90, 0xAB, 0xCD, 0xEF, 0x02
);

/* ── Callout 分类函数 ─────────────────────────
 *
 * 在 ALE_AUTH_CONNECT 层被调用。
 * 检测: UDP + 目标端口 443 → 阻止
 *       其他 → 允许
 */
void NTAPI QuicBlockClassify(
    const FWPS_INCOMING_VALUES* inFixedValues,
    const FWPS_INCOMING_METADATA_VALUES* inMetaValues,
    void* layerData,
    const void* classifyContext,
    const FWPS_FILTER* filter,
    UINT64 flowContext,
    FWPS_CLASSIFY_OUT* classifyOut)
{
    UINT32 localPort, remotePort;
    UINT16 protocol;

    /* 默认允许 */
    classifyOut->actionType = FWP_ACTION_PERMIT;
    classifyOut->rights &= ~FWPS_RIGHT_ACTION_WRITE;

    /* 获取协议类型 */
    protocol = FWPS_GET_FIELD(inFixedValues,
        FWPS_FIELD_ALE_AUTH_CONNECT_V4_IP_PROTOCOL);

    /* 只阻止 UDP */
    if (protocol != IPPROTO_UDP)
        return;

    /* 获取目标端口 */
    remotePort = FWPS_GET_FIELD(inFixedValues,
        FWPS_FIELD_ALE_AUTH_CONNECT_V4_IP_REMOTE_PORT);
    remotePort = RtlUshortByteSwap((USHORT)remotePort);

    /* 阻止 UDP 443 (QUIC) */
    if (remotePort == 443)
    {
        classifyOut->actionType = FWP_ACTION_BLOCK;
        DbgPrint("[Oracle] QUIC blocked: port 443\n");
    }
}

void NTAPI QuicBlockNotify(
    FWPS_CALLOUT_NOTIFY_TYPE notifyType,
    const GUID* filterKey,
    FWPS_FILTER* filter)
{
    UNREFERENCED_PARAMETER(filterKey);
    UNREFERENCED_PARAMETER(filter);

    switch (notifyType)
    {
    case FWPS_CALLOUT_NOTIFY_ADD_FILTER:
        DbgPrint("[Oracle] QUIC block filter added\n");
        break;
    case FWPS_CALLOUT_NOTIFY_DELETE_FILTER:
        DbgPrint("[Oracle] QUIC block filter removed\n");
        break;
    }
}

NTSTATUS NTAPI QuicBlockFlowAdd(
    FWPS_INCOMING_VALUES* inFixedValues,
    FWPS_INCOMING_METADATA_VALUES* inMetaValues,
    void* layerData)
{
    return STATUS_SUCCESS;
}

/* ── 注册 Callout ─────────────────────────── */

NTSTATUS RegisterCallout()
{
    NTSTATUS status;
    FWPS_CALLOUT callout = { 0 };

    callout.calloutKey = OracleQuicCalloutGuid;
    callout.flags = 0;
    callout.classifyFn = QuicBlockClassify;
    callout.notifyFn = QuicBlockNotify;
    callout.flowDeleteFn = QuicBlockFlowAdd;

    status = FwpsCalloutRegister(g_deviceObject, &callout, &g_calloutRegistration);
    if (!NT_SUCCESS(status))
    {
        DbgPrint("[Oracle] FwpsCalloutRegister failed: %x\n", status);
        return status;
    }

    /* 注册到 ALE_AUTH_CONNECT 层 */
    {
        FWPM_CALLOUT mCallout = { 0 };
        FWPM_FILTER mFilter = { 0 };
        FWPM_FILTER_CONDITION filterCond = { 0 };

        mCallout.calloutKey = OracleQuicCalloutGuid;
        mCallout.displayData.name = L"Oracle QUIC Block Callout";
        mCallout.displayData.description = L"Blocks QUIC (UDP/443) to force TCP fallback";
        mCallout.flags = 0;
        mCallout.providerKey = NULL;
        mCallout.applicableLayer = FWPM_LAYER_ALE_AUTH_CONNECT_V4;

        status = FwpmCalloutAdd(g_engineHandle, &mCallout, NULL, NULL);
        if (!NT_SUCCESS(status) && status != STATUS_FWP_ALREADY_EXISTS)
        {
            DbgPrint("[Oracle] FwpmCalloutAdd failed: %x\n", status);
            FwpsCalloutUnregisterById(g_calloutId);
            return status;
        }

        /* 添加过滤器 — 所有 UDP 443 连接 */
        mFilter.layerKey = FWPM_LAYER_ALE_AUTH_CONNECT_V4;
        mFilter.displayData.name = L"Oracle QUIC Block Filter";
        mFilter.displayData.description = L"Block all UDP/443 to force TCP fallback";
        mFilter.action.type = FWP_ACTION_CALLOUT_TERMINATING;
        mFilter.action.calloutKey = OracleQuicCalloutGuid;
        mFilter.subLayerKey = OracleQuicSublayerGuid;
        mFilter.weight.type = FWP_EMPTY;
        mFilter.numFilterConditions = 0; /* blocks all UDP/443 */
        mFilter.filterCondition = NULL;

        status = FwpmFilterAdd(g_engineHandle, &mFilter, NULL, NULL);
        if (!NT_SUCCESS(status))
        {
            DbgPrint("[Oracle] FwpmFilterAdd failed: %x\n", status);
        }
    }

    return status;
}

/* ── 驱动入口 ─────────────────────────────── */

NTSTATUS DriverEntry(PDRIVER_OBJECT driverObject, PUNICODE_STRING registryPath)
{
    NTSTATUS status;
    UNICODE_STRING deviceName;
    UNICODE_STRING symbolicLink;

    UNREFERENCED_PARAMETER(registryPath);

    DbgPrint("[Oracle] QUIC Block Driver loading...\n");

    /* 创建设备对象 */
    RtlInitUnicodeString(&deviceName, L"\\Device\\OracleQuicBlock");
    status = IoCreateDevice(driverObject, 0, &deviceName,
        FILE_DEVICE_UNKNOWN, 0, FALSE, &g_deviceObject);
    if (!NT_SUCCESS(status))
    {
        DbgPrint("[Oracle] IoCreateDevice failed: %x\n", status);
        return status;
    }

    /* 创建符号链接 */
    RtlInitUnicodeString(&symbolicLink, L"\\DosDevices\\OracleQuicBlock");
    status = IoCreateSymbolicLink(&symbolicLink, &deviceName);
    if (!NT_SUCCESS(status))
    {
        DbgPrint("[Oracle] IoCreateSymbolicLink failed: %x\n", status);
        IoDeleteDevice(g_deviceObject);
        return status;
    }

    /* 打开 WFP 引擎 */
    status = FwpmEngineOpen(NULL, RPC_C_AUTHN_WINNT, NULL, NULL, &g_engineHandle);
    if (!NT_SUCCESS(status))
    {
        DbgPrint("[Oracle] FwpmEngineOpen failed: %x\n", status);
        IoDeleteSymbolicLink(&symbolicLink);
        IoDeleteDevice(g_deviceObject);
        return status;
    }

    /* 添加子层 */
    {
        FWPM_SUBLAYER subLayer = { 0 };
        subLayer.subLayerKey = OracleQuicSublayerGuid;
        subLayer.displayData.name = L"Oracle QUIC Block Sublayer";
        subLayer.displayData.description = L"Sublayer for QUIC blocking";
        subLayer.weight = 0x100;

        FwpmSubLayerAdd(g_engineHandle, &subLayer, NULL);
    }

    /* 注册 Callout */
    status = RegisterCallout();
    if (!NT_SUCCESS(status))
    {
        DbgPrint("[Oracle] RegisterCallout failed: %x\n", status);
        FwpmEngineClose(g_engineHandle);
        IoDeleteSymbolicLink(&symbolicLink);
        IoDeleteDevice(g_deviceObject);
        return status;
    }

    driverObject->DriverUnload = DriverUnload;

    DbgPrint("[Oracle] QUIC Block Driver loaded successfully\n");
    return STATUS_SUCCESS;
}

/* ── 驱动卸载 ─────────────────────────────── */

VOID DriverUnload(PDRIVER_OBJECT driverObject)
{
    UNICODE_STRING symbolicLink;

    DbgPrint("[Oracle] QUIC Block Driver unloading...\n");

    /* 删除过滤器 */
    FwpmFilterDeleteByKey(g_engineHandle, &OracleQuicCalloutGuid);

    /* 取消注册 Callout */
    if (g_calloutRegistration)
        FwpsCalloutUnregisterByPointer(g_calloutRegistration);

    /* 关闭引擎 */
    if (g_engineHandle)
        FwpmEngineClose(g_engineHandle);

    /* 清理设备 */
    RtlInitUnicodeString(&symbolicLink, L"\\DosDevices\\OracleQuicBlock");
    IoDeleteSymbolicLink(&symbolicLink);

    if (driverObject->DeviceObject)
        IoDeleteDevice(driverObject->DeviceObject);

    DbgPrint("[Oracle] QUIC Block Driver unloaded\n");
}
