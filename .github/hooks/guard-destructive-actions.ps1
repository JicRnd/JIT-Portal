$inputText = [Console]::In.ReadToEnd()

try {
    $payload = $inputText | ConvertFrom-Json -Depth 20
    $toolInput = if ($null -ne $payload.toolInput) {
        $payload.toolInput | ConvertTo-Json -Depth 20 -Compress
    } else {
        $inputText
    }
} catch {
    $toolInput = $inputText
}

$destructivePattern = '(?i)(git\s+(reset|restore|checkout|clean|stash\s+(pop|drop|clear))\b|--force\b|remove-item\b|\bdel(?:ete)?\b|move-item\b|copy-item\b|out-file\b|set-content\b|add-content\b|overwrite|re-baseline|regenerat(?:e|ion))'

if ($toolInput -match $destructivePattern) {
    [Console]::WriteLine((@{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'ask'
            permissionDecisionReason = 'Potentially destructive repository or workspace operation detected. Confirm the exact command and files before proceeding.'
        }
    } | ConvertTo-Json -Compress))
} else {
    [Console]::WriteLine('{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow"}}')
}
