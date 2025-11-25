# Comprehensive Parameter Sweep for Court Scheduling System
# Runs multiple scenarios × multiple policies × multiple seeds

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "COMPREHENSIVE PARAMETER SWEEP" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

$ErrorActionPreference = "Stop"
$results = @()

# Configuration matrix
$scenarios = @(
    @{
        name = "baseline_10k_2year"
        cases = 10000
        seed = 42
        days = 500
        description = "2-year simulation: 10k cases, ~500 working days (HACKATHON REQUIREMENT)"
    },
    @{
        name = "baseline_10k"
        cases = 10000
        seed = 42
        days = 200
        description = "Baseline: 10k cases, balanced distribution"
    },
    @{
        name = "baseline_10k_seed2"
        cases = 10000
        seed = 123
        days = 200
        description = "Baseline replica with different seed"
    },
    @{
        name = "baseline_10k_seed3"
        cases = 10000
        seed = 456
        days = 200
        description = "Baseline replica with different seed"
    },
    @{
        name = "small_5k"
        cases = 5000
        seed = 42
        days = 200
        description = "Small court: 5k cases"
    },
    @{
        name = "large_15k"
        cases = 15000
        seed = 42
        days = 200
        description = "Large backlog: 15k cases"
    },
    @{
        name = "xlarge_20k"
        cases = 20000
        seed = 42
        days = 150
        description = "Extra large: 20k cases, capacity stress"
    }
)

$policies = @("fifo", "age", "readiness")

Write-Host "Configuration:" -ForegroundColor Yellow
Write-Host "  Scenarios: $($scenarios.Count)" -ForegroundColor White
Write-Host "  Policies: $($policies.Count)" -ForegroundColor White
Write-Host "  Total simulations: $($scenarios.Count * $policies.Count)" -ForegroundColor White
Write-Host ""

$totalRuns = $scenarios.Count * $policies.Count
$currentRun = 0

# Create results directory
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$resultsDir = "data\comprehensive_sweep_$timestamp"
New-Item -ItemType Directory -Path $resultsDir -Force | Out-Null

# Generate datasets
Write-Host "Step 1: Generating datasets..." -ForegroundColor Cyan
$datasetDir = "$resultsDir\datasets"
New-Item -ItemType Directory -Path $datasetDir -Force | Out-Null

foreach ($scenario in $scenarios) {
    Write-Host "  Generating $($scenario.name)..." -NoNewline
    $datasetPath = "$datasetDir\$($scenario.name)_cases.csv"
    
    & uv run python main.py generate --cases $scenario.cases --seed $scenario.seed --output $datasetPath > $null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAILED" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Step 2: Running simulations..." -ForegroundColor Cyan

foreach ($scenario in $scenarios) {
    $datasetPath = "$datasetDir\$($scenario.name)_cases.csv"
    
    foreach ($policy in $policies) {
        $currentRun++
        $runName = "$($scenario.name)_$policy"
        $logDir = "$resultsDir\$runName"
        
        $progress = [math]::Round(($currentRun / $totalRuns) * 100, 1)
        Write-Host "[$currentRun/$totalRuns - $progress%] " -NoNewline -ForegroundColor Yellow
        Write-Host "$runName" -NoNewline -ForegroundColor White
        Write-Host " ($($scenario.days) days)..." -NoNewline -ForegroundColor Gray
        
        $startTime = Get-Date
        
        & uv run python main.py simulate `
            --days $scenario.days `
            --cases $datasetPath `
            --policy $policy `
            --log-dir $logDir `
            --seed $scenario.seed > $null
        
        $endTime = Get-Date
        $duration = ($endTime - $startTime).TotalSeconds
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host " OK " -ForegroundColor Green -NoNewline
            Write-Host "($([math]::Round($duration, 1))s)" -ForegroundColor Gray
            
            # Parse report
            $reportPath = "$logDir\report.txt"
            if (Test-Path $reportPath) {
                $reportContent = Get-Content $reportPath -Raw
                
                # Extract metrics using regex
                if ($reportContent -match 'Cases disposed: (\d+)') {
                    $disposed = [int]$matches[1]
                }
                if ($reportContent -match 'Disposal rate: ([\d.]+)%') {
                    $disposalRate = [double]$matches[1]
                }
                if ($reportContent -match 'Gini coefficient: ([\d.]+)') {
                    $gini = [double]$matches[1]
                }
                if ($reportContent -match 'Court utilization: ([\d.]+)%') {
                    $utilization = [double]$matches[1]
                }
                if ($reportContent -match 'Total hearings: ([\d,]+)') {
                    $hearings = $matches[1] -replace ',', ''
                }
                
                $results += [PSCustomObject]@{
                    Scenario = $scenario.name
                    Policy = $policy
                    Cases = $scenario.cases
                    Days = $scenario.days
                    Seed = $scenario.seed
                    Disposed = $disposed
                    DisposalRate = $disposalRate
                    Gini = $gini
                    Utilization = $utilization
                    Hearings = $hearings
                    Duration = [math]::Round($duration, 1)
                }
            }
        } else {
            Write-Host " FAILED" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "Step 3: Generating summary..." -ForegroundColor Cyan

# Export results to CSV
$resultsCSV = "$resultsDir\summary_results.csv"
$results | Export-Csv -Path $resultsCSV -NoTypeInformation

Write-Host "  Results saved to: $resultsCSV" -ForegroundColor Green

# Generate markdown summary
$summaryMD = "$resultsDir\SUMMARY.md"
$markdown = @"
# Comprehensive Simulation Results

**Generated**: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
**Total Simulations**: $totalRuns
**Scenarios**: $($scenarios.Count)
**Policies**: $($policies.Count)

## Results Matrix

### Disposal Rate (%)

| Scenario | FIFO | Age | Readiness | Best |
|----------|------|-----|-----------|------|
"@

foreach ($scenario in $scenarios) {
    $fifo = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "fifo" }).DisposalRate
    $age = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "age" }).DisposalRate
    $readiness = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "readiness" }).DisposalRate
    
    $best = [math]::Max($fifo, [math]::Max($age, $readiness))
    $bestPolicy = if ($fifo -eq $best) { "FIFO" } elseif ($age -eq $best) { "Age" } else { "**Readiness**" }
    
    $markdown += "`n| $($scenario.name) | $fifo | $age | **$readiness** | $bestPolicy |"
}

$markdown += @"


### Gini Coefficient (Fairness)

| Scenario | FIFO | Age | Readiness | Best |
|----------|------|-----|-----------|------|
"@

foreach ($scenario in $scenarios) {
    $fifo = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "fifo" }).Gini
    $age = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "age" }).Gini
    $readiness = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "readiness" }).Gini
    
    $best = [math]::Min($fifo, [math]::Min($age, $readiness))
    $bestPolicy = if ($fifo -eq $best) { "FIFO" } elseif ($age -eq $best) { "Age" } else { "**Readiness**" }
    
    $markdown += "`n| $($scenario.name) | $fifo | $age | **$readiness** | $bestPolicy |"
}

