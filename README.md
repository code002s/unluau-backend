# unluau-backend

**Декомпилятор Luau / Roblox-байткода (v3–v14) с автоматической «чисткой» результата.**
Luau / Roblox bytecode decompiler (v3–v14) that returns clean, readable Luau.

```
Roblox executor ──► https://kynx-site.pages.dev/decompile      (KYNX site, Cloudflare Pages)
                              │  JSON {"script":"<base64>"}
                              ▼
                      KYNX upstream Worker ──► unluau-backend (этот сервис, Render/Docker)
                                                 1. descramble  (Roblox op*227)
                                                 2. unluac-rs   (CFG → структура → код)
                                                 3. cleanup     (имена, ранние return, сервисы)
                              ◄── чистый Luau ◄──┘
```

## Структура репозитория

```
/              бэкенд декомпилятора (этот сервис, собирается Render из корневого Dockerfile)
/webs          сайт и воркеры KYNX: kynx-full/kynx-site-v4 (kynx-site.pages.dev), upstream-worker, kynx-scripts, clients, docs
```

Публичный адрес сайта — `https://kynx-site.pages.dev/decompile`. Папка `webs/` в Docker-образ не попадает
(`.dockerignore`), но любой push пересобирает сервис на Render.

## Публичный API — `kynx-site.pages.dev/decompile`

Именно этот адрес используют клиенты. Сам бэкенд наружу не публикуется.

```bash
curl -sS -X POST https://kynx-site.pages.dev/decompile \
     -H "Content-Type: application/json" \
     -d "{\"script\":\"$(base64 -w0 script.luauc)\"}"
```

| | |
|---|---|
| Запрос | `POST`, JSON `{"script": "<base64 байткода>"}`, до 4 МБ |
| Ответ `200` | исходник Luau, `text/plain` |
| Ошибки | `400` плохой ввод · `413` слишком большой · `422` не декомпилировано · `502` бэкенд недоступен |

Остальные маршруты сайта (`/luau/decompile`, `/konstant/decompile`, `/api/decompile`, …) описаны в
`docs/API.md` репозитория KYNX; все они приходят в этот же бэкенд.

## Что делает «чистка» (cleanup)

После декомпиляции код разбирается собственным парсером Luau и приводится к виду из **Top Luau Style Guide**:

| Правило | До → после |
|---|---|
| Осмысленные имена | `result`, `Parent2`, `value2`, `a` → `Players`, `screenGui`, `playerCount`, `data` |
| Ранние `return` / `continue` вместо вложенности | `if a then if b then … end end` → `if not a then return end` … |
| Без `else` после `return` | `if x then return 1 else return 2 end` → `if x then return 1 end return 2` |
| `else if` → `elseif` | плоская цепочка условий |
| Кэш сервисов | повторные `game:GetService("X")` → один `local X` в начале файла |
| Не используемый ключ цикла | `for k, v in …` → `for _, v in …` |
| Единый формат | 4 пробела, `obj.name` вместо `obj["name"]`, пустые строки между блоками |

Пример (реальный вывод):

<table><tr><th>декомпилятор</th><th>после cleanup</th></tr><tr><td>

```lua
local result = game:GetService("Players")
local result2 = game:GetService("ReplicatedStorage")
local result3 = result.LocalPlayer
local Parent = result3:WaitForChild("PlayerGui")
local Parent2 = Instance.new("ScreenGui")
Parent2.Name = "StaffStatsUI"
Parent2.Parent = Parent
local remote = result2:WaitForChild("StaffServerStatsRemote")
remote.OnClientEvent:Connect(function(a)
    if typeof(a) == "table" then
        if a.authorized == true then
            local value = a.serverFPS
            local value2 = tonumber(a.playerCount) or 0
            print(value, value2)
        end
    end
end)
```

</td><td>

