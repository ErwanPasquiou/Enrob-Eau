<# Genere un jeu coherent dans un NOUVEAU dossier, sans modifier la base active. #>
param(
    [Parameter(Mandatory=$true)][string]$RequestsPath,
    [Parameter(Mandatory=$true)][string]$OutputDirectory,
    [datetime]$AsOf = '2026-10-12',
    [int]$OrderSequence = 9,
    [int]$ServiceSequence = 11
)
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $OutputDirectory) { throw 'Le dossier de sortie existe deja.' }
if ($OrderSequence -lt 0 -or $ServiceSequence -lt 0) { throw 'Compteur negatif.' }
$requestsJson = Get-Content -LiteralPath $RequestsPath -Raw -Encoding UTF8
$requests = ConvertFrom-Json -InputObject $requestsJson
$requests = @($requests)
$orders = [Collections.Generic.List[object]]::new()
$services = [Collections.Generic.List[object]]::new()
$refs = [Collections.Generic.HashSet[string]]::new()
$planned = ([char]0xC0).ToString() + ' planifier'
$closed = 'Cl' + [char]0xF4 + 'tur' + [char]0xE9 + 'e'
$finished = 'Termin' + [char]0xE9 + 'e'
$stamp = $AsOf.ToString('yyyy-MM-dd') + 'T12:00:00'
$note = "DONNEES FICTIVES - scenario genere au $($AsOf.ToString('yyyy-MM-dd')); aucune photo."
function Day([datetime]$date, [int]$offset) { return $date.AddDays($offset).ToString('yyyy-MM-dd') }
function Timestamp([datetime]$date, [int]$offset) { return (Day $date $offset) + 'T00:00:00' }
function Coordinates($value) {
    if ($value -and $value -match '^\s*(?:GPS\s*:\s*)?(-?\d+(?:\.\d+)?)\s*[,;]\s*(-?\d+(?:\.\d+)?)\s*$') {
        $lat = [double]::Parse($Matches[1], [Globalization.CultureInfo]::InvariantCulture)
        $lon = [double]::Parse($Matches[2], [Globalization.CultureInfo]::InvariantCulture)
        if ([math]::Abs($lat) -le 90 -and [math]::Abs($lon) -le 180) { return "$($Matches[1]),$($Matches[2])" }
    }
    return $null
}
foreach ($request in ($requests | Sort-Object RequestReference)) {
    if ($request.RequestReference -notmatch '^DEM-\d{6}$' -or -not $refs.Add($request.RequestReference)) { throw 'Reference demande invalide ou dupliquee.' }
    # Ne pas inventer une date ou une commune manquante.
    if (-not $request.RequestDate -or -not $request.ReportedCity -or -not $request.RequestReason) { continue }
    $start = [datetime]::ParseExact($request.RequestDate, 'yyyy-MM-dd', [Globalization.CultureInfo]::InvariantCulture)
    $age = [int]($AsOf.Date - $start.Date).TotalDays
    if ($age -lt 0) { continue }
    $number = [int]$request.RequestReference.Substring(4)
    # 10% sans travaux ; les autres scenarios restent reproductibles par reference.
    $scenario = $number % 10
    if ($scenario -eq 0) { continue }
    $finishOffset = 12 + ($number % 24)
    $noExcavation = $request.DictAtuIndicator -eq 'Sans terrassement'
    $stage = if ($scenario -eq 1 -or $age -lt 4) { 0 } elseif ($scenario -eq 2 -or $age -lt 6) { 1 } elseif ($scenario -le 4 -or $age -lt $finishOffset) { 2 } else { 3 }
    $waiting = $scenario -eq 4 -and $stage -eq 2
    $orderStatus = if ($stage -eq 3) { $closed } elseif ($stage -eq 0) { $planned } elseif ($waiting) { 'En attente' } else { 'En cours' }
    $serviceStatus = if ($stage -eq 3) { $finished } else { $orderStatus }
    $request.RequestStatus = if ($stage -eq 3) { $closed } elseif ($waiting) { 'En attente' } else { 'En cours' }
    $request.UpdatedAt = $stamp
    $request.RequestComment = (@($request.RequestComment, $note) | Where-Object { $_ }) -join "`n"
    $orderCount = if ($number % 13 -eq 0) { 2 } else { 1 }
    for ($i = 0; $i -lt $orderCount; $i++) {
        $OrderSequence++
        $orderRef = 'INT-{0:D6}' -f $OrderSequence
        $order = [ordered]@{
            WorkOrderReferenceEnrobEau = $orderRef
            WorkOrderReferenceSaur = 'DEMO-SAUR-{0:D6}' -f $OrderSequence
            RequestReference = $request.RequestReference
            IssuedAt = $null; ReceivedAt = $null; ClosedAt = $null
            SaurComment = $note
            CityWorksComment = $null; CityInformedAt = $null
            CustomerWorksComment = $null; CustomerInformedAt = $null
            WorkOrderStatus = $orderStatus; CreatedAt = $stamp; UpdatedAt = $stamp
        }
        if ($stage -gt 0) {
            if ($request.DictAtuIndicator -eq 'DICT' -or $request.DictAtuIndicator -like 'ATU*') {
                $order.IssuedAt = Timestamp $start 1
                $order.ReceivedAt = Timestamp $start 2
            }
            $order.CityWorksComment = 'Information commune simulee pour le jeu exemple.'
            $order.CityInformedAt = Timestamp $start 2
            $order.CustomerWorksComment = 'Information abonnes simulee pour le jeu exemple.'
            $order.CustomerInformedAt = Timestamp $start 2
        }
        if ($waiting) { $order.SaurComment += ' Attente simulee de disponibilite pour la refection definitive.' }
        if ($stage -eq 3) { $order.ClosedAt = Timestamp $start $finishOffset }
        $orders.Add([pscustomobject]$order)
        $serviceCount = if ($number % 7 -eq 0) { 2 } else { 1 }
        for ($j = 0; $j -lt $serviceCount; $j++) {
            $ServiceSequence++
            $service = [ordered]@{
                ServiceReference = 'PR-{0:D6}' -f $ServiceSequence
                WorkOrderReferenceEnrobEau = $orderRef
                ServiceCode = 'DEMO-REFECTION'
                WorkAddress = $request.ReportedAdress; WorkCity = $request.ReportedCity
                WorkCoordinates = Coordinates $request.LocationLandmark
                WorkReason = $request.RequestReason
                SurfaceRepairType = $null; RoadType = $null
                Comment = "$note Lot $($i + 1), zone $($j + 1)."
                ExcavationDate = $null; BackfillDate = $null; Concrete2CmDate = $null
                HasConcrete2Cm = $null; TemporaryRepairDate = $null; HasTemporaryRepair = $null
                FinalRepairDate = $null; ServiceStatus = $serviceStatus
                CreatedAt = $stamp; UpdatedAt = $stamp
            }
            if ($request.ReportedSurfaceType) { $service.SurfaceRepairType = $request.ReportedSurfaceType -join ', ' }
            if ($request.ReportedRoadType) { $service.RoadType = $request.ReportedRoadType -join ', ' }
            if ($noExcavation) { $service.ServiceCode = 'DEMO-SANS-TERRASSEMENT' }
            if ($stage -ge 1 -and -not $noExcavation) { $service.ExcavationDate = Day $start 4 }
            if ($stage -ge 2 -and -not $noExcavation) {
                $service.BackfillDate = Day $start 6
                $service.Concrete2CmDate = $service.BackfillDate; $service.HasConcrete2Cm = $true
                $service.TemporaryRepairDate = $service.BackfillDate; $service.HasTemporaryRepair = $true
            }
            if ($stage -eq 3) { $service.FinalRepairDate = Day $start $finishOffset }
            $services.Add([pscustomobject]$service)
        }
    }
}
if ($OrderSequence -gt 999999 -or $ServiceSequence -gt 999999) { throw 'Capacite des references depassee.' }
$requestSequence = ($requests | ForEach-Object { [int]$_.RequestReference.Substring(4) } | Measure-Object -Maximum).Maximum
$summary = [ordered]@{
    as_of = $AsOf.ToString('yyyy-MM-dd'); source_sha256 = (Get-FileHash -LiteralPath $RequestsPath -Algorithm SHA256).Hash
    demandes = $requests.Count; interventions = $orders.Count; prestations = $services.Count; photos = 0
    demandes_sans_intervention = $requests.Count - @($orders | Select-Object -ExpandProperty RequestReference -Unique).Count
    statuts_interventions = @($orders | Group-Object WorkOrderStatus | Select-Object Name, Count)
    statuts_prestations = @($services | Group-Object ServiceStatus | Select-Object Name, Count)
}
$null = New-Item -ItemType Directory -Path $OutputDirectory
$utf8 = [Text.UTF8Encoding]::new($false)
foreach ($item in @(
    @{Name='demandes'; Data=$requests}, @{Name='interventions'; Data=$orders.ToArray()},
    @{Name='prestations'; Data=$services.ToArray()},
    @{Name='sequences'; Data=@{demandes=[int]$requestSequence; interventions=$OrderSequence; prestations=$ServiceSequence}},
    @{Name='generation'; Data=$summary}
)) {
    [IO.File]::WriteAllText((Join-Path ([IO.Path]::GetFullPath($OutputDirectory)) ($item.Name + '.json')), (ConvertTo-Json -InputObject $item.Data -Depth 10), $utf8)
}
$summary | ConvertTo-Json -Depth 5
