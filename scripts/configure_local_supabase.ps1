$ErrorActionPreference = "Stop"

$root = (
    Resolve-Path (
        Join-Path $PSScriptRoot ".."
    )
).Path

$envPath = Join-Path $root ".env"
$examplePath = Join-Path $root ".env.example"

if (-not (Test-Path -LiteralPath $envPath)) {
    if (-not (
        Test-Path -LiteralPath $examplePath
    )) {
        throw ".env.example was not found."
    }

    Copy-Item `
        -LiteralPath $examplePath `
        -Destination $envPath

    Write-Host "Created .env from .env.example."
}

$tempOutput = Join-Path (
    [System.IO.Path]::GetTempPath()
) (
    "docuflow-supabase-status-" +
    [guid]::NewGuid().ToString("N") +
    ".txt"
)

$tempError = Join-Path (
    [System.IO.Path]::GetTempPath()
) (
    "docuflow-supabase-status-error-" +
    [guid]::NewGuid().ToString("N") +
    ".txt"
)

try {
    & npx supabase status -o env `
        1> $tempOutput `
        2> $tempError

    $statusExitCode = $LASTEXITCODE

    if ($statusExitCode -ne 0) {
        $errorText = (
            Get-Content `
                -LiteralPath $tempError `
                -Raw `
                -ErrorAction SilentlyContinue
        )

        throw (
            "Unable to read local Supabase status. " +
            "Confirm the DocuFlow Supabase project is running. " +
            $errorText
        )
    }

    $statusText = Get-Content `
        -LiteralPath $tempOutput `
        -Raw

    $values = @{}

    foreach (
        $match in [regex]::Matches(
            $statusText,
            '(?m)^\s*([A-Z0-9_]+)\s*=\s*"?([^"\r\n]+)"?\s*$'
        )
    ) {
        $values[
            $match.Groups[1].Value
        ] = $match.Groups[2].Value.Trim()
    }

    foreach ($required in @(
        "ANON_KEY",
        "SERVICE_ROLE_KEY"
    )) {
        if (-not $values.ContainsKey(
            $required
        )) {
            throw (
                "Supabase status did not return " +
                "$required."
            )
        }
    }

    $updates = [ordered]@{
        "SUPABASE_URL" = (
            "http://host.docker.internal:54321"
        )
        "SUPABASE_ANON_KEY" = (
            $values["ANON_KEY"]
        )
        "SUPABASE_SERVICE_ROLE_KEY" = (
            $values["SERVICE_ROLE_KEY"]
        )
        "SUPABASE_JWKS_URL" = (
            "http://host.docker.internal:54321/" +
            "auth/v1/.well-known/jwks.json"
        )
        "DATABASE_URL" = (
            "postgresql+asyncpg://postgres:postgres@" +
            "host.docker.internal:54322/postgres"
        )
    }

    if ($values.ContainsKey(
        "JWT_SECRET"
    )) {
        $updates[
            "SUPABASE_JWT_SECRET"
        ] = $values["JWT_SECRET"]
    }

    $content = [System.IO.File]::ReadAllText(
        $envPath
    )

    foreach (
        $entry in $updates.GetEnumerator()
    ) {
        $escapedName = [regex]::Escape(
            $entry.Key
        )

        $line = (
            $entry.Key +
            "=" +
            $entry.Value
        )

        if (
            $content -match (
                "(?m)^$escapedName=.*$"
            )
        ) {
            $content = [regex]::Replace(
                $content,
                "(?m)^$escapedName=.*$",
                [System.Text.RegularExpressions.MatchEvaluator]{
                    param($match)
                    return $line
                }
            )
        }
        else {
            if (
                -not $content.EndsWith(
                    [Environment]::NewLine
                )
            ) {
                $content += (
                    [Environment]::NewLine
                )
            }

            $content += (
                $line +
                [Environment]::NewLine
            )
        }
    }

    $utf8NoBom = New-Object `
        System.Text.UTF8Encoding($false)

    [System.IO.File]::WriteAllText(
        $envPath,
        $content,
        $utf8NoBom
    )

    Write-Host ""
    Write-Host (
        "Local Supabase credentials were loaded " +
        "into .env."
    )
    Write-Host (
        "Secret values were not printed."
    )
}
finally {
    Remove-Item `
        -LiteralPath $tempOutput `
        -Force `
        -ErrorAction SilentlyContinue

    Remove-Item `
        -LiteralPath $tempError `
        -Force `
        -ErrorAction SilentlyContinue
}