$markdown += @"


### Utilization (%)

| Scenario | FIFO | Age | Readiness | Best |
|----------|------|-----|-----------|------|
"@

foreach ($scenario in $scenarios) {
    $fifo = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "fifo" }).Utilization
    $age = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "age" }).Utilization
    $readiness = ($results | Where-Object { $_.Scenario -eq $scenario.name -and $_.Policy -eq "readiness" }).Utilization
    
    $best = [math]::Max($fifo, [math]::Max($age, $readiness))
    $bestPolicy = if ($fifo -eq $best) { "FIFO" } elseif ($age -eq $best) { "Age" } else { "**Readiness**" }
    
    $markdown += "`n| $($scenario.name) | $fifo | $age | **$readiness** | $bestPolicy |"
}

$markdown += @"


## Statistical Summary

### Our Algorithm (Readiness) Performance

"@

$readinessResults = $results | Where-Object { $_.Policy -eq "readiness" }
$avgDisposal = ($readinessResults.DisposalRate | Measure-Object -Average).Average
$stdDisposal = [math]::Sqrt((($readinessResults.DisposalRate | ForEach-Object { [math]::Pow($_ - $avgDisposal, 2) }) | Measure-Object -Average).Average)
$minDisposal = ($readinessResults.DisposalRate | Measure-Object -Minimum).Minimum
$maxDisposal = ($readinessResults.DisposalRate | Measure-Object -Maximum).Maximum

$markdown += @"

- **Mean Disposal Rate**: $([math]::Round($avgDisposal, 1))%
- **Std Dev**: $([math]::Round($stdDisposal, 2))%
- **Min**: $minDisposal%
- **Max**: $maxDisposal%
- **Coefficient of Variation**: $([math]::Round(($stdDisposal / $avgDisposal) * 100, 1))%

### Performance Comparison (Average across all scenarios)

| Metric | FIFO | Age | Readiness | Advantage |
|--------|------|-----|-----------|-----------|
"@

$avgDisposalFIFO = ($results | Where-Object { $_.Policy -eq "fifo" } | Measure-Object -Property DisposalRate -Average).Average
$avgDisposalAge = ($results | Where-Object { $_.Policy -eq "age" } | Measure-Object -Property DisposalRate -Average).Average
$avgDisposalReadiness = ($results | Where-Object { $_.Policy -eq "readiness" } | Measure-Object -Property DisposalRate -Average).Average
$advDisposal = $avgDisposalReadiness - [math]::Max($avgDisposalFIFO, $avgDisposalAge)

$avgGiniFIFO = ($results | Where-Object { $_.Policy -eq "fifo" } | Measure-Object -Property Gini -Average).Average
$avgGiniAge = ($results | Where-Object { $_.Policy -eq "age" } | Measure-Object -Property Gini -Average).Average
$avgGiniReadiness = ($results | Where-Object { $_.Policy -eq "readiness" } | Measure-Object -Property Gini -Average).Average
$advGini = [math]::Min($avgGiniFIFO, $avgGiniAge) - $avgGiniReadiness

$markdown += @"

| **Disposal Rate** | $([math]::Round($avgDisposalFIFO, 1))% | $([math]::Round($avgDisposalAge, 1))% | **$([math]::Round($avgDisposalReadiness, 1))%** | +$([math]::Round($advDisposal, 1))% |
| **Gini** | $([math]::Round($avgGiniFIFO, 3)) | $([math]::Round($avgGiniAge, 3)) | **$([math]::Round($avgGiniReadiness, 3))** | -$([math]::Round($advGini, 3)) (better) |

## Files

- Raw data: `summary_results.csv`
- Individual reports: `<scenario>_<policy>/report.txt`
- Datasets: `datasets/<scenario>_cases.csv`

---
Generated by comprehensive_sweep.ps1
"@

$markdown | Out-File -FilePath $summaryMD -Encoding UTF8

Write-Host "  Summary saved to: $summaryMD" -ForegroundColor Green
Write-Host ""

Write-Host "================================================" -ForegroundColor Cyan
Write-Host "SWEEP COMPLETE!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "Results directory: $resultsDir" -ForegroundColor Yellow
Write-Host "Total duration: $([math]::Round(($results | Measure-Object -Property Duration -Sum).Sum / 60, 1)) minutes" -ForegroundColor White
Write-Host ""