```lua
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local localPlayer = Players.LocalPlayer
local playerGui = localPlayer:WaitForChild("PlayerGui")
local screenGui = Instance.new("ScreenGui")
screenGui.Name = "StaffStatsUI"
screenGui.Parent = playerGui
local remote = ReplicatedStorage:WaitForChild("StaffServerStatsRemote")

remote.OnClientEvent:Connect(function(data)
    if typeof(data) ~= "table" then
        return
    end

    if data.authorized ~= true then
        return
    end

    local serverFps = data.serverFPS
    local playerCount = tonumber(data.playerCount) or 0
    print(serverFps, playerCount)
end)
```

</td></tr></table>

### Гарантии

- **Никогда не хуже исходного.** Если встретился синтаксис, которого парсер не знает (типы, `goto`, экспериментальный
  `if local`), или любая проверка не прошла — отдаётся исходный вывод декомпилятора без изменений.
- **Переименование безопасно.** Новое имя применяется, только если оно не перехватывает и не затеняет другую
  переменную; после всех шагов имена перепроверяются заново. Осмысленные имена из debug-информации не трогаются.
- **Поведение не меняется.** Все преобразования семантически точные. Не делаются «красивые, но опасные» замены:
  `x == true` → `x` (меняет смысл для не-boolean) и `not (a < b)` → `a >= b` (неверно для NaN).
- **`--!strict` не добавляется по умолчанию**: у декомпилированного кода нет аннотаций типов, и strict-режим даст
  сотни предупреждений. Включается через `LUAU_STRICT_HEADER=1`.
- Комментарии, стоящие перед операторами, сохраняются.

Чтобы получить «сырой» результат декомпилятора (для отладки), добавьте `?raw=1`:
`LUAU_BACKEND_URL = https://<backend>/decompile?raw=1`.
Ответ бэкенда содержит заголовок `X-Cleanup: cleaned | skipped | off` (причина пропуска — в `X-Cleanup-Note`).

## API бэкенда (его вызывает Worker, не клиенты)

`POST /decompile` (или `POST /`) — тело: **сырой байткод** (`application/octet-stream`).

| Статус | Значение |
|---|---|
| `200 text/plain` | исходник Luau |
| `400` | пустое тело |
| `401` | нужен `Authorization: Bearer <BACKEND_TOKEN>` (только если токен задан) |
| `413` | тело больше 16 МБ |
| `422` | это не поддерживаемый байткод, или декомпилятор отказал (`{"error": "..."}`) |
| `500` / `503` / `504` | внутренняя ошибка / занято / таймаут |

`GET /health` → `{"ok": true, "engine": "unluac-rs", "luauVersions": "3-14"}`

| Переменная | По умолчанию | Назначение |
|---|---|---|
| `PORT` | `8080` | порт |
| `DECOMPILE_TIMEOUT` | `25` | секунд на одну декомпиляцию (Worker сдаётся через 30 с) |
| `MAX_CONCURRENT` | `2` | одновременных декомпиляций |
| `QUEUE_TIMEOUT` | `20` | сколько ждать свободный слот, затем `503` |
| `LUAU_STRICT_HEADER` | выкл. | `1` — добавлять `--!strict` |
| `BACKEND_TOKEN` | — | **не задавайте**: Worker не отправляет `Authorization` |
| `UNLUAC_BIN` | `/usr/local/bin/unluac-cli` | путь к CLI |

## Деплой на Render

Этот репозиторий заменяет прежний .NET-бэкенд (`Api.csproj`, `Program.cs`): удалите эти два файла и положите
содержимое проекта в корень репозитория.

1. Render → **New → Web Service** → репозиторий → Environment: **Docker** (берётся `render.yaml`).
2. Первая сборка компилирует Rust (≈ 5–10 минут).
3. В upstream Worker (`kynx-full/upstream-worker`):
   ```bash
   npx wrangler secret put LUAU_BACKEND_URL
   # вставьте: https://<адрес вашего бэкенда>/decompile
   ```
4. Проверка: `GET /health` Worker'а показывает `"luauBackend": true`, затем запрос на
   `https://kynx-site.pages.dev/decompile` (см. выше).

