# KYNX — команды для Windows PowerShell

Копируй по одной строке, **без комментариев** и без `1.` / `2.` в начале. `&&` в старом PowerShell не работает, используй отдельные строки.

## Деплой (все три части)
```powershell
cd kynx-full\upstream-worker
npm install
npx wrangler deploy
npx wrangler secret put UPSTREAM_TOKEN

cd ..\kynx-site-v4
npx wrangler pages secret put UPSTREAM_TOKEN --project-name=kynx-site
npx wrangler pages deploy . --project-name=kynx-site

cd ..\..\kynx-scripts
npm install
npx wrangler deploy
```
`UPSTREAM_TOKEN` должен быть одинаковым в upstream-воркере и в проекте Pages. KV id уже вписан в `kynx-scripts\wrangler.toml`; если KV уже есть, `kv namespace create` не нужен (`npx wrangler kv namespace list` покажет id).

## Тесты и локальный запуск
```powershell
cd kynx-full\upstream-worker
npm test

cd ..\..\kynx-scripts
npm test
npx wrangler dev
```

## Запросы к API (PowerShell, без curl и base64)
```powershell
$BASE = "https://kynx-site.pages.dev"
$F = "C:\path\script.luauc"
$b64 = [Convert]::ToBase64String([IO.File]::ReadAllBytes($F))

Invoke-RestMethod -Method Post -Uri "$BASE/konstant/decompile" -ContentType "text/plain" -InFile $F
Invoke-RestMethod -Method Post -Uri "$BASE/luau/decompile" -ContentType "text/plain" -Body $b64
Invoke-RestMethod -Method Post -Uri "$BASE/decompile" -ContentType "application/json" -Body (@{script=$b64} | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$BASE/x2125/decompile" -ContentType "application/json" -Body (@{script=$b64; options=@{}} | ConvertTo-Json)
Invoke-RestMethod -Method Post -Uri "$BASE/api/decompile" -ContentType "application/json" -Body (@{bytecodeBase64=$b64} | ConvertTo-Json)

Invoke-RestMethod https://kynx-upstream.kynxyy.workers.dev/health
```
Напрямую в upstream (с токеном):
```powershell
Invoke-RestMethod -Method Post -Uri "https://kynx-upstream.kynxyy.workers.dev/decompile" -Headers @{Authorization="Bearer ТВОЙ_ТОКЕН"} -ContentType "application/json" -Body (@{script=$b64} | ConvertTo-Json)
```

## Клиенты (запускать из корня kynx-all)
```powershell
node clients\example.mjs C:\path\script.luauc
```

## Проверка rbxmx на веб-вызовы
```powershell
Select-String -Path .\roblox\MainModule_KYNX_8_kynx_site.rbxmx -Pattern 'https?://[^"<>\s)]+' -AllMatches | ForEach-Object { $_.Matches.Value } | Group-Object | Sort-Object Count -Descending | Select-Object Count,Name
Select-String -Path .\roblox\MainModule_KYNX_8_kynx_site.rbxmx -Pattern 'HttpService|loadstring|HttpGet|RequestAsync|PostAsync' -AllMatches | ForEach-Object { $_.Matches.Value } | Group-Object | Select-Object Count,Name
```

## Bash (Linux/macOS/Git Bash)
```bash
BASE=https://kynx-site.pages.dev
curl -X POST $BASE/konstant/decompile -H "Content-Type: text/plain" --data-binary @script.luauc
curl -X POST $BASE/luau/decompile --data-binary "$(base64 -w0 script.luauc)"
bash clients/examples.sh script.luauc
```
