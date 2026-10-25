# Lab 05: Ship It as a Container

## Overview

| | |
|---|---|
| **Goal** | Package the Lab 03 API as a small, hardened container image, run it with PostgreSQL in Docker Compose, then have CI build, smoke-test and publish it to GitHub Container Registry |
| **Runs on** | Docker Desktop on Windows, GitHub Actions, and GitHub Container Registry (GHCR) |
| **Cost** | Free. Actions and GHCR are free for public repositories |
| **Time** | About three hours |

Until now, the API only ran from my virtual environment. In this lab it became a container image that anyone can pull and run, built and tested by CI on every push to `main`.

The published image on GitHub Container Registry:

![The image on GitHub Container Registry](images/ghcr-package.png)

---

## Architecture

```
On my computer (Docker Compose project "asset-register-lab05")

  127.0.0.1:8000 ──► api   (my image, non-root, read-only filesystem)
                      │      DATABASE_URL points at host "db"
                      ▼
  127.0.0.1:5433 ──► db    (postgres:18-alpine) ──► volume "pgdata"

On GitHub, on every push to main

  test (4 labs, in parallel) ──► image: build ──► start the stack ──► smoke test ──► push
                                                                                     │
                            ghcr.io/im-mq/fastapi-asset-register:<commit> and :latest ◄┘
```

| | Lab 03 | Lab 05 |
|---|---|---|
| **The API runs from** | My virtual environment | A container image |
| **PostgreSQL** | Docker Compose | Docker Compose, in the same project as the API |
| **The API finds the database at** | `localhost:5432` | `db:5432`, the Compose service name |
| **Port on my computer** | `5432` | `5433`, so both labs can run at once |
| **Test tools** | In `requirements.txt` | In `requirements-dev.txt`, kept out of the image |

The application code (`database.py`, `models.py`, `main.py`) and the 20 tests are copied unchanged from Lab 03.

---

## Following along?

- I ran every command in **PowerShell** on Windows, in **Windows Terminal**, from the `lab-05-container` folder unless a step says otherwise.
- Each command is in its own box. Run **one line at a time**.
- Boxes marked **What I saw** show my output. They are not commands to run.
- Image IDs, digests and commit hashes will differ on your machine.
- The real `.env` file is not in the repository. Copy `.env.example` to `.env` and set your own password.

---

## The files

### `requirements.txt` and `requirements-dev.txt`

The image only needs what the app needs to run. pytest moved to a separate file:

```
fastapi[standard]==0.149.0
sqlalchemy==2.1.5
psycopg[binary]==3.3.6
pydantic-settings==2.14.0
```

```
# Everything the app needs, plus the tools to test it. Not installed in the image
-r requirements.txt
pytest==9.1.1
```

### `Dockerfile`

```dockerfile
# syntax=docker/dockerfile:1

# ---- Stage 1: install the packages into a virtual environment ----
FROM python:3.14-slim AS build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: the image that actually runs ----
FROM python:3.14-slim

LABEL org.opencontainers.image.source="https://github.com/iM-MQ/fastapi-asset-register"
LABEL org.opencontainers.image.description="Asset Register API: FastAPI and PostgreSQL"

# No .pyc files, and logs appear straight away
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# A user with no password and no home directory, so the app never runs as root
RUN useradd --system --no-create-home --uid 10001 appuser

WORKDIR /app

# Only the finished virtual environment and the app's code are copied across
COPY --from=build /opt/venv /opt/venv
COPY database.py models.py main.py ./

USER appuser

EXPOSE 8000

# Docker marks the container unhealthy if /health stops answering
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

CMD ["fastapi", "run", "main.py", "--port", "8000"]
```

| Part | Why |
|---|---|
| Two stages | The first stage installs packages. Only the finished virtual environment is copied into the second, so pip's working files never reach the final image |
| `python:3.14-slim` | A small Debian-based Python image. Alpine is smaller still, but many Python packages need extra work to install on it |
| `LABEL org.opencontainers.image.source` | Links the published package to this repository on GitHub |
| `LABEL org.opencontainers.image.description` | The text GitHub shows under the package name |
| `useradd ... --uid 10001` and `USER appuser` | The app runs as an ordinary user. If someone broke into it, they would not be root inside the container |
| `COPY database.py models.py main.py` | Only the three files the app runs. No tests, no `.env`, no README |
| `HEALTHCHECK` | Uses Python's own `urllib`, because the slim image has no `curl` |
| `CMD [...]` in exec form | FastAPI's documentation recommends this form, so the app receives shutdown signals and shuts down cleanly |

