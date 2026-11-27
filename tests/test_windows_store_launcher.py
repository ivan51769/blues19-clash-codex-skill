import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import unittest


ASSET = (Path(__file__).resolve().parents[1] / 'skills' / 'clash-codex-optimizer'
         / 'assets' / 'start-windows-store-codex.ps1')
POWERSHELL = shutil.which('powershell.exe') if os.name == 'nt' else None
WRAPPER = r'''
param([int]$Port, [switch]$ExpectClosed)
$ErrorActionPreference = 'Stop'
function Get-AppxPackage($Name) {
    if ($Name -ne 'OpenAI.Codex') { throw 'Unexpected package lookup' }
    [pscustomobject]@{InstallLocation = $PSScriptRoot}
}
function Get-AppxPackageManifest($Package) {
    [xml]'<Package><Applications><Application Id="App" Executable="app/ChatGPT.exe" /></Applications></Package>'
}
function Get-Command($Name, $CommandType) {
    if ($Name -ne 'chatgpt-desktop.exe' -or $CommandType -ne 'Application') { throw 'Unexpected alias lookup' }
    [pscustomobject]@{Source = 'synthetic-alias.exe'}
}
function Get-Process($Name, $ErrorAction) {
    if ($Name -ne 'ChatGPT') { throw 'Unexpected process lookup' }
}
function Start-Process($FilePath, $ArgumentList) {
    if ($ExpectClosed) { throw 'Launcher tried to start with a closed port' }
    $proxy = "http://127.0.0.1:$Port"
    if ($FilePath -ne 'synthetic-alias.exe' -or $ArgumentList -ne "--proxy-server=$proxy" -or
        $env:HTTP_PROXY -ne $proxy -or $env:HTTPS_PROXY -ne $proxy -or
        $env:ALL_PROXY -ne $proxy -or $env:NO_PROXY -ne 'localhost,127.0.0.1,::1') {
        throw 'Incorrect child launch configuration'
    }
    'mock-launch-ok'
}
$env:HTTP_PROXY = 'original'
Remove-Item Env:ALL_PROXY -ErrorAction SilentlyContinue
try { & "$PSScriptRoot/start-windows-store-codex.ps1" -ProxyPort $Port }
catch {
    if (!$ExpectClosed -or $_.Exception.Message -notlike '*not listening*') { throw }
    'closed-port-refused'
}
if ($env:HTTP_PROXY -ne 'original' -or (Test-Path Env:ALL_PROXY)) { throw 'Proxy leaked into caller' }
'env-restored'
'''


@unittest.skipUnless(POWERSHELL, 'Windows PowerShell required for the Windows Store launcher')
class WindowsStoreLauncherTests(unittest.TestCase):
    def launch(self, listen):
        with socket.socket() as loopback, tempfile.TemporaryDirectory() as temp:
            loopback.bind(('127.0.0.1', 0))
            if listen:
                loopback.listen(1)
            root = Path(temp)
            (root / ASSET.name).write_bytes(ASSET.read_bytes())
            wrapper = root / 'verify.ps1'
            wrapper.write_text(WRAPPER, encoding='ascii')
            cmd = [POWERSHELL, '-NoProfile', '-NonInteractive', '-File', str(wrapper),
                   '-Port', str(loopback.getsockname()[1])]
            if not listen:
                cmd.append('-ExpectClosed')
            result = subprocess.run(cmd, cwd=root, capture_output=True, text=True, errors='replace', timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('env-restored', result.stdout)
        return result.stdout

    def test_launch_with_explicit_loopback_proxy_and_restore_caller_environment(self):
        self.assertIn('mock-launch-ok', self.launch(listen=True))

    def test_closed_port_does_not_launch(self):
        self.assertIn('closed-port-refused', self.launch(listen=False))
