param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $HarnoveArguments
)

$runtime = Join-Path $PSScriptRoot 'runtime\harnove.py'
if (-not (Test-Path -LiteralPath $runtime)) {
    throw "Harnove runtime not found: $runtime. Run the plugin init.py first."
}

$pythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($pythonCommand) {
    & $pythonCommand.Source $runtime @HarnoveArguments
    exit $LASTEXITCODE
}

$python3Command = Get-Command python3 -ErrorAction SilentlyContinue
if ($python3Command) {
    & $python3Command.Source $runtime @HarnoveArguments
    exit $LASTEXITCODE
}

$pyCommand = Get-Command py -ErrorAction SilentlyContinue
if ($pyCommand) {
    & $pyCommand.Source -3 $runtime @HarnoveArguments
    exit $LASTEXITCODE
}

throw 'Python 3.10+ was not found. Install Python or invoke runtime/harnove.py with an explicit Python executable.'

