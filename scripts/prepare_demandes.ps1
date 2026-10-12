<#!
Convertit le classeur source en JSON compatible avec l'application.
Ne remplace jamais une base existante. Le statut du classeur est conserve.
#>
param(
    [string]$Source = 'data/exemples/Demande.xlsx',
    [Parameter(Mandatory=$true)][string]$OutputPath
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem
if (Test-Path -LiteralPath $OutputPath) { throw 'Le fichier de sortie existe deja.' }
$fields = 'RequestReference RequestDate RequesterReference ReportedAdress ReportedCity AffectedStreets LocationLandmark CustomerName BusinessDomain LeakReportReference RequestReason MeterReference ReportedMaterial ReportedDiameter ReportedRoadType ReportedRoadTypeOther ReportedSurfaceType RoadImpact EstimatedWorkDays DictAtuIndicator WaterShutdownIndicator SafetyInstructions SpecialConditions RequestComment ImpactTransport RequestStatus CreatedAt UpdatedAt'.Split(' ')
$multiple = @('ReportedRoadType', 'ReportedSurfaceType', 'RoadImpact')
$knownHeaders = @($fields | Where-Object { $_ -ne 'ImpactTransport' }) + @('ImpactTransport1', 'RoadImpactOther', 'WaterShutdownIndicatorOther')
$culture = [Globalization.CultureInfo]::InvariantCulture
$book = [IO.Compression.ZipFile]::OpenRead([IO.Path]::GetFullPath($Source))
function Read-XmlEntry([string]$name) {
    $entry = $book.GetEntry($name)
    if (-not $entry) { throw "Entree XLSX absente : $name" }
    $reader = [IO.StreamReader]::new($entry.Open())
    try { return [xml]$reader.ReadToEnd() } finally { $reader.Dispose() }
}
try {
    $workbook = Read-XmlEntry 'xl/workbook.xml'
    $sheetInfo = @($workbook.workbook.sheets.sheet | Where-Object name -eq 'Demande')
    if ($sheetInfo.Count -ne 1) { throw 'Une feuille Demande unique est attendue.' }
    $relationId = $sheetInfo[0].GetAttribute('id', 'http://schemas.openxmlformats.org/officeDocument/2006/relationships')
    $relationships = Read-XmlEntry 'xl/_rels/workbook.xml.rels'
    $target = ($relationships.Relationships.Relationship | Where-Object Id -eq $relationId).Target
    $sheetPath = if ($target.StartsWith('/')) { $target.TrimStart('/') } else { 'xl/' + $target }
    $stringsXml = Read-XmlEntry 'xl/sharedStrings.xml'
    $strings = @($stringsXml.sst.si | ForEach-Object { $_.InnerText })
    $sheet = Read-XmlEntry $sheetPath
    $headers = @{}
    $references = [Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
    $records = [Collections.Generic.List[object]]::new()
    $invalidDiameters = 0
    $extraComments = 0
    foreach ($sourceRow in $sheet.worksheet.sheetData.row) {
        $sourceRecord = @{}
        foreach ($cell in $sourceRow.c) {
            if ($null -ne $cell.f) { throw "Formule non prise en charge : $($cell.r)" }
            $column = $cell.r -replace '\d', ''
            $value = $cell.v
            if ($cell.t -eq 's') { $value = $strings[[int]$value] }
            elseif ($cell.t -eq 'b') { $value = [string]$value -eq '1' }
            elseif ($cell.t -eq 'inlineStr') { $value = $cell.is.InnerText }
            elseif ($cell.t -eq 'e') { throw "Erreur Excel en $($cell.r)" }
            if ($sourceRow.r -eq '1') {
                if ($knownHeaders -cnotcontains $value -or $headers.Values -ccontains $value) { throw "Colonne inconnue ou dupliquee : $value" }
                $headers[$column] = $value
            } elseif ($headers.ContainsKey($column)) { $sourceRecord[$headers[$column]] = $value }
        }
        if ($sourceRow.r -eq '1') { continue }
        if (-not $sourceRecord.Count) { continue }
        $record = [ordered]@{}
        foreach ($field in $fields) { $record[$field] = $null }
        foreach ($field in $fields) {
            $sourceField = if ($field -eq 'ImpactTransport') { 'ImpactTransport1' } else { $field }
            $value = $sourceRecord[$sourceField]
            if ($null -ne $value -and ($value -is [bool] -or -not [string]::IsNullOrWhiteSpace([string]$value))) {
                $record[$field] = $value
            }
        }
        $reference = [string]$record.RequestReference
        if ($reference -cnotmatch '^DEM-[0-9]{6}$' -or [int]$reference.Substring(4) -eq 0 -or -not $references.Add($reference)) {
            throw "Reference invalide ou dupliquee : $reference"
        }
        foreach ($field in $multiple) {
            if ($null -ne $record[$field]) {
                $raw = [string]$record[$field]
                if (-not $raw.TrimStart().StartsWith('[')) { throw "$reference : tableau attendu pour $field" }
                $array = ConvertFrom-Json -InputObject $raw
                foreach ($item in $array) { if ($item -isnot [string]) { throw "$reference : valeur non textuelle dans $field" } }
                $record[$field] = @($array)
            }
        }
        $notes = [Collections.Generic.List[string]]::new()
        foreach ($field in @('ReportedDiameter', 'EstimatedWorkDays')) {
            if ($null -ne $record[$field]) {
                $raw = [string]$record[$field]
                $number = 0.0
                $valid = $raw.Trim() -match '^\d+([.,]\d+)?$' -and [double]::TryParse($raw.Trim().Replace(',', '.'), [Globalization.NumberStyles]::AllowDecimalPoint, $culture, [ref]$number)
                if ($valid -and -not [double]::IsInfinity($number)) { $record[$field] = $number }
                else {
                    $record[$field] = $null
                    $notes.Add("[Import Demande.xlsx - $field] $raw")
                    if ($field -eq 'ReportedDiameter') { $invalidDiameters++ }
                }
            }
        }
        foreach ($field in @('RoadImpactOther', 'WaterShutdownIndicatorOther')) {
            if (-not [string]::IsNullOrWhiteSpace([string]$sourceRecord[$field])) {
                $notes.Add("[Import Demande.xlsx - $field] $($sourceRecord[$field])")
                $extraComments++
            }
        }
        if ($notes.Count) {
            $pieces = @()
            if ($record.RequestComment) { $pieces += [string]$record.RequestComment }
            $pieces += $notes.ToArray()
            $record.RequestComment = $pieces -join "`n"
        }
        foreach ($field in @('RequestDate', 'CreatedAt', 'UpdatedAt')) {
            if ($null -ne $record[$field]) {
                $value = [string]$record[$field]
                if ($value -notmatch '^\d{4}-\d{2}-\d{2}(T\d{2}:\d{2}:\d{2})?$') { throw "$reference : date ISO attendue dans $field" }
                $parsed = [datetime]::Parse($value, $culture)
                $record[$field] = if ($field -eq 'RequestDate') { $parsed.ToString('yyyy-MM-dd') } else { $parsed.ToString("yyyy-MM-dd'T'HH:mm:ss") }
            }
        }
        if ($record.ImpactTransport -isnot [bool]) { throw "$reference : ImpactTransport1 doit etre booleen" }
        $records.Add([pscustomobject]$record)
    }
    if ($records.Count -eq 0) { throw 'Aucune demande a importer.' }
    foreach ($field in $knownHeaders) {
        if ($headers.Values -cnotcontains $field) { throw "Colonne source absente : $field" }
    }
    $json = ConvertTo-Json -InputObject $records.ToArray() -Depth 10
    $absoluteOutput = [IO.Path]::GetFullPath($OutputPath)
    # CreateNew interdit tout ecrasement, meme si le fichier apparait en cours de conversion.
    $stream = [IO.File]::Open($absoluteOutput, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write)
    $writer = [IO.StreamWriter]::new($stream, [Text.UTF8Encoding]::new($false))
    try { $writer.Write($json + "`n") } finally { $writer.Dispose() }
    [pscustomobject]@{Count=$records.Count;InvalidDiametersPreserved=$invalidDiameters;ExtraCommentsPreserved=$extraComments;Output=$absoluteOutput} | ConvertTo-Json
} finally { $book.Dispose() }
