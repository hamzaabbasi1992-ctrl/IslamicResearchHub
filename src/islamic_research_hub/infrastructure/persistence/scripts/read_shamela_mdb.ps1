<#
.SYNOPSIS
Reads a batch of Maktaba Shamela .mdb files (Jet 3/Access-97 format) via
the older Microsoft.Jet.OLEDB.4.0 provider (32-bit only, so this script
must run under 32-bit PowerShell - the modern ACE-based providers refuse
to open these files at all).

.DESCRIPTION
Each real Shamela book is its own .mdb file with exactly two tables:
"book" (page/paragraph content) and "title" (table-of-contents headings).
The "book" table's real column set varies between files (some carry a
"seal" column, others carry "hno"/"Sora"/"Aya"/"na" instead) - confirmed
by direct inspection of real files, not assumed - so this script reads
whatever columns are actually present per file rather than a fixed list.

Real bug found running a full 100-file batch: accumulating every file's
rows in memory and calling `ConvertTo-Json` once at the end throws
`System.OutOfMemoryException` in 32-bit PowerShell (a small usable
address space) - and PowerShell still exits 0 despite the fatal error,
so the failure was silently invisible to the calling process. Fixed by
streaming NDJSON: one compact JSON line per file, written and flushed
immediately, with that file's rows discarded before the next one starts
- peak memory is bounded by roughly one file's data, not the whole batch.

.PARAMETER JobsFile
Path to a JSON file: an array of {"Path": "..."} (one per .mdb to read).

.PARAMETER ResultsFile
Path to write as newline-delimited JSON (one compact object per line):
{"Path", "Succeeded", "Error", "BookRows", "TitleRows"}. "BookRows"/
"TitleRows" are each an array of objects with whatever columns that
file's real table actually has.
#>
param(
    [Parameter(Mandatory=$true)][string]$JobsFile,
    [Parameter(Mandatory=$true)][string]$ResultsFile
)

function Read-AllRows($connection, $tableName) {
    $rs = New-Object -ComObject ADODB.Recordset
    $rs.Open("SELECT * FROM [$tableName]", $connection, 3, 1)
    $rows = [System.Collections.Generic.List[object]]::new()
    while (-not $rs.EOF) {
        $row = [ordered]@{}
        foreach ($field in $rs.Fields) {
            $value = $field.Value
            if ($value -is [byte[]]) { $value = [Convert]::ToBase64String($value) }
            $row[$field.Name] = $value
        }
        $rows.Add([PSCustomObject]$row)
        $rs.MoveNext()
    }
    $rs.Close()
    return $rows
}

$jobs = Get-Content $JobsFile -Raw -Encoding UTF8 | ConvertFrom-Json
# PowerShell 5.1 unwraps single-element JSON arrays into a bare object; force array context.
if ($jobs -isnot [System.Array]) { $jobs = @($jobs) }

$writer = New-Object System.IO.StreamWriter($ResultsFile, $false, [System.Text.Encoding]::UTF8)
try {
    foreach ($job in $jobs) {
        $path = $job.Path
        $succeeded = $false
        $errorMessage = $null
        $bookRows = @()
        $titleRows = @()

        $conn = New-Object -ComObject ADODB.Connection
        try {
            $conn.Open("Provider=Microsoft.Jet.OLEDB.4.0;Data Source=$path;")
            $bookRows = Read-AllRows $conn "book"
            $titleRows = Read-AllRows $conn "title"
            $succeeded = $true
        } catch {
            $succeeded = $false
            $errorMessage = $_.Exception.Message
        } finally {
            if ($conn.State -ne 0) { $conn.Close() }
        }

        $result = [PSCustomObject]@{
            Path = $path
            Succeeded = $succeeded
            Error = $errorMessage
            BookRows = $bookRows
            TitleRows = $titleRows
        }

        try {
            $line = $result | ConvertTo-Json -Compress -Depth 6
        } catch {
            # Serialization itself failed (e.g. one pathologically large file) -
            # report it as this one file's failure instead of losing the whole
            # batch to an out-of-memory crash.
            $failResult = [PSCustomObject]@{
                Path = $path
                Succeeded = $false
                Error = "Result serialization failed: $($_.Exception.Message)"
                BookRows = @()
                TitleRows = @()
            }
            $line = $failResult | ConvertTo-Json -Compress -Depth 2
        }
        $writer.WriteLine($line)
        $writer.Flush()

        # Drop references before the next file so 32-bit PowerShell's limited
        # address space isn't held by rows already written out.
        $bookRows = $null
        $titleRows = $null
        $result = $null
    }
} finally {
    $writer.Close()
}
