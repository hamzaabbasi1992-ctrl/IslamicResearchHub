<#
.SYNOPSIS
Decrypts a batch of Jibreel Desktop .mjbx files to plain, unencrypted .mjbz
files using the app's own System.Data.SQLite.dll (32-bit only, so this
script must run under 32-bit PowerShell).

.PARAMETER JobsFile
Path to a JSON file: an array of {"Source": "...", "Destination": "..."}.

.PARAMETER SqliteDllPath
Path to the Jibreel Desktop app's own System.Data.SQLite.dll.

.PARAMETER Password
The .mjbx encryption password.

.PARAMETER ResultsFile
Path to write a JSON array of {"Source", "Destination", "Succeeded"} to.
#>
param(
    [Parameter(Mandatory=$true)][string]$JobsFile,
    [Parameter(Mandatory=$true)][string]$SqliteDllPath,
    [Parameter(Mandatory=$true)][string]$Password,
    [Parameter(Mandatory=$true)][string]$ResultsFile
)

Add-Type -Path $SqliteDllPath

$jobs = Get-Content $JobsFile -Raw | ConvertFrom-Json
# PowerShell 5.1 unwraps single-element JSON arrays into a bare object; force array context.
if ($jobs -isnot [System.Array]) { $jobs = @($jobs) }
$results = [System.Collections.Generic.List[object]]::new()

foreach ($job in $jobs) {
    $source = $job.Source
    $destination = $job.Destination
    $destDir = Split-Path $destination -Parent
    if (-not (Test-Path $destDir)) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
    if (Test-Path $destination) { Remove-Item $destination -Force }

    $srcConnStr = "Data Source=$source;Version=3;New=False;Compress=True;Password=$Password"
    $destConnStr = "Data Source=$destination;Version=3;New=True"
    $srcConn = New-Object System.Data.SQLite.SQLiteConnection($srcConnStr)
    $destConn = New-Object System.Data.SQLite.SQLiteConnection($destConnStr)
    $succeeded = $false
    try {
        $srcConn.Open()
        $destConn.Open()
        $srcConn.BackupDatabase($destConn, "main", "main", -1, $null, 0)
        $succeeded = $true
    } catch {
        $succeeded = $false
    } finally {
        if ($srcConn) { $srcConn.Close() }
        if ($destConn) { $destConn.Close() }
        if (-not $succeeded -and (Test-Path $destination)) { Remove-Item $destination -Force }
    }
    $results.Add([PSCustomObject]@{ Source = $source; Destination = $destination; Succeeded = $succeeded })
}

# PowerShell 5.1 unwraps a single-element list into a bare JSON object; force array framing.
$json = $results | ConvertTo-Json -Depth 3
if ($results.Count -eq 1) { $json = "[$json]" }
elseif ($results.Count -eq 0) { $json = "[]" }
$json | Out-File -Encoding utf8 $ResultsFile