### `.dockerignore`

Keeps files out of the **build context**, the folder Docker sends to the builder. The most important line is `.env`: my real `.env` can never be copied into an image by mistake.

```
# Only the app's code and requirements go into the image
.env
.env.*
!.env.example
__pycache__/
.pytest_cache/
*.pyc
images/
initdb/
README.md
conftest.py
test_*.py
requirements-dev.txt
compose.yaml
```

### `compose.yaml`

```yaml
# The whole Asset Register: the API and PostgreSQL
name: asset-register-lab05

services:
  db:
    image: postgres:18-alpine
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    ports:
      # For running the tests from my computer. A different port from Lab 03,
      # so both labs can run at once
      - "127.0.0.1:5433:5432"
    volumes:
      - pgdata:/var/lib/postgresql
      - ./initdb:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER} -d $${POSTGRES_DB}"]
      interval: 5s
      timeout: 3s
      retries: 10

  api:
    build: .
    image: asset-register-api:local
    environment:
      # Inside Compose's network, the database's host name is its service name
      DATABASE_URL: postgresql+psycopg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB}
    ports:
      - "127.0.0.1:8000:8000"
    depends_on:
      db:
        condition: service_healthy
    # Hardening: the app cannot change its own files, gain privileges,
    # or use any Linux capabilities it does not need
    read_only: true
    tmpfs:
      - /tmp
    cap_drop:
      - ALL
    security_opt:
      - no-new-privileges:true

volumes:
  pgdata:
```

| Part | Why |
|---|---|
| `${POSTGRES_PASSWORD}` | Compose reads the value from `.env`, which is not in the repository. In CI it comes from the workflow instead |
| `127.0.0.1:` on both ports | Only my own computer can reach them, not other devices on my network |
| `@db:5432` | Containers in a Compose project reach each other by service name |
| `depends_on ... service_healthy` | The API only starts once PostgreSQL passes its health check |
| `read_only: true` and `tmpfs: /tmp` | The container's filesystem cannot be changed. Only `/tmp` is writable, and it lives in memory |
| `cap_drop: ALL` | Removes every Linux capability. The API only listens on port 8000, which needs none |
| `no-new-privileges:true` | Nothing in the container can gain more privileges than it started with |

### `.env.example`

A template for `.env` with a placeholder password. It sets `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB` for Compose, plus `DATABASE_URL` and `TEST_DATABASE_URL` on `localhost:5433` for running the tests from my computer. My real `.env` has the same lines with a random 24-character password, and is excluded by `.gitignore` and `.dockerignore`.

---

## Part 1: The container on my computer

### Step 1: Built the image and started the stack

```powershell
cd C:\fastapi-asset-register\lab-05-container
```

```powershell
docker compose up -d --build
```

```powershell
docker compose ps
```

Both containers showed as **healthy**, and both ports were bound to `127.0.0.1` only.

### Step 2: Used the API

`/health` returned `{"status":"ok"}`, and creating an asset returned `id` 1, saved in PostgreSQL.

### Tests I carried out

#### Test 1: The app does not run as root

```powershell
docker compose exec api id
```

**What I saw:**

```
uid=10001(appuser) gid=999(appuser) groups=999(appuser)
```

#### Test 2: The filesystem is read-only

I tried to create a file where the app's code lives:

```powershell
docker compose exec api touch /app/hacked.txt
```

**What I saw:**

```
touch: cannot touch '/app/hacked.txt': Read-only file system
```

This is the result I wanted. Even running code inside the container cannot change the app's files.

#### Test 3: Only the app's code is in the image

```powershell
docker compose exec api ls -la /app
```

Only `database.py`, `main.py` and `models.py` were there, owned by `root`. `appuser` can read them but not change them, even without the read-only filesystem.

#### Test 4: The image size

```powershell
docker image ls asset-register-api
```

**What I saw** (shortened):

```
IMAGE                      ID             DISK USAGE   CONTENT SIZE
asset-register-api:local   d39611e56013        387MB         87.8MB
```

**Disk usage** is the unpacked size on my computer, most of it the shared `python:3.14-slim` base. **Content size** is the compressed size, which is what is pushed to and pulled from a registry.

#### Test 5: The tests pass against the containerised database

From my virtual environment, with the test tools from `requirements-dev.txt`:

```powershell
python -m pip install -r requirements-dev.txt
```

```powershell
python -m pytest -q
```

**What I saw:**

