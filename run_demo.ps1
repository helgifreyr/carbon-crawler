param(
    [string]$Script = "$PSScriptRoot\demo\arpg_client.py",
    [int]$TimeoutSec = 0,
    [string]$RunName = ""
)

$triplet = "$PSScriptRoot\vcpkg_installed\x64-windows-v143-internal"
# A RunName ending in "#" takes the first numbered slot whose exe isn't running, so the exe path repeats across
# launches (the firewall remembers programs by path) while several copies can still run side by side.
if ($RunName.EndsWith("#")) {
    $base = $RunName.TrimEnd("#")
    foreach ($i in 1..32) {
        $exe = "$PSScriptRoot\.run\$base$i\exefile_Internal.exe"
        $free = -not (Test-Path $exe)
        if (-not $free) {
            try { [IO.File]::Open($exe, "Open", "ReadWrite", "None").Close(); $free = $true } catch { }
        }
        if ($free) { $RunName = "$base$i"; break }
    }
}
$run = if ($RunName) { "$PSScriptRoot\.run\$RunName" } else { "$PSScriptRoot\.run" }
if (-not (Test-Path "$triplet\tools\carbon-exefile\exefile_Internal.exe")) {
    throw "exefile not found under $triplet - run install_deps.sh first"
}

New-Item -ItemType Directory -Force $run | Out-Null
Copy-Item "$triplet\tools\carbon-exefile\*", "$triplet\bin\blue_internal.pyd", "$triplet\lib\_destiny_internal.pyd" $run -Force
Get-ChildItem "$triplet\bin", "$triplet\lib" -Filter "_trinity_*.pyd" -ErrorAction SilentlyContinue | Copy-Item -Destination $run -Force

$saved = @{}
foreach ($name in "PYTHONHOME", "PYTHONPATH", "BUILDFLAVOR", "PATH", "CARBON_BIN") {
    $saved[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
}

try {
    $env:PYTHONHOME = "$triplet\tools\python3"
    $env:PYTHONPATH = @(
        $run, "$triplet\bin", "$triplet\lib", "$triplet\bin\python", "$triplet\python",
        "$triplet\tools\python3\Lib", "$triplet\tools\python3\DLLs", "$PSScriptRoot\vendor\pydeps"
    ) -join ";"
    $env:BUILDFLAVOR = "internal"
    $env:CARBON_BIN = "$triplet\bin"
    $env:PATH = "$run;$triplet\bin;$env:PATH"

    # exefile is a GUI-subsystem exe, so PowerShell won't wait on it or capture its output without this.
    $proc = Start-Process "$run\exefile_Internal.exe" -ArgumentList "/inherit", "/buildflavor=internal", "/py", "`"$Script`"" `
        -NoNewWindow -PassThru -RedirectStandardOutput "$run\stdout.log" -RedirectStandardError "$run\stderr.log"
    $deadline = if ($TimeoutSec -gt 0) { (Get-Date).AddSeconds($TimeoutSec) } else { [datetime]::MaxValue }
    $offsets = @{ "stdout.log" = 0L; "stderr.log" = 0L }
    function Show-NewOutput {
        foreach ($log in @($offsets.Keys)) {
            $stream = [IO.File]::Open("$run\$log", "Open", "Read", "ReadWrite")
            try {
                $stream.Seek($offsets[$log], "Begin") | Out-Null
                $text = (New-Object IO.StreamReader($stream)).ReadToEnd()
                $offsets[$log] = $stream.Position
            } finally { $stream.Dispose() }
            if ($text) { [Console]::Out.Write($text) }
        }
    }
    while (-not $proc.WaitForExit(200)) {
        Show-NewOutput
        if ((Get-Date) -gt $deadline) {
            Stop-Process -Id $proc.Id -Force
            Write-Warning "timed out after $TimeoutSec s; killed pid $($proc.Id)"
            break
        }
    }
    Show-NewOutput
    $code = $proc.ExitCode
} finally {
    if ($proc -and -not $proc.HasExited) { Stop-Process -Id $proc.Id -Force }
    foreach ($name in $saved.Keys) {
        [Environment]::SetEnvironmentVariable($name, $saved[$name], "Process")
    }
}
exit $code
