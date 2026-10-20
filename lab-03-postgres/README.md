# Lab 03: A Real Database

## Overview

| | |
|---|---|
| **Goal** | Move the Asset Register API from memory into PostgreSQL, keep all the tests passing against a separate test database, and prove the data survives restarts |
| **Runs on** | Windows, Python 3.14, FastAPI 0.149.0, SQLAlchemy 2.1, and PostgreSQL 18 in Docker |
| **Cost** | Free |
| **Time** | About three hours |

In Lab 02, every restart emptied the register, because the assets lived in a Python dictionary. This lab stores them in **PostgreSQL**, the same database as the original Flask app, running in a Docker container. The API's routes and rules are unchanged. Only where the data lives is different.

The same two assets, returned by the API after the app had been restarted and the database container replaced:

![Assets returned from PostgreSQL after restarts](images/assets-from-postgres.png)

---

## Architecture

```
Your computer
├── FastAPI app (in the virtual environment)
│        │  DATABASE_URL, read from .env
│        ▼
└── Docker: postgres:18-alpine  ── volume "pgdata" (survives restarts)
         ├── database "assets"        ← the app's real data
         └── database "assets_test"   ← emptied before every test
```

| What changed from Lab 02 | How |
|---|---|
| Where assets are stored | A PostgreSQL table, instead of a Python dictionary |
| Who chooses the `id` and `added` values | PostgreSQL, through a sequence and `DEFAULT now()` |
| How routes reach the data | A database session, given to each request by FastAPI's dependency injection |
| How the connection is configured | `DATABASE_URL` from an environment variable or `.env`, so no password is in the code |
| What the tests use | A separate `assets_test` database, swapped in without changing the app's code |

---

## Following along?

