# find-lockers.ps1 — list processes holding a file open, via the Windows
# Restart Manager (the same API installers use). Prints one line per holder:
#   PID<TAB>ProcessName<TAB>ExecutablePath
# or "NONE" when nothing holds the file. Used by prebuild-clean.js to give an
# actionable error when the electron-builder output directory cannot be
# emptied (locked app.asar etc.).
param([Parameter(Mandatory = $true)][string]$Target)

Add-Type @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public static class FileLockFinder {
    [StructLayout(LayoutKind.Sequential)]
    struct RM_UNIQUE_PROCESS { public int dwProcessId; public System.Runtime.InteropServices.ComTypes.FILETIME ProcessStartTime; }

    const int CCH_RM_MAX_APP_NAME = 255;
    const int CCH_RM_MAX_SVC_NAME = 63;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct RM_PROCESS_INFO {
        public RM_UNIQUE_PROCESS Process;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_APP_NAME + 1)] public string strAppName;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = CCH_RM_MAX_SVC_NAME + 1)] public string strServiceShortName;
        public int ApplicationType;
        public uint AppStatus;
        public uint TSSessionId;
        [MarshalAs(UnmanagedType.Bool)] public bool bRestartable;
    }

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Unicode)]
    static extern int RmRegisterResources(uint pSessionHandle, uint nFiles, string[] rgsFilenames, uint nApplications, [In] RM_UNIQUE_PROCESS[] rgApplications, uint nServices, string[] rgsServiceNames);

    [DllImport("rstrtmgr.dll", CharSet = CharSet.Auto)]
    static extern int RmStartSession(out uint pSessionHandle, int dwSessionFlags, string strSessionKey);

    [DllImport("rstrtmgr.dll")]
    static extern int RmEndSession(uint pSessionHandle);

    [DllImport("rstrtmgr.dll")]
    static extern int RmGetList(uint dwSessionHandle, out uint pnProcInfoNeeded, ref uint pnProcInfo, [In, Out] RM_PROCESS_INFO[] rgAffectedApps, ref uint lpdwRebootReasons);

    public static List<int> FindLockers(string path) {
        uint handle;
        string key = Guid.NewGuid().ToString();
        var pids = new List<int>();
        int res = RmStartSession(out handle, 0, key);
        if (res != 0) throw new Exception("RmStartSession failed: " + res);
        try {
            uint needed = 0, count = 0, reasons = 0;
            string[] resources = new string[] { path };
            res = RmRegisterResources(handle, 1, resources, 0, null, 0, null);
            if (res != 0) throw new Exception("RmRegisterResources failed: " + res);
            res = RmGetList(handle, out needed, ref count, null, ref reasons);
            if (res == 234) {
                RM_PROCESS_INFO[] info = new RM_PROCESS_INFO[needed];
                count = needed;
                res = RmGetList(handle, out needed, ref count, info, ref reasons);
                if (res == 0) {
                    for (int i = 0; i < count; i++) pids.Add(info[i].Process.dwProcessId);
                }
            }
        } finally { RmEndSession(handle); }
        return pids;
    }
}
'@

try {
    $lockers = [FileLockFinder]::FindLockers($Target)
} catch {
    Write-Output "ERROR`t$($_.Exception.Message)"
    exit 0
}
if ($lockers.Count -eq 0) {
    Write-Output "NONE"
    exit 0
}
foreach ($p in $lockers) {
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$p" -ErrorAction SilentlyContinue
    if ($null -eq $proc) { Write-Output "$p`t(unknown)`t"; continue }
    Write-Output "$($p)`t$($proc.Name)`t$($proc.ExecutablePath)"
}