```
....................                                                     [100%]
20 passed in 1.00s
```

The same 20 tests as Lab 03, unchanged, now against PostgreSQL on port 5433.

| Test | Expected | Result |
|---|---|---|
| Both containers healthy | `healthy`, ports on `127.0.0.1` only | ✅ |
| API works | `/health` ok, asset created | ✅ |
| Runs as | `appuser`, not root | ✅ |
| Write to `/app` | Refused | ✅ |
| Contents of `/app` | Only the three app files | ✅ |
| Tests | 20 passed | ✅ |

---

## Part 2: CI builds, tests and publishes the image

### The workflow, `.github/workflows/tests.yml`

The workflow from Lab 04, with Lab 05 added to the test matrix and a new `image` job:

```yaml
# Tests every lab, then builds, smoke-tests and publishes the Lab 05 image
name: Tests

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

# Every job can read the code. Only the image job is given more, below
permissions:
  contents: read

jobs:
  test:
    name: ${{ matrix.lab }}
    runs-on: ubuntu-latest

    strategy:
      # Let every lab finish, even if one fails, so each reports its own result
      fail-fast: false
      matrix:
        lab:
          - lab-01-python-refresher
          - lab-02-fastapi
          - lab-03-postgres
          - lab-05-container

    # A throwaway PostgreSQL for Labs 03 and 05, deleted when the job ends
    services:
      postgres:
        image: postgres:18-alpine
        env:
          POSTGRES_USER: assets
          # Not a real secret: this database only exists inside the job,
          # cannot be reached from outside, and holds no real data
          POSTGRES_PASSWORD: ci-only-password
          POSTGRES_DB: assets_test
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U assets -d assets_test"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 10

    # The same settings the labs read from .env on my computer
    env:
      DATABASE_URL: postgresql+psycopg://assets:ci-only-password@localhost:5432/assets_test
      TEST_DATABASE_URL: postgresql+psycopg://assets:ci-only-password@localhost:5432/assets_test

    # Every "run" step starts inside the lab's own folder
    defaults:
      run:
        working-directory: ${{ matrix.lab }}

    steps:
      - name: Check out the code
        uses: actions/checkout@v5

      - name: Set up Python 3.14
        uses: actions/setup-python@v6
        with:
          python-version: "3.14"
          cache: pip
          cache-dependency-path: ${{ matrix.lab }}/requirements*.txt

      # Lab 05 keeps its test tools in requirements-dev.txt, out of the image
      - name: Install the lab's packages
        run: |
          if [ -f requirements-dev.txt ]; then
            python -m pip install -r requirements-dev.txt
          else
            python -m pip install -r requirements.txt
          fi

      - name: Run the tests
        run: python -m pytest -v

  image:
    name: image
    # Only build the image once every lab's tests have passed
    needs: test
    runs-on: ubuntu-latest

    # This job alone may publish packages
    permissions:
      contents: read
      packages: write

    # Compose reads these instead of a .env file
    env:
      POSTGRES_USER: assets
      POSTGRES_PASSWORD: ci-only-password
      POSTGRES_DB: assets

    defaults:
      run:
        working-directory: lab-05-container

    steps:
      - name: Check out the code
        uses: actions/checkout@v5

      - name: Build the image and start the stack
        run: docker compose up -d --build --wait

      - name: Smoke-test the running API
        run: |
          curl --fail --silent --show-error http://127.0.0.1:8000/health
          curl --fail --silent --show-error -X POST http://127.0.0.1:8000/assets \
            -H "Content-Type: application/json" \
            -d '{"name": "Smoke test laptop", "type": "laptop"}'
          curl --fail --silent --show-error http://127.0.0.1:8000/assets | grep "Smoke test laptop"

      - name: Show the logs if anything failed
        if: failure()
        run: docker compose logs

      - name: Stop the stack
        if: always()
        run: docker compose down -v

      # Publish only from main, never from a pull request
      - name: Log in to GitHub Container Registry
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      # Push the exact image that was just tested, not a new build
      - name: Publish the tested image
        if: github.event_name == 'push' && github.ref == 'refs/heads/main'
        run: |
          IMAGE=ghcr.io/im-mq/fastapi-asset-register
          docker tag asset-register-api:local "$IMAGE:${{ github.sha }}"
          docker tag asset-register-api:local "$IMAGE:latest"
          docker push "$IMAGE:${{ github.sha }}"
          docker push "$IMAGE:latest"
```

