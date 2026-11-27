# Launch the installed Windows Store Codex with a process-local HTTP proxy.
param(
    [Parameter(Mandatory = $true)]
    [ValidateRange(1, 65535)]
    [int]$ProxyPort,
    [switch]$ShowErrorDialog
)

$ErrorActionPreference = 'Stop'
$lock = [Threading.Mutex]::new($false, 'Local\ClashCodexOptimizerWindowsStore')
$owned = $false
try {
    try { $owned = $lock.WaitOne(0) } catch [Threading.AbandonedMutexException] { $owned = $true }
    if (-not $owned) { return }

    $package = Get-AppxPackage OpenAI.Codex | Select-Object -First 1
    if (-not $package) { throw 'The Microsoft Store Codex app is not installed.' }
    $app = (Get-AppxPackageManifest $package).Package.Applications.Application |
        Where-Object Id -eq 'App' | Select-Object -First 1
    if (-not $app.Executable) { throw 'The Store desktop entry was not found in the package manifest.' }
    $image = [IO.Path]::GetFullPath((Join-Path $package.InstallLocation $app.Executable))
    $processName = [IO.Path]::GetFileNameWithoutExtension($image)
    $alias = (Get-Command chatgpt-desktop.exe -CommandType Application).Source

    $deadline = (Get-Date).AddSeconds(15)
    $previousId = 0
    do {
        $instances = @(Get-Process -Name $processName -ErrorAction SilentlyContinue |
            Where-Object { $_.Path -eq $image } | Sort-Object StartTime)
        if (-not $instances.Count) { break }
        $window = $instances | Where-Object {
            $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -eq 'ChatGPT' -and $_.Responding
        } | Select-Object -First 1
        if ($window) {
            [void](New-Object -ComObject WScript.Shell).AppActivate($window.Id)
            return
        }
        $now = Get-Date
        if ($previousId -ne $instances[0].Id) {
            $previousId = $instances[0].Id
            $steadySince = $now
        }
        # Give a closing instance time to exit; a stable tray instance can take the alias handoff.
        if (($now - $steadySince).TotalSeconds -ge 4 -and
            ($now - $instances[0].StartTime).TotalSeconds -ge 10 -and
            -not ($instances | Where-Object MainWindowTitle)) { break }
        if ($now -ge $deadline) { throw 'Codex is still closing or starting. Close any error dialog, then try again.' }
        Start-Sleep -Milliseconds 300
    } while ($true)

    $tcp = [Net.Sockets.TcpClient]::new()
    try {
        $connection = $tcp.ConnectAsync('127.0.0.1', $ProxyPort)
        if (-not $connection.Wait(1500) -or -not $tcp.Connected) { throw 'Proxy unavailable.' }
    } catch {
        throw "Clash is not listening on 127.0.0.1:$ProxyPort. Start Clash or verify its HTTP/mixed port."
    } finally { $tcp.Dispose() }

    $proxy = "http://127.0.0.1:$ProxyPort"
    $child = @{ HTTP_PROXY = $proxy; HTTPS_PROXY = $proxy; ALL_PROXY = $proxy; NO_PROXY = 'localhost,127.0.0.1,::1' }
    $previous = @{}
    foreach ($key in $child.Keys) { $previous[$key] = [Environment]::GetEnvironmentVariable($key, 'Process') }
    try {
        foreach ($key in $child.Keys) { [Environment]::SetEnvironmentVariable($key, $child[$key], 'Process') }
        Start-Process -FilePath $alias -ArgumentList "--proxy-server=$proxy"
    } finally {
        foreach ($key in $child.Keys) { [Environment]::SetEnvironmentVariable($key, $previous[$key], 'Process') }
    }
} catch {
    if ($ShowErrorDialog) {
        Add-Type -AssemblyName System.Windows.Forms
        [void][Windows.Forms.MessageBox]::Show($_.Exception.Message, 'Codex Desktop', 'OK', 'Warning')
    }
    throw
} finally {
    if ($owned) { $lock.ReleaseMutex() }
    $lock.Dispose()
}
