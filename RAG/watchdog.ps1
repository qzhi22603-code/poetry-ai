$c = New-Object Net.Sockets.TcpClient
$alive = $false
try { $c.Connect("127.0.0.1", 11499); $alive = $true } catch { $alive = $false }
finally { $c.Close() }
if (-not $alive) {
    Start-Process wscript.exe -ArgumentList '"C:\Users\38107\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\poemly-rag-proxy.vbs"'
}
