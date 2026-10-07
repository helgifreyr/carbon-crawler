param([string]$Script = "trinity_viewer.py")

# exefile is a GUI-subsystem program: it never sees the console's Ctrl+C and its output goes nowhere. Run it from
# here instead, echo its output, and stop it when this window is closed or Ctrl+C is pressed.
$here = $PSScriptRoot
$logs = Join-Path $here "logs"
New-Item -ItemType Directory -Force $logs | Out-Null
$name = [IO.Path]::GetFileNameWithoutExtension($Script)
$out, $err = (Join-Path $logs "$name.log"), (Join-Path $logs "$name.err.log")
$proc = Start-Process (Join-Path $here "bin\exefile_Internal.exe") -NoNewWindow -PassThru `
    -ArgumentList "/inherit", "/buildflavor=internal", "/py", "`"$(Join-Path $here "app\$Script")`"" `
    -RedirectStandardOutput $out -RedirectStandardError $err
# A job object that kills what it holds when its last handle closes: however this script ends (Ctrl+C, the window
# closed, the process killed), the game goes with it.
Add-Type -TypeDefinition @'
using System; using System.Runtime.InteropServices;
public static class KillOnClose {
    [StructLayout(LayoutKind.Sequential)] struct Basic { public long a, b; public uint flags; public UIntPtr c, d; public uint e; public UIntPtr f; public uint g, h; }
    [StructLayout(LayoutKind.Sequential)] struct Io { public ulong a, b, c, d, e, f; }
    [StructLayout(LayoutKind.Sequential)] struct Extended { public Basic basic; public Io io; public UIntPtr i, j, k, l; }
    [DllImport("kernel32.dll")] static extern IntPtr CreateJobObject(IntPtr a, string name);
    [DllImport("kernel32.dll")] static extern bool SetInformationJobObject(IntPtr job, int cls, ref Extended info, uint size);
    [DllImport("kernel32.dll")] static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);
    public static IntPtr Hold(IntPtr process) {
        IntPtr job = CreateJobObject(IntPtr.Zero, null);
        Extended info = new Extended();
        info.basic.flags = 0x2000;
        SetInformationJobObject(job, 9, ref info, (uint)Marshal.SizeOf(typeof(Extended)));
        AssignProcessToJobObject(job, process);
        return job;
    }
}
'@
$job = [KillOnClose]::Hold($proc.Handle)
$offsets = @{ $out = 0L; $err = 0L }
function Show-NewOutput {
    foreach ($log in @($offsets.Keys)) {
        if (-not (Test-Path $log)) { continue }
        $stream = [IO.File]::Open($log, "Open", "Read", "ReadWrite")
        try {
            $stream.Seek($offsets[$log], "Begin") | Out-Null
            $text = (New-Object IO.StreamReader($stream)).ReadToEnd()
            $offsets[$log] = $stream.Position
        } finally { $stream.Dispose() }
        if ($text) { [Console]::Out.Write($text) }
    }
}
try {
    while (-not $proc.WaitForExit(200)) { Show-NewOutput }
    Show-NewOutput
    $code = $proc.ExitCode
} finally {
    if (-not $proc.HasExited) { Stop-Process -Id $proc.Id -Force; Write-Host "stopped" }
}
exit $code
