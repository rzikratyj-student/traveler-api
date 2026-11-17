# TravelerAPI

REST API для спільного планування подорожей (лабораторна робота 1, «Розподілені сховища даних», СумДУ).
Python + FastAPI + PostgreSQL. Конкурентний доступ розв'язано через оптимістичне блокування (`version`)
у планах і локаціях та коротке блокування рядка плану під час змін локацій.

- Пояснення рішень для захисту: [`docs/defense-guide.md`](docs/defense-guide.md)
- Що і як перевірено: [`docs/verification.md`](docs/verification.md)
- Контракт API: [`docs/travel_api_swagger.json`](docs/travel_api_swagger.json) (сервер також віддає його на `/openapi.json` і `/docs`)

## Структура

| Шлях | Що там |
|---|---|
| `app/main.py` | Підключення до БД, FastAPI-застосунок, `/health`, обробники помилок, OpenAPI |
| `app/plans.py` | Моделі та маршрути `/api/travel-plans` |
| `app/locations.py` | Моделі та маршрути локацій, блокування плану, `visit_order` |
| `docs/schema.sql` | Схема БД для **нової** бази |
| `migrations/001_location_version.sql` | Оновлення **старої** бази (без `locations.version`) |
| `docs/schema.mermeid`, `docs/schema.png` | ER-діаграма (PNG ще не показує `locations.version`, див. verification.md) |
| `scripts/update_openapi.py` | Вносить зміни в збережений OpenAPI |
| `scripts/load_test.py` | Навантажувальний тест |
| `tests/*.hurl` | HTTP-тести Hurl |
| `tests/test_concurrency.py` | Конкурентні тести (потрібен запущений сервер) |
| `tests/test_error_handling.py`, `tests/test_openapi_contract.py` | Тести без БД і сервера |

## Вимоги

- Python 3.12+ (перевірено на 3.13)
- PostgreSQL 13+ (потрібна вбудована `gen_random_uuid()`; перевірено на 16)
- [Hurl](https://hurl.dev) 6 або 7 (перевірено на 7.1.0)

## Запуск (Windows, PowerShell)

Команди виконуються з кореня репозиторію.

### 1. Віртуальне середовище і залежності

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Конфігурація

```powershell
Copy-Item .env.example .env
notepad .env
```

У `.env` вкажіть `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`. Файл `.env` є в `.gitignore`, не комітьте його.
Замість `.env` можна задати звичайні змінні середовища: `$env:DB_USER = "traveler"` тощо.

### 3a. Нова база даних

```powershell
psql -U postgres -c "CREATE ROLE traveler LOGIN PASSWORD 'change-me'"
psql -U postgres -c "CREATE DATABASE traveler OWNER traveler"
psql -U traveler -d traveler -v ON_ERROR_STOP=1 -f docs/schema.sql
```

`docs/schema.sql` уже містить `locations.version`, тому міграція для нової бази **не потрібна**.

### 3b. Оновлення наявної бази, створеної до коміту `ec1f488`

Якщо базу створено зі схеми базової реалізації (`8b68e36`), де в `locations` ще немає колонки `version`:

```powershell
psql -U traveler -d traveler -v ON_ERROR_STOP=1 -f migrations/001_location_version.sql
```

Наявні локації отримають `version = 1`. Міграція безпечна для повторного запуску: якщо колонка вже є,
PostgreSQL виведе `NOTICE ... already exists, skipping` і нічого не змінить.

### 4. Сервер

```powershell
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Перевірка: `curl.exe http://127.0.0.1:8000/health` → `{"status":"ok"}`. Документація API: http://127.0.0.1:8000/docs

## Тести

Сервер має працювати в іншому вікні PowerShell. Тести створюють власні дані й видаляють їх після себе,
але краще запускати їх на окремій тестовій базі.

```powershell
hurl --test .\tests\ --variables-file .\tests\variables.properties
```

```powershell
python -m pytest .\tests\ -v
```

- `hurl --test` з каталогом запускає всі `*.hurl` у ньому; у Hurl 6+ файли виконуються паралельно.
  Якщо стара версія Hurl не приймає каталог, передайте файли явно: `hurl --test (Get-ChildItem .\tests\*.hurl) --variables-file .\tests\variables.properties`.
- Адреса сервера для Hurl задана в `tests\variables.properties` (`host`), для pytest у змінній `TEST_API_URL`
  (типово `http://127.0.0.1:8000`).
- `test_error_handling.py` і `test_openapi_contract.py` не потребують ні БД, ні сервера.

### Навантажувальний тест

```powershell
python scripts\load_test.py --users 1000 --think 5 --duration 60 --processes 3
```

Опис методики й отримані цифри є в `docs/verification.md`. Результат залежить від машини,
тому вказуйте середовище разом із цифрами.

## Оновлення OpenAPI

Збережений контракт змінюється скриптом (він ідемпотентний, тобто повторний запуск дає той самий файл):

```powershell
python scripts\update_openapi.py
```

`tests/test_openapi_contract.py` перевіряє, що маршрути й поля запитів у контракті збігаються з кодом.

---

# Початкове завдання (з шаблону)

## System Overview



Build a Travel Planner REST API with PostgreSQL that handles concurrent editing of travel plans. Focus on ACID transactions and optimistic locking to prevent data conflicts.



### Core Entities

```

typescriptTravelPlan {
  id: UUID
  title: string
  description?: string
  start_date?: date
  end_date?: date
  budget?: decimal
  currency: string = 'USD'
  is_public: boolean = false
  version: integer = 1  // Optimistic locking
  created_at: timestamp
  updated_at: timestamp
}


Location {
  id: UUID
  travel_plan_id: UUID (FK)
  name: string
  address?: string
  latitude?: decimal
  longitude?: decimal
  visit_order: integer     // Auto-increment on insert
  arrival_date?: timestamp
  departure_date?: timestamp
  budget?: decimal
  notes?: text
  created_at: timestamp
}

```

### Critical API Endpoints

```

# Travel Plans
GET    /api/travel-plans                 # List with pagination
POST   /api/travel-plans                 # Create new plan
GET    /api/travel-plans/{id}            # Get plan with locations
PUT    /api/travel-plans/{id}            # Update with version check
DELETE /api/travel-plans/{id}            # Cascade delete

# Locations (always scoped to plan)
POST   /api/travel-plans/{id}/locations     # Add location (auto-order)
PUT    /api/locations/{id}                 # Update single location
DELETE /api/locations/{id}                 # Delete location

```

### Concurrency Patterns to Implement

* Optimistic Locking for travel\_plans using version field
* Auto-incrementing visit\_order for new locations
* Transaction Isolation for location updates
* Cascade Operations with proper foreign key constraints

### Database Design Requirements

* Use UUIDs for all primary keys
* Auto-assign visit\_order = MAX(visit\_order) + 1 for new locations
* Add proper indexes for query performance
* Implement check constraints for data validity
* Create triggers for auto-updating timestamp fields
* Foreign key constraints with CASCADE deletes

### Success Criteria
* Handle concurrent edits without lost updates
* Location addition works with auto-ordering
* Location updates are atomic and consistent
* All operations complete in <200ms
* Comprehensive test coverage with race condition scenarios



### Testing

```cmd

   hurl --test .\tests\ --variables-file .\tests\variables.properties
```

