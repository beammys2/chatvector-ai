$dates = @()
$date = [datetime]"2019-03-22"

while ($date -le [datetime]"2026-09-29") {

    $dates += $date.ToString("yyyy-MM-dd")

    # Random gap: 0 to 10 days
    $step = Get-Random -Minimum 1 -Maximum 5

    $date = $date.AddDays($step)

    # Avoid infinite loop when step = 0 too often
    if ($step -eq 0) {
        $date = $date.AddDays(1)
    }
}

$dates | Set-Content date.txt