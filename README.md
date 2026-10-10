# unluau-backend

**Декомпилятор Luau / Roblox-байткода (версии 3–14) в виде HTTP-сервиса.**
Luau / Roblox bytecode decompiler (v3–v14) as an HTTP service — the `LUAU_BACKEND_URL` for the KYNX Worker.

```
Roblox executor ──► KYNX Worker (Cloudflare) ──► unluau-backend (Render, Docker)
   bytecode              /decompile                 unluac-rs + v8–v14 parser
                                                            │
                                      readable Luau source ◄┘
```

## Что это даёт / Features

- Читает **Luau bytecode v3–v14** (актуальный Roblox использует v13+).
- Принимает дампы из executor со «скрамбленными» опкодами (`op * 227 mod 256`) — определяет и раскодирует сам.
- Движок [unluac-rs](https://github.com/x3zvawq/unluac-rs) (MIT): построение CFG → анализ потока данных → структурирование → код. Корректные `for`/`while`, `and`/`or`, `continue`, строки, `local`-области.
- Имена локальных переменных восстанавливаются эвристикой, если в байткоде нет debug-имён.
- Векторные константы выводятся как `Vector3.new(...)`.
- Сложный поток управления, который нельзя структурировать, выводится как псевдокод вместо ошибки.

## Качество / Measured quality

Проверка: ~356 Luau-скриптов, скомпилированных настоящим компилятором Luau в v13, результат прогнан через парсер Luau (`luau-compile --only-parse`).

| | Unluau (прежний движок) | unluac-rs + этот патч |
|---|---|---|
| Файлов декомпилировано | 336 / 356 | **352 / 356** |
| Результат с валидным синтаксисом | ≈ 57 % | **351 / 352** |
| Версии 9, 11, 12, 13, 14 | — | **19 / 19 каждая** |

Это проверка **синтаксиса и структуры**, а не доказательство идентичного поведения: декомпилятор не может вернуть исходные имена, комментарии и типы, а код без debug-информации получает сгенерированные имена (`Parent2`, `value3`). Всегда проверяйте результат в Roblox Studio.

## API

`POST /decompile` (или `POST /`) — тело запроса: сырой байткод.

```bash
curl -i --data-binary "@script.luauc" \
     -H "Content-Type: application/octet-stream" \
     https://unluau-backend.onrender.com/decompile
```

| Статус | Значение |
|---|---|
| `200 text/plain` | исходник Luau |
| `400` | пустое тело |
| `401` | нужен `Authorization: Bearer <BACKEND_TOKEN>` (если токен задан) |
| `413` | тело больше 16 МБ |
| `422` | это не поддерживаемый байткод, или декомпилятор отказал (`{"error": "..."}`) |
| `500` / `504` | внутренняя ошибка / таймаут |

`GET /health` → `{"ok": true, "engine": "unluac-rs", "luauVersions": "3-14"}`

Переменные окружения: `PORT`, `BACKEND_TOKEN` (необязательно), `MAX_CONCURRENT` (по умолчанию 2), `DECOMPILE_TIMEOUT` (секунды, по умолчанию 60).

## Деплой / Deploy

1. Запушьте папку в GitHub-репозиторий, к которому подключён Docker-сервис на Render.
2. Первая сборка компилирует Rust (≈ 5–10 минут).
3. В Worker (`kynx-full/upstream-worker/wrangler.toml`):
   ```toml
   [vars]
   LUAU_BACKEND_URL = "https://unluau-backend.onrender.com/decompile"
   ```
   затем `npx wrangler deploy`. Проверка: `/health` Worker'а показывает `"luauBackend": true`.

Бесплатный план Render «засыпает»; первый запрос после простоя может быть дольше 30 секунд (таймаут Worker'а) — сначала откройте `/health`.

## Что изменено в unluac-rs / What the patch adds

`unluac-rs/` — копия upstream (MIT), у которой Luau-парсер расширен с v7 до v14:

| Версия | Поддержка |
|---|---|
| v8 | 64-битные целочисленные константы |
| v9 | изменения только в рантайме |
| v10 | константы-«формы классов» (разбираются; сами опкоды классов отвергаются) |
| v11 | `CALLFB`, таблица feedback-слотов |
| v12 | префикс размера у каждой функции, inline cost |
| v13 | векторные константы двойной точности |
| v14 | `FASTPCALL` |

Файлы: `src/parser/dialect/luau/{raw,parser}.rs`, `src/parser/reader.rs`, `src/transformer/dialect/luau/lower*`.
Декодирование Roblox-опкодов — `luau_descramble.py`.

## Локальный запуск / Local

```bash
cd unluac-rs && cargo build --release -p unluac-cli      # нужен Rust ≥ 1.94
UNLUAC_BIN=$PWD/target/release/unluac-cli PORT=8080 python3 ../server.py
curl --data-binary @../test/fixtures/v13_basic_O1_g1.luauc localhost:8080/decompile
```

Образцы для проверки: `test/fixtures/` (обычный v13, тот же файл в Roblox-кодировке, v14, Roblox-подобный скрипт).

## Известные ограничения / Limits

- Редкие большие скрипты не декомпилируются: несовпадение аргументов `FASTCALL` или редкие паники upstream — в этом случае возвращается `422/500` с причиной.
- Опкоды экспериментальных Luau-классов (`NEWCLASS`, `NEWCLASSMEMBER`, `CMPPROTO`) не поддерживаются.
- Без debug-имён локальные переменные получают сгенерированные имена.
- Результат — реконструкция, а не оригинальный код.

## Лицензии / Credits

- [unluac-rs](https://github.com/x3zvawq/unluac-rs) — MIT (`unluac-rs/LICENSE.txt`).
- Формат байткода — по исходникам [Luau](https://github.com/luau-lang/luau) (MIT).
