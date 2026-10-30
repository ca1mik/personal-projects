param(
    [string[]]$Domains = @("ppdstr.online", "ppdstr.ru")
)

foreach ($domain in $Domains) {
    Write-Host ""
    Write-Host "=== $domain ==="

    try {
        $records = Resolve-DnsName $domain -ErrorAction Stop |
            Where-Object { $_.Type -eq "A" } |
            Select-Object -ExpandProperty IPAddress -Unique

        if ($records) {
            Write-Host "DNS A:" ($records -join ", ")
        } else {
            Write-Host "DNS A: no A records found"
        }
    } catch {
        Write-Host "DNS A: ERROR -" $_.Exception.Message
    }

    foreach ($scheme in @("http", "https")) {
        $url = "${scheme}://$domain"
        $headers = & cmd.exe /d /c "curl.exe -sS -I --max-time 15 $url 2>&1"
        if ($LASTEXITCODE -ne 0) {
            $message = ($headers | Out-String).Trim()
            if (-not $message) {
                $message = "curl exited with code $LASTEXITCODE"
            }
            Write-Host "$scheme : ERROR - $message"
            continue
        }

        $statusLine = ($headers | Select-Object -First 1)
        if (-not $statusLine) {
            $statusLine = "no response"
        }
        Write-Host "$scheme : $statusLine"
    }
}
