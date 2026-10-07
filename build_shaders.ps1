param([switch]$Rebuild)

$triplet = "$PSScriptRoot\vcpkg_installed\x64-windows-v143-internal"
$compiler = Get-ChildItem -Path $triplet -Recurse -Filter "ShaderCompiler*.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $compiler) { throw "ShaderCompiler.exe not found under $triplet - install carbon-trinity[shader-compiler]" }

$effectRoot = "$PSScriptRoot\res\graphics\effect"
$outRoot = "$PSScriptRoot\res\graphics\effect.dx11"
$models = @{ "sm_lo" = 3; "sm_hi" = 4; "sm_depth" = 5 }
$platformDx11 = 2
$failed = 0

$env:PATH = "$($compiler.DirectoryName);$triplet\bin;$env:PATH"

foreach ($fx in Get-ChildItem -Path $effectRoot -Recurse -Filter "*.fx") {
    $relative = $fx.FullName.Substring($effectRoot.Length + 1).ToLower()
    foreach ($ext in $models.Keys) {
        $out = Join-Path $outRoot ([IO.Path]::ChangeExtension($relative, $ext))
        if (-not $Rebuild -and (Test-Path $out) -and (Get-Item $out).LastWriteTime -gt (Get-ChildItem $fx.DirectoryName -Filter "*.fx*" | Measure-Object LastWriteTime -Maximum).Maximum) {
            continue
        }
        New-Item -ItemType Directory -Force (Split-Path $out) | Out-Null
        & $compiler.FullName /single /O3 /define SHADERMODEL $models[$ext] /define PLATFORM $platformDx11 $fx.FullName $out
        if ($LASTEXITCODE -ne 0) { $failed++; Write-Host "FAILED: $relative ($ext)" -ForegroundColor Red }
        else { Write-Host "ok  $relative -> $ext" }
    }
}
exit $failed
