param([int]$ConsolePid, [string]$Result)
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class CtrlC {
    [DllImport("kernel32.dll")] static extern bool AttachConsole(uint pid);
    [DllImport("kernel32.dll")] static extern bool FreeConsole();
    [DllImport("kernel32.dll")] static extern bool SetConsoleCtrlHandler(IntPtr h, bool add);
    [DllImport("kernel32.dll")] static extern bool GenerateConsoleCtrlEvent(uint ev, uint group);
    public static string Send(uint pid) {
        FreeConsole();
        if (!AttachConsole(pid)) return "attach failed " + Marshal.GetLastWin32Error();
        SetConsoleCtrlHandler(IntPtr.Zero, true);
        bool ok = GenerateConsoleCtrlEvent(0, 0);
        System.Threading.Thread.Sleep(300);
        return ok ? "sent" : "send failed";
    }
}
'@
[CtrlC]::Send($ConsolePid) | Out-File $Result