| Part | What it does |
|---|---|
| `lab-05-container` in the matrix | Runs Lab 05's 20 tests alongside the other labs |
| `if [ -f requirements-dev.txt ]` | Lab 05 installs its test tools from `requirements-dev.txt`. The other labs still use `requirements.txt` |
| `needs: test` | The image is only built once every lab's tests have passed |
| `permissions: packages: write` on the `image` job only | Least privilege: the test jobs can still only read the code |
| `docker compose up -d --build --wait` | Builds the image with the same `compose.yaml` I use locally, and waits until both containers are healthy |
| Smoke test | Checks the real running container, not just the code: health, a write to PostgreSQL, and reading it back |
| `if: failure()` logs | If anything fails, the containers' logs appear in the run |
| `if: always()` stop | The stack is always cleaned up, pass or fail |
| `github.event_name == 'push' && github.ref == 'refs/heads/main'` | Pull requests build and test the image but never publish it |
| `secrets.GITHUB_TOKEN` | A short-lived token GitHub creates for each run. No personal access token is stored anywhere |
| `docker tag` instead of a new build | The image that is pushed is exactly the one the smoke test checked |
| Two tags | `:<commit>` never changes, so any image can be traced to its code. `:latest` always moves to the newest build |

### Step 1: Pushed the workflow and Lab 05

```powershell
cd C:\fastapi-asset-register
```

```powershell
git add lab-05-container .github
```

Before committing, I checked `git status` to make sure `lab-05-container/.env` was not staged, and scanned the staged files for anything personal, including my real database password. Then I committed and pushed to `main`.

### Step 2: Watched the run

The four test jobs ran in parallel, then the `image` job started.

![The smoke test in the image job](images/ci-smoke-test.png)

**What I saw** in **Smoke-test the running API**, three responses printed on one line because `curl` adds no line break:

```
{"status":"ok"}{"name":"Smoke test laptop","type":"laptop","assigned_to":null,"id":1,"added":"2026-10-20T19:20:03.722330Z"}[{"name":"Smoke test laptop","type":"laptop","assigned_to":null,"id":1,"added":"2026-10-20T19:20:03.722330Z"}]
```

**What I saw** in **Publish the tested image** (shortened):

```
The push refers to repository [ghcr.io/im-mq/fastapi-asset-register]
22a6d2b1cc03: Pushed
...
3f874db21bd89507c199240a075ec40c04eb5c17: digest: sha256:7eb88a6a6f6f98fb8b7fa46bb6aba84cfd4e4f009bcfca7c5fd7d87f23287df5 size: 1993
The push refers to repository [ghcr.io/im-mq/fastapi-asset-register]
c26012ea6753: Layer already exists
...
latest: digest: sha256:7eb88a6a6f6f98fb8b7fa46bb6aba84cfd4e4f009bcfca7c5fd7d87f23287df5 size: 1993
```

Both tags have the same digest, so they are the same image. The second push uploaded nothing new: every layer already existed.

### Step 3: Checked the package

The package appeared under my profile's **Packages** tab, already **Public**, with the description from the Dockerfile and both tags, as the screenshot at the top shows. See [Issue 3](#issues-i-hit-and-things-i-learned-along-the-way) for why it was public.

### Step 4: Required the new checks

I added `lab-05-container` and `image` to the **Protect main** ruleset from Lab 04, under **Require status checks to pass**. A pull request now needs all five checks to pass, including a successful build and smoke test of the image.

### Test 6: Pulled the published image

From PowerShell, without signing in to GHCR:

```powershell
docker pull ghcr.io/im-mq/fastapi-asset-register:latest
```

**What I saw** (shortened):

```
latest: Pulling from im-mq/fastapi-asset-register
b6efcd50874c: Pull complete
a5883d972f3b: Already exists
...
Digest: sha256:7eb88a6a6f6f98fb8b7fa46bb6aba84cfd4e4f009bcfca7c5fd7d87f23287df5
Status: Downloaded newer image for ghcr.io/im-mq/fastapi-asset-register:latest
```

```powershell
docker image inspect ghcr.io/im-mq/fastapi-asset-register:latest --format "{{index .RepoDigests 0}}"
```

**What I saw:**

```
ghcr.io/im-mq/fastapi-asset-register@sha256:7eb88a6a6f6f98fb8b7fa46bb6aba84cfd4e4f009bcfca7c5fd7d87f23287df5
```

The digest matches the one CI pushed, so the image I pulled is exactly the one CI tested. Layers marked **Already exists** came from the `python:3.14-slim` base already on my computer.