- I ran every command in **PowerShell** on Windows, in **Windows Terminal**, with one tab running the API and another for everything else.
- Each command is in its own box. Run **one line at a time**.
- Boxes marked **What I saw** show my output. They are not commands to run.
- Docker Desktop must be running.
- Follow the [first-time setup](../README.md#first-time-setup) in the main README to create and activate the virtual environment, then install this lab's packages:

```powershell
python -m pip install -r lab-03-postgres\requirements.txt
```

---

## Files in this lab

| File | What it does |
|---|---|
| `compose.yaml` | Runs PostgreSQL 18 in Docker, with a named volume and a health check |
| `initdb/create-test-database.sql` | Creates the `assets_test` database the first time PostgreSQL starts |
| `.env.example` | The settings the lab needs, with a placeholder password. The real `.env` is never committed |
| `database.py` | Reads the settings, creates the connection engine, and gives each request a session |
| `models.py` | The `assets` table, written as a Python class |
| `main.py` | The API. The same models and routes as Lab 02, now using the database |
| `conftest.py` | Points the tests at `assets_test` and empties it before every test |
| `test_main.py` | The 19 tests from Lab 02, plus one that reads the table directly |
| `requirements.txt` | The exact versions of every package |

### The database, from `compose.yaml`

```yaml
services:
  db:
    image: postgres:18-alpine
    environment:
      # Read from the .env file next to this one, which Git ignores
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      # Only reachable from this computer, not from the network
      - "127.0.0.1:5432:5432"
    volumes:
      # From PostgreSQL 18, the data volume is mounted at /var/lib/postgresql
      - pgdata:/var/lib/postgresql
      # Scripts in this folder run once, the first time the database is created
      - ./initdb:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10
```

| Setting | Why |
|---|---|
| `${POSTGRES_PASSWORD}` | Docker Compose fills it in from `.env`, so no password is written in this file |
| `127.0.0.1:5432:5432` | Only programs on my computer can connect, not anything else on the network |
| `pgdata:/var/lib/postgresql` | A named volume, so the data survives the container being removed. From PostgreSQL 18 the volume is mounted here, not at `/var/lib/postgresql/data` as in older versions |
| `./initdb` | Runs the SQL script once, when the database is first created |
| `pg_isready` health check | `docker compose up --wait` waits until PostgreSQL accepts connections, not just until the container starts |

### The table, from `models.py`

```python
class AssetRecord(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    type: Mapped[str] = mapped_column(String(50))
    assigned_to: Mapped[str | None] = mapped_column(String(100))
    added: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

This is the original app's `CREATE TABLE`, written in Python:

| Original SQL | SQLAlchemy | Notes |
|---|---|---|
| `id SERIAL PRIMARY KEY` | `mapped_column(primary_key=True)` | PostgreSQL numbers each row |
| `name TEXT NOT NULL` | `Mapped[str]` with `String(100)` | `str` rather than `str \| None` means NOT NULL. The length matches the API's rule |
| `assigned_to TEXT` | `Mapped[str \| None]` | `\| None` means the column can be empty |
| `added TIMESTAMP DEFAULT now()` | `DateTime(timezone=True), server_default=func.now()` | The database stamps the time, and stores its time zone, unlike the original |

### The connection, from `database.py`

```python
class Settings(BaseSettings):
    """Read from environment variables, or from a .env file in the lab folder."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str | None = None


settings = Settings()

# The engine manages a pool of connections. It does not connect until first used.
# pool_pre_ping checks each connection still works before handing it out, so a
# database restart does not break the next request
engine = create_engine(settings.database_url, pool_pre_ping=True)

# A factory for sessions. One session is one conversation with the database
SessionLocal = sessionmaker(bind=engine)


def get_session() -> Iterator[Session]:
    """Give each request its own session, and always close it afterwards."""
    with SessionLocal() as session:
        yield session
```

| Code | What it does |
|---|---|
| `class Settings(BaseSettings)` | Fills `database_url` from the `DATABASE_URL` environment variable or `.env`, and refuses to start if it is missing |
| `extra="ignore"` | Ignores the `POSTGRES_...` lines in `.env`, which are for Docker |
| `create_engine(...)` | Keeps a pool of connections to reuse, instead of reconnecting for every request |
| `pool_pre_ping=True` | Checks a pooled connection is alive before using it. Added after [Issue 3](#3-replacing-the-database-container-broke-the-api) |
| `get_session` with `yield` | Gives each request its own session and always closes it, even if the request fails |

### The routes, from `main.py`

```python
# A database session, supplied to any route that asks for one
SessionDep = Annotated[Session, Depends(get_session)]


@app.post("/assets", status_code=status.HTTP_201_CREATED)
def create_asset(new: AssetIn, session: SessionDep) -> Asset:
    """Add an asset. The database chooses the ID and records when it was added."""
    record = AssetRecord(**new.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return Asset.model_validate(record)
```

| Code | What it does |
|---|---|
| `Depends(get_session)` | Dependency injection: FastAPI creates a session for each request and passes it in. Routes never open or close connections themselves |
| `session.add` then `commit` | Stages the new row, then saves it. Nothing is written until `commit` |
| `session.refresh(record)` | Reloads the row to pick up the `id` and `added` values PostgreSQL has just set |
| `from_attributes=True` (on `Asset`) | Lets Pydantic build the response straight from a database row |
| `lifespan` | Creates the `assets` table when the app starts, if it does not already exist |

### The test set-up, from `conftest.py`

```python
test_engine = create_engine(settings.test_database_url)
TestSession = sessionmaker(bind=test_engine)
Base.metadata.create_all(test_engine)


def get_test_session():
    with TestSession() as session:
        yield session


# Every route that asks for get_session now gets a test database session instead
app.dependency_overrides[get_session] = get_test_session


@pytest.fixture(autouse=True)
def empty_table():
    """Start every test with no assets and IDs counting from 1."""
    with test_engine.begin() as connection:
        connection.execute(text("TRUNCATE TABLE assets RESTART IDENTITY"))
```

| Code | What it does |
|---|---|
| `app.dependency_overrides` | Swaps the real database for the test one, for every route, without changing `main.py`. This is why the routes use `Depends` |
| `TRUNCATE ... RESTART IDENTITY` | Empties the table and resets the IDs before every test, so tests cannot affect each other |
| A `RuntimeError` if `TEST_DATABASE_URL` is missing | Stops the tests rather than letting them run against the real database by mistake |
| `database_rows` fixture | Reads the table with plain SQL, to prove data is really stored in PostgreSQL |

---

## How I built it

### Step 1: Created the configuration with a random password

```powershell
cd C:\fastapi-asset-register\lab-03-postgres
```

I generated a 24-character password of letters and numbers, kept in a variable and never shown:

```powershell
$pw = -join ((48..57) + (65..90) + (97..122) | Get-Random -Count 24 | ForEach-Object { [char]$_ })
```

```powershell
Set-Content -Path .env -Encoding ascii -Value "POSTGRES_USER=assets", "POSTGRES_PASSWORD=$pw", "POSTGRES_DB=assets", "DATABASE_URL=postgresql+psycopg://assets:$pw@localhost:5432/assets", "TEST_DATABASE_URL=postgresql+psycopg://assets:$pw@localhost:5432/assets_test"
```

My first attempt wrote a broken file. See [Issue 1](#1-the-env-file-contained-the-here-string-markers). Letters and numbers only means the password cannot break the URL, as `@` or `/` would.

I checked the file without showing the password, and confirmed Git ignores it:

```powershell
Get-Content .env | ForEach-Object { ($_ -split '=')[0] }
```

```
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
DATABASE_URL
TEST_DATABASE_URL
```

```powershell
git check-ignore -v .env
```

```
.gitignore:10:.env      .env
```

### Step 2: Started PostgreSQL

```powershell
docker compose up -d --wait
```

```
 ✔ Image postgres:18-alpine             Pulled
 ✔ Network asset-register-lab03_default Created
 ✔ Volume asset-register-lab03_pgdata   Created
 ✔ Container asset-register-lab03-db-1  Healthy
```

```powershell
docker compose exec db psql -U assets -d assets -c "\l"
```

**What I saw** (shortened):

```
    Name     | Owner  | Encoding
-------------+--------+----------
 assets      | assets | UTF8
 assets_test | assets | UTF8
 postgres    | assets | UTF8
 template0   | assets | UTF8
 template1   | assets | UTF8
```

```powershell
docker compose logs db | Select-String "create-test-database"
```

```
db-1  | /usr/local/bin/docker-entrypoint.sh: running /docker-entrypoint-initdb.d/create-test-database.sql
```

`assets_test` only appeared on my second attempt. See [Issue 2](#2-the-test-database-was-not-created).

### Step 3: Installed the packages and ran the tests

```powershell
python -m pip install -r requirements.txt
```

```powershell
python -m pytest -v
```

**What I saw** (shortened):

```
collected 20 items

test_main.py::test_health PASSED
...
test_main.py::test_ids_are_never_reused PASSED
test_main.py::test_asset_is_saved_in_the_database PASSED

20 passed in 1.25s
```

---

## Tests I carried out

### Test 1: The data survives an app restart

This is the test that failed in Lab 02. I started the API with `fastapi dev main.py`, added two assets, stopped it with **Ctrl+C**, started it again, and listed them:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/assets
```

**What I saw:**

```
name        : Dell Latitude 7450
type        : laptop
assigned_to : Finance team
id          : 1
added       : 2026-10-20T16:44:27.594303Z

name        : HP LaserJet Pro
type        : printer
assigned_to :
id          : 2
added       : 2026-10-20T16:44:35.086746Z
```

Both assets came back with their original IDs and timestamps.

### Test 2: The data is really in PostgreSQL

```powershell
docker compose exec db psql -U assets -d assets -c "SELECT * FROM assets;"
```

**What I saw:**

```
 id |        name        |  type   | assigned_to  |             added
----+--------------------+---------+--------------+-------------------------------
  1 | Dell Latitude 7450 | laptop  | Finance team | 2026-10-20 16:44:27.594303+00
  2 | HP LaserJet Pro    | printer |              | 2026-10-20 16:44:35.086746+00
```

The printer's `assigned_to` is a real `NULL`, not the empty string the original app stored, and `added` includes its time zone, `+00`.

### Test 3: The data survives the container being replaced

`docker compose down` deletes the container. Without `-v`, it keeps the volume:

```powershell
docker compose down
```

```
 ✔ Container asset-register-lab03-db-1  Removed
 ✔ Network asset-register-lab03_default Removed
```

```powershell
docker compose up -d --wait
```

```powershell
docker compose exec db psql -U assets -d assets -c "SELECT id, name, type, assigned_to FROM assets;"
```

```
 id |        name        |  type   | assigned_to
----+--------------------+---------+--------------
  1 | Dell Latitude 7450 | laptop  | Finance team
  2 | HP LaserJet Pro    | printer |
```

The container was new, but the data lives in the `pgdata` volume. This test also found a bug in the API. See [Issue 3](#3-replacing-the-database-container-broke-the-api).

### Test 4: The API recovers from a database restart

After adding `pool_pre_ping=True`, I repeated Test 3 while the API was running, then asked it for the assets:

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/assets
```

It returned both assets on the first request, with no error. The tests still passed:

```powershell
python -m pytest -q
```

```
20 passed in 0.92s
```

| Test | Expected | Result |
|---|---|---|
| 20 automated tests against `assets_test` | All pass | ✅ |
| App restart | Data still there | ✅ |
| Data read directly with SQL | Matches the API | ✅ |
| Container replaced | Data still there | ✅ |
| API after a database restart | Recovers on the next request | ✅ After the fix in Issue 3 |

---

## Issues I hit and how I fixed them

### 1. The `.env` file contained the here-string markers

**Symptom.**

```
failed to read C:\fastapi-asset-register\lab-03-postgres\.env: line 1: unexpected character "@" in variable name "@\"\r"
```

**Root cause.** I first wrote the file with a PowerShell here-string, which is a block of text between `@"` and `"@`. A here-string only works when PowerShell receives the whole block at once. Mine was not run that way, so the `@"` marker was written into the file as text.

**Fix.** I wrote the file with one `Set-Content` command, passing the five lines as a list. A single line cannot be split up.

### 2. The test database was not created

**Symptom.** `\l` listed `assets`, `postgres`, `template0` and `template1`, but no `assets_test`.

**Investigation.**

```powershell
Get-ChildItem initdb | Select-Object Name, Length
```

This returned nothing: the `initdb` folder was empty. A search found the script one level up:

```powershell
Get-ChildItem -Path C:\fastapi-asset-register -Recurse -Filter "create-test-database*" | Select-Object FullName
```

```
C:\fastapi-asset-register\lab-03-postgres\create-test-database.sql
```

**Root cause.** I created the file while the lab folder, rather than `initdb`, was selected in VS Code. PostgreSQL only runs scripts in `/docker-entrypoint-initdb.d`, and only when the database is first created.

**Fix.** I moved the file, then recreated the database from an empty volume so the script would run. `-v` deletes the volume and all its data, which was safe here because nothing had been stored yet:

```powershell
Move-Item create-test-database.sql initdb\
```

```powershell
docker compose down -v
```

```powershell
docker compose up -d --wait
```

**Lesson.** PostgreSQL init scripts run once, on an empty volume. Changing them later has no effect unless the volume is recreated.

### 3. Replacing the database container broke the API

**Symptom.** After Test 3, the API's next request failed with `Internal Server Error`. The server's log showed why:

```
"GET /assets HTTP/1.1" 500
sqlalchemy.exc.OperationalError: (psycopg.OperationalError) consuming input failed: could not receive data from server: Software caused connection abort (0x00002745/10053)
[SQL: SELECT assets.id, assets.name, assets.type, assets.assigned_to, assets.added
FROM assets ORDER BY assets.id]
```

After the fix, the same log showed `"GET /assets HTTP/1.1" 200` for the first request after a database restart.

**Root cause.** SQLAlchemy keeps a pool of open connections and reuses them. When the old container was removed, every connection in the pool died, but the pool did not know, so it handed a dead connection to the next request.

**Fix.** I added `pool_pre_ping=True` to `create_engine`. SQLAlchemy now checks each connection is alive before using it, and replaces it if not. Repeating Test 3 then worked first time.

**Lesson.** Databases restart, fail over and get patched. An app that cannot survive its database restarting is not ready for production, and this is the kind of fault that only appears when you test what happens when something goes away.

### 4. `No module named pytest` in a new terminal

**Symptom.**

```
C:\Users\<user>\AppData\Local\Python\pythoncore-3.14-64\python.exe: No module named pytest
```

**Root cause.** The new terminal was using my main Python install, not the virtual environment where pytest is installed. Activation was then blocked by the execution policy, as in Lab 01.

**Fix.** `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then `C:\fastapi-asset-register\.venv\Scripts\Activate.ps1`. The `(.venv)` prompt confirms it.

---

## Clean up

To stop PostgreSQL but keep the data:

```powershell
docker compose down
```

To delete the data as well, which cannot be undone:

```powershell
docker compose down -v
```

---

## Command reference

| Command | What it does |
|---|---|
| `docker compose up -d --wait` | Starts the database in the background and waits until it is healthy |
| `docker compose exec db psql -U assets -d assets -c "<SQL>"` | Runs SQL inside the database container |
| `docker compose logs db` | Shows the database container's output |
| `docker compose down` | Removes the container, keeping the volume |
| `docker compose down -v` | Removes the container and the volume, deleting the data |
| `git check-ignore -v <file>` | Shows which `.gitignore` rule, if any, matches a file |

## What I learned

- Moving from a dictionary to a database changed where the data lives, not the API's routes or rules, because each route gets its storage through dependency injection.
- Dependency injection also made testing simple: one line swaps the real database for a test database.
- A separate test database that is emptied before every test keeps the tests repeatable and the real data safe.
- Secrets belong in an ignored `.env` file, with a committed `.env.example` showing what is needed.
- PostgreSQL init scripts run only once, on an empty volume.
- Testing what happens when the database goes away found a real bug that the automated tests could not.

---

## References

Official documentation I used while building and testing this lab.

| What I did | Documentation |
|---|---|
| Connected FastAPI to a SQL database | [FastAPI: SQL (Relational) Databases](https://fastapi.tiangolo.com/tutorial/sql-databases/) |
| Gave each request a session with `Depends` | [FastAPI: Dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) |
| Swapped in the test database | [FastAPI: Testing Dependencies with Overrides](https://fastapi.tiangolo.com/advanced/testing-dependencies/) |
| Created the table on start-up | [FastAPI: Lifespan Events](https://fastapi.tiangolo.com/advanced/events/) |
| Read the settings from `.env` | [FastAPI: Settings and Environment Variables](https://fastapi.tiangolo.com/advanced/settings/) |
| Defined the table as a Python class | [SQLAlchemy: Declaring Mapped Classes](https://docs.sqlalchemy.org/en/21/orm/declarative_tables.html) |
| Recovered from dropped connections | [SQLAlchemy: Dealing with Disconnects](https://docs.sqlalchemy.org/en/21/core/pooling.html#dealing-with-disconnects) |
| Ran PostgreSQL in Docker | [postgres image on Docker Hub](https://hub.docker.com/_/postgres) |
| Created the test database on first start | [postgres image: initialization scripts](https://hub.docker.com/_/postgres#initialization-scripts) |
| Waited for the database to be healthy | [Docker Compose: up](https://docs.docker.com/reference/cli/docker/compose/up/) |