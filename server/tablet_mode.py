import subprocess
import os
import ctypes
import winreg

PS_SET_TABLET = r"""
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;

public static class TabletModeHelper
{
    [ComImport, Guid("6D5140C1-7436-11CE-8034-00AA006009FA"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IServiceProvider
    {
        void QueryService(ref Guid guidService, ref Guid riid, out IntPtr ppvObject);
    }

    [ComImport, Guid("4FDA780A-ACD2-41F7-B4F2-EBE674C9BF2A"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface ITabletModeController
    {
        int GetMode(out int mode);
        int SetMode(int mode, int modeTrigger);
    }

    public static void SetMode(int mode)
    {
        var CLSID_ImmersiveShell = new Guid("C2F03A33-21F5-47FA-B4BB-156362A2F239");
        var IID_ITabletMode = new Guid("4FDA780A-ACD2-41F7-B4F2-EBE674C9BF2A");
        Type shellType = Type.GetTypeFromCLSID(CLSID_ImmersiveShell);
        object shell = Activator.CreateInstance(shellType);
        IntPtr pSP = Marshal.GetIUnknownForObject(shell);
        IServiceProvider provider = (IServiceProvider)Marshal.GetObjectForIUnknown(pSP);
        IntPtr pCtrl;
        provider.QueryService(ref IID_ITabletMode, ref IID_ITabletMode, out pCtrl);
        ITabletModeController ctrl = (ITabletModeController)Marshal.GetObjectForIUnknown(pCtrl);
        ctrl.SetMode(mode, 4);
        Marshal.Release(pCtrl);
        Marshal.Release(pSP);
    }
}
"@

[TabletModeHelper]::SetMode($Args[0])
"""


def is_windows_11():
    try:
        ver = ctypes.windll.ntdll.RtlGetVersion
        class OSVERSIONINFOEXW(ctypes.Structure):
            _fields_ = [("dwOSVersionInfoSize", ctypes.c_ulong),
                        ("dwMajorVersion", ctypes.c_ulong),
                        ("dwMinorVersion", ctypes.c_ulong),
                        ("dwBuildNumber", ctypes.c_ulong),
                        ("dwPlatformId", ctypes.c_ulong),
                        ("szCSDVersion", ctypes.c_wchar * 128)]
        osv = OSVERSIONINFOEXW()
        osv.dwOSVersionInfoSize = ctypes.sizeof(osv)
        ver(osv)
        return osv.dwBuildNumber >= 22000
    except Exception:
        return False


def _set_via_com(mode):
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", PS_SET_TABLET, str(mode)],
            capture_output=True, timeout=15
        )
        return True
    except Exception:
        return False


def _set_via_registry(mode):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\ImmersiveShell",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "TabletMode", 0, winreg.REG_DWORD, mode)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def _set_convertible_slate(mode):
    try:
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\PriorityControl",
            0, winreg.KEY_SET_VALUE
        )
        winreg.SetValueEx(key, "ConvertibleSlateMode", 0, winreg.REG_DWORD,
                          0 if mode else 1)
        winreg.CloseKey(key)
        return True
    except Exception:
        return False


def set_tablet_mode(enabled):
    mode = 1 if enabled else 0
    if _set_via_com(mode):
        return True
    _set_via_registry(mode)
    if is_windows_11():
        _set_convertible_slate(mode)
    return False


def is_tablet_mode():
    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\ImmersiveShell",
            0, winreg.KEY_READ
        )
        val, _ = winreg.QueryValueEx(key, "TabletMode")
        winreg.CloseKey(key)
        return val == 1
    except Exception:
        return False


if __name__ == "__main__":
    import sys
    mode = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    print(f"Setting tablet mode to: {'ON' if mode else 'OFF'}")
    set_tablet_mode(mode)
    print(f"Tablet mode is now: {'ON' if is_tablet_mode() else 'OFF'}")