| Test | Expected | Result |
|---|---|---|
| Lab 05's tests in CI | 20 passed | ✅ |
| Smoke test of the running image | Health ok, asset created and read back | ✅ |
| Published from `main` | `:<commit>` and `:latest` pushed, same digest | ✅ |
| Pull without signing in | Works, because the package is public | ✅ |
| Pulled digest | Matches CI's | ✅ |

---

## Issues I hit and things I learned along the way

Nothing in this lab failed, but three things were not what I expected.

### 1. Docker suggested "Debug this Compose error with Gordon"

After the read-only test, Docker printed:

```
What's next:
    Debug this Compose error with Gordon → docker ai "help me fix this compose error"
```

Gordon is the AI assistant built into Docker Desktop. Docker suggests it whenever a command fails. Here the failure was the point of the test, so there was nothing to fix.

### 2. Two different image sizes

`docker image ls` showed 387MB and 87.8MB for the same image. The first is the unpacked size on disk, the second the compressed size sent to a registry. When comparing images, I now look at both.

### 3. The package was already public

I expected a new package on GHCR to start private. It was public straight away. GitHub's documentation explains why: a package published from a workflow with `GITHUB_TOKEN` is linked to the repository the workflow runs in, and inherits that repository's visibility and permissions. This repository is public, so the package is too.

---

## Clean-up

To stop the stack and keep the data:

```powershell
docker compose down
```

To stop it and delete the database volume as well:

```powershell
docker compose down -v
```

---

## Command reference

| Command | What it does |
|---|---|
| `docker compose up -d --build` | Builds the image, then starts every service in the background |
| `docker compose up -d --build --wait` | The same, then waits until every service is healthy |
| `docker compose ps` | Lists the project's containers, their health and ports |
| `docker compose exec api <command>` | Runs a command inside the running `api` container |
| `docker compose logs` | Shows the containers' output |
| `docker compose down -v` | Stops and removes the containers, network and volumes |
| `docker image ls <name>` | Lists local images and their sizes |
| `docker pull <image>` | Downloads an image from a registry |
| `docker image inspect <image> --format "{{index .RepoDigests 0}}"` | Shows the registry digest of a pulled image |
| `docker tag <source> <target>` | Gives an existing image another name, without rebuilding it |
| `docker push <image>` | Uploads an image to a registry |

## What I learned

- A multi-stage build keeps build tools out of the final image, and `.dockerignore` keeps secrets and tests out of the build entirely.
- Running as a non-root user with a read-only filesystem and no capabilities limits what an attacker could do even if the app were broken into.
- Separating `requirements.txt` from `requirements-dev.txt` keeps test tools out of production.
- Inside Compose, containers find each other by service name, so the same code connects to `localhost` from my computer and to `db` from the container, through one environment variable.
- A smoke test checks the built, running container, which unit tests alone cannot.
- Pushing the exact image that was tested, tagged with the commit, means every published image can be traced back to its code.
- `GITHUB_TOKEN` with `packages: write` on one job is enough to publish. No long-lived token is stored anywhere.

---

## References

Official documentation I used while building and testing this lab.

| What I did | Documentation |
|---|---|
| Wrote the two-stage Dockerfile | [Docker: Multi-stage builds](https://docs.docker.com/build/building/multi-stage/) |
| Used `USER`, `HEALTHCHECK` and `CMD` | [Docker: Dockerfile reference](https://docs.docker.com/reference/dockerfile/) |
| Kept files out of the build | [Docker: Build context and .dockerignore files](https://docs.docker.com/build/concepts/context/#dockerignore-files) |
| Ran FastAPI in a container with `fastapi run` | [FastAPI: FastAPI in Containers - Docker](https://fastapi.tiangolo.com/deployment/docker/) |
| Hardened the `api` service and waited for the database | [Docker: Define services in Docker Compose](https://docs.docker.com/reference/compose-file/services/) |
| Started the stack and waited for health in CI | [Docker: docker compose up](https://docs.docker.com/reference/cli/docker/compose/up/) |
| Logged in to GHCR from the workflow | [docker/login-action](https://github.com/docker/login-action) |
| Published to GHCR and labelled the image | [GitHub: Working with the Container registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry) |
| Published with `GITHUB_TOKEN` | [GitHub: Publishing and installing a package with GitHub Actions](https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions) |
| Understood why the package was public | [GitHub: About permissions for GitHub Packages](https://docs.github.com/en/packages/learn-github-packages/about-permissions-for-github-packages) |