Бесплатный план Render «засыпает»: первый запрос после простоя может занять > 30 с (таймаут Worker'а) — сначала
откройте `/health` или используйте платный инстанс.

## Локальный запуск и тесты

```bash
cd unluac-rs && cargo build --release -p unluac-cli        # нужен Rust ≥ 1.94
cd .. && UNLUAC_BIN=$PWD/unluac-rs/target/release/unluac-cli PORT=8080 python3 server.py
curl --data-binary @test/fixtures/v13_basic_O1_g1.luauc localhost:8080/decompile

python3 -m unittest discover -s test -t .                   # Rust и сеть не нужны
LUAU_DIR=/path/to/luau python3 -m unittest discover -s test -t .   # + проверка настоящим компилятором Luau
```

Тесты: дескремблер (на фикстурах), cleanup (имена, поток управления, кэш сервисов, откат на исходник),
HTTP-сервер (на поддельном CLI) и — если найден `luau` — **сравнение вывода скриптов до и после чистки** и
проверка результата компилятором `luau-compile`.

Проверено при разработке (Luau 0.742): очистка прогнана по 57 реальным conformance-скриптам Luau — 39 обработаны
и все скомпилированы, остальные корректно пропущены (типизированный синтаксис); из запускаемых без окружения тестов
20 дали идентичный вывод, остальные отличаются только адресами указателей, таймингами и номерами строк в
текстах ошибок. Сам `unluac-cli` в этой среде не собирался (нет Rust), поэтому связка «CLI → cleanup» проверена на
его типичном выводе, а не на живом бинарнике — после первой сборки прогоните `test/fixtures/` вручную.

## Что изменено в unluac-rs

`unluac-rs/` — копия upstream (MIT), у которой Luau-парсер расширен с v7 до v14:

| Версия | Поддержка |
|---|---|
| v8 | 64-битные целочисленные константы |
| v9 | изменения только в рантайме |
| v10 | константы-«формы классов» (разбираются; опкоды классов отвергаются) |
| v11 | `CALLFB`, таблица feedback-слотов |
| v12 | префикс размера у каждой функции, inline cost |
| v13 | векторные константы двойной точности |
| v14 | `FASTPCALL` |

Файлы: `src/parser/dialect/luau/{raw,parser}.rs`, `src/parser/reader.rs`, `src/transformer/dialect/luau/lower*`.

## Структура

```
server.py            HTTP-сервер (только маршруты и ответы)
unluau/descramble.py Roblox-кодировка опкодов (op*227 mod 256)
unluau/decompiler.py вызов unluac-cli, повтор с дескремблом, статусы ошибок
unluau/cleanup.py    конвейер чистки и откат на исходник
unluau/syntax.py     лексер, дерево, парсер Luau
unluau/scopes.py     привязка имён к объявлениям + перепроверка
unluau/naming.py     осмысленные имена
unluau/services.py   кэш сервисов
unluau/flow.py       ранние return / continue
unluau/printer.py    форматирование
test/                тесты и фикстуры
```

## Ограничения

- Редкие большие скрипты не декомпилируются (несовпадение аргументов `FASTCALL`, редкие паники upstream) —
  возвращается `422/500` с причиной.
- Опкоды экспериментальных Luau-классов (`NEWCLASS`, `NEWCLASSMEMBER`, `CMPPROTO`) не поддерживаются.
- Результат — реконструкция: исходные имена без debug-информации, комментарии и типы восстановить нельзя;
  имена подбираются эвристикой. Всегда проверяйте код в Roblox Studio.
- Cleanup пропускает скрипты с типизированным синтаксисом (декомпилятор его не выдаёт).

## Лицензии

- [unluac-rs](https://github.com/x3zvawq/unluac-rs) — MIT (`unluac-rs/LICENSE.txt`).
- Формат байткода — по исходникам [Luau](https://github.com/luau-lang/luau) (MIT).
