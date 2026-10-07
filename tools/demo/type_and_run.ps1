param([string]$Command, [string]$EnvB64 = "", [double]$DelayS = 0, [string]$Dir = "", [string]$Tag = "")

# For the demo recording: sets the scene's settings out of sight, then types the command like a person would and runs it.
if ($EnvB64) {
    $vars = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($EnvB64)) | ConvertFrom-Json
    foreach ($p in $vars.PSObject.Properties) { Set-Item -Path "env:$($p.Name)" -Value $p.Value }
}
if ($Dir) { Set-Location $Dir }
Clear-Host
function Show-Prompt {
    Write-Host -NoNewline "carbon-crawler " -ForegroundColor DarkYellow
    Write-Host -NoNewline ([char]0x276F + " ") -ForegroundColor DarkGray
}
# The shell's own prompt after the command finishes matches the one typed at.
function global:prompt { "$([char]27)[33mcarbon-crawler$([char]27)[90m $([char]0x276F)$([char]27)[0m " }
Show-Prompt
Start-Sleep -Milliseconds ([int]($DelayS * 1000))
$rng = New-Object Random
foreach ($ch in $Command.ToCharArray()) {
    Write-Host -NoNewline $ch
    Start-Sleep -Milliseconds (45 + $rng.Next(70))
}
Start-Sleep -Milliseconds 350
Write-Host ""
& cmd /c $Command
# Show the prompt and just wait: this shell never reads input, so keys typed into it by mistake never run.
Write-Host -NoNewline (prompt)
while ($true) { Start-Sleep -Seconds 60 }
