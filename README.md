# FastAPI Asset Register

Rebuilding my [Docker Asset Register](https://github.com/iM-MQ/docker-asset-register), a Flask and PostgreSQL app, as a modern REST API with **FastAPI**, step by step, with automated tests from the very first lab.

I already know what the Asset Register does, so each lab focuses on *how* to build it well: typed Python, validation, a real database, tests that run on every push, and a container image ready to deploy.

## Labs

| Lab | Topic | Status |
|---|---|---|
| [01](lab-01-python-refresher) | Python refresher: virtual environments, type hints, dataclasses, enums, JSON files, and first tests with pytest | Complete ✅ |
| 02 | First FastAPI app: create, read, update and delete assets in memory, with Pydantic validation and automatic API docs | Planned ⏳ |
| 03 | A real database: PostgreSQL through SQLAlchemy, run with Docker Compose | Planned ⏳ |
| 04 | Tests in CI: pytest with FastAPI's test client, run by GitHub Actions on every push | Planned ⏳ |
| 05 | Ship it: a container image published to GitHub, ready to deploy to Azure | Planned ⏳ |

## Where this fits

| Repository | What it covers |
|---|---|
| [docker-asset-register](https://github.com/iM-MQ/docker-asset-register) | The original Flask app, containerised with Docker Compose and a CI pipeline |
| [terraform-azure-labs](https://github.com/iM-MQ/terraform-azure-labs) | Azure infrastructure as code with Terraform |
| [kubernetes-labs](https://github.com/iM-MQ/kubernetes-labs) | The Asset Register on Kubernetes, locally and on AKS |
| [azure-landing-zone](https://github.com/iM-MQ/azure-landing-zone) | The governed Azure platform that applications like this run in |
| **fastapi-asset-register** | The application itself, rebuilt as a tested REST API |

## Prerequisites

| Requirement | Version used | Purpose | Install (Windows) |
|---|---|---|---|
| Python | 3.14 (3.12 or later required) | Runs the code and tests | [python.org/downloads](https://www.python.org/downloads/) |
| Git | 2.x | Clones this repository | `winget install --id Git.Git -e` |
| Docker Desktop | Latest | Runs PostgreSQL from Lab 03 | `winget install --id Docker.DockerDesktop -e` |
| VS Code + Python extension | Latest (optional) | Editing, with type checking and test discovery | `winget install --id Microsoft.VisualStudioCode -e` |

## First-time setup

Clone the repository:

```powershell
git clone https://github.com/iM-MQ/fastapi-asset-register.git
```

```powershell
cd fastapi-asset-register
```

Create a virtual environment, a private copy of Python for this project:

```powershell
py -m venv .venv
```

Activate it. If PowerShell says running scripts is disabled, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` first, which allows scripts in that window only:

```powershell
.\.venv\Scripts\Activate.ps1
```

Each lab has its own `requirements.txt`. For example, for Lab 01:

```powershell
python -m pip install -r lab-01-python-refresher\requirements.txt
```

## Practices followed

- Every lab has tests, and every test is run before committing
- Package versions are pinned in `requirements.txt`, so results are repeatable
- The virtual environment, caches and secrets are excluded by `.gitignore`
- Every README records the commands I ran, what I saw, and the issues I hit