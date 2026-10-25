# Lab 04: Tests in CI

## Overview

| | |
|---|---|
| **Goal** | Run every lab's tests on GitHub Actions on every push and pull request, with a real PostgreSQL for Lab 03, and stop a change reaching `main` unless they all pass |
| **Runs on** | GitHub Actions (Ubuntu, Python 3.14) and the repository's settings |
| **Cost** | Free. GitHub Actions is free for public repositories |
| **Time** | About two hours |

Until now, the tests only ran when I remembered to run them, on my own computer. This lab moves them to **GitHub Actions**, so they run automatically on GitHub's servers for every push and every pull request. A **ruleset** then makes passing tests a requirement for merging into `main`.

A pull request that breaks Lab 01's tag rule, with merging blocked because a required check failed:

![A failing check blocks the pull request](images/ci-pr-blocked.png)

---

## Architecture

```
git push or pull request ──► GitHub Actions: "Tests"
                              ├── job: lab-01-python-refresher ──► 17 tests
                              ├── job: lab-02-fastapi          ──► 19 tests
                              └── job: lab-03-postgres         ──► 20 tests
                                     └── service: postgres:18-alpine (deleted when the job ends)

Ruleset "Protect main": all three jobs must pass before a pull request can merge (Lab 05 adds two more)
```

This lab adds no application code. It is one workflow file at the root of the repository, plus a repository setting.

---

## Following along?

- I ran every command in **PowerShell** on Windows, in **Windows Terminal**.
- Each command is in its own box. Run **one line at a time**.
- Boxes marked **What I saw** show my output. They are not commands to run.
- The workflow lives at `.github/workflows/tests.yml` in the root of the repository, not in this folder. GitHub only runs workflows from there.

---

## The workflow, `.github/workflows/tests.yml`

> [!NOTE]
> This is the workflow as it was at the end of this lab. In [Lab 05](../lab-05-container/README.md#part-2-ci-builds-tests-and-publishes-the-image) I added Lab 05 to the test matrix, plus a new `image` job that builds, smoke-tests and publishes the container image, and made both new checks required. The [current workflow file](../.github/workflows/tests.yml) has the latest version.

```yaml
# Runs every lab's tests on GitHub's servers, on every push and pull request
name: Tests

on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:

# The workflow only needs to read the code
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

    # A throwaway PostgreSQL for Lab 03, deleted when the job ends
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

    # The same settings Lab 03 reads from .env on my computer
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
          cache-dependency-path: ${{ matrix.lab }}/requirements.txt

      - name: Install the lab's packages
        run: python -m pip install -r requirements.txt

      - name: Run the tests
        run: python -m pytest -v
```

| Part | What it does |
|---|---|
| `on: push`, `pull_request`, `workflow_dispatch` | Runs on every push to `main`, on every pull request, and on demand from the **Actions** tab |
| `permissions: contents: read` | Least privilege: the workflow can read the code and nothing else |
| `matrix: lab: [...]` | One job definition, run three times at once, one per lab |
| `fail-fast: false` | Without it, one failing job cancels the others. With it, every lab reports its own result |
| `services: postgres` | GitHub starts PostgreSQL before the steps and waits for its health check |
| `ci-only-password` in the file | Safe, because the database exists only for a few minutes inside GitHub's runner and is never exposed. Real credentials belong in GitHub Secrets |
| `env: DATABASE_URL ...` | Replaces my `.env` file, which is not in the repository. Lab 03 reads environment variables first, so its code did not change |
| `working-directory` | Each job runs in its own lab folder, as I do locally |
| `cache: pip` | Reuses downloaded packages between runs |
| `python-version: "3.14"` | In quotes, so YAML does not read it as the number 3.14 |

---

## How I built it

### Step 1: Created the workflow and pushed it

```powershell
cd C:\fastapi-asset-register
```

```powershell
New-Item -ItemType Directory -Path .github\workflows
```

I created `tests.yml`, committed and pushed it. The **Actions** tab then showed *Get started with GitHub Actions*, meaning GitHub had found no workflow. See [Issue 1](#1-github-did-not-find-the-workflow).

### Step 2: Watched the first run

After moving the file to the right place, the run's three jobs all passed. The `lab-03-postgres` job started PostgreSQL in **Initialize containers** before running the tests.

![The first run, with all three labs passing](images/ci-run-passing.png)

**What I saw** in the `lab-03-postgres` job (shortened):

```
Initialize containers
  Starting postgres service container
  Waiting for all services to be ready

Run the tests
  platform linux -- Python 3.14.8, pytest-9.1.1, pluggy-1.7.0
  collecting ... collected 20 items
  test_main.py::test_health PASSED
  ...
```

The same tests, unchanged, passed on Linux as well as on my Windows computer.

---

## Tests I carried out

### Test 1: A bad change in a pull request

I repeated Lab 01's "simplify the tag rule" change, this time on a branch, so `main` was never touched:

```powershell
git switch -c break-tag-rule
```

```powershell
(Get-Content lab-01-python-refresher\assets.py) -replace 'AST-\\d\{4\}', 'AST-\d+' | Set-Content lab-01-python-refresher\assets.py
```

```powershell
git commit -am "Loosen the asset tag rule"
```

```powershell
git push -u origin break-tag-rule
```

I opened a pull request on GitHub. The checks ran automatically:

![The pull request's checks, before checks were required](images/ci-pr-failing.png)

| Check | Result |
|---|---|
| `lab-01-python-refresher` | ❌ Failing after 30s |
| `lab-02-fastapi` | ✅ Successful in 27s |
| `lab-03-postgres` | ✅ Successful in 35s |

CI caught the change and showed exactly which lab it broke. But the **Merge pull request** button was still enabled: CI was reporting the problem, not preventing it.

I closed the pull request without merging, deleted the branch on GitHub, and cleaned up locally:

```powershell
git switch main
```

```powershell
git branch -D break-tag-rule
```

```powershell
git fetch --prune
```

```
 - [deleted]         (none)     -> origin/break-tag-rule
```

### Test 2: Making the checks required

I created a ruleset in **Settings → Rules → Rulesets**:

| Setting | Value | Why |
|---|---|---|
| Name | `Protect main` | |
| Enforcement status | Active | |
| Target | The default branch, `main` | |
| Require status checks to pass | `lab-01-python-refresher`, `lab-02-fastapi`, `lab-03-postgres` | A pull request cannot merge unless all three pass |
| Restrict deletions | On | Nobody can delete `main` |
| Block force pushes | On | Nobody can rewrite `main`'s history |
| Bypass list | Repository admin | So I can still push documentation straight to `main`. In a team, very few people would have this |

I then made the same bad change in GitHub's web editor, choosing **Create a new branch for this commit and start a pull request**. This time each check was marked **Required**, and the **Merge pull request** button was disabled, as the screenshot at the top shows. The only way to merge was the admin bypass, which I did not use. I closed the pull request and deleted the branch.

| Test | Expected | Result |
|---|---|---|
| Push to `main` | All three labs pass | ✅ |
| Bad change in a pull request | Lab 01 fails, the others pass | ✅ |
| Merging the bad change with checks required | Blocked | ✅ |

---

## Issues I hit and how I fixed them

### 1. GitHub did not find the workflow

**Symptom.** After pushing, the **Actions** tab showed *Get started with GitHub Actions* and a list of suggested templates, instead of a run.

**Investigation.**

```powershell
Get-ChildItem -Path . -Recurse -Force -Filter "tests.yml*" -Exclude .venv | Select-Object FullName
```

```
C:\fastapi-asset-register\.github\tests.yml
```

**Root cause.** I created the file in `.github` instead of `.github\workflows`. GitHub only runs workflow files from `.github/workflows`.

**Fix.** I moved the file and committed the move:

```powershell
Move-Item .github\tests.yml .github\workflows\
```

```powershell
git add .github
```

```powershell
git commit -m "Move workflow into .github/workflows"
```

```
 rename .github/{ => workflows}/tests.yml (100%)
```

Git recognised the change as a rename. `100%` means the contents were unchanged.

**Lesson.** This was the same kind of mistake as the misplaced init script in Lab 03. I now list a folder's contents after creating files in it, before relying on them.

---

## Command reference

| Command | What it does |
|---|---|
| `git switch -c <branch>` | Creates a new branch and switches to it |
| `git commit -am "<message>"` | Stages every changed tracked file and commits it |
| `git push -u origin <branch>` | Pushes a new branch to GitHub and links it to the local one |
| `git switch main` | Switches back to `main`, restoring its version of every file |
| `git branch -D <branch>` | Deletes a local branch that was never merged |
| `git fetch --prune` | Removes local records of branches deleted on GitHub |

## What I learned

- CI runs the same tests on every change, on a clean machine, so passing does not depend on my computer or my memory.
- A matrix runs one job definition for several labs at once, and `fail-fast: false` shows exactly which one broke.
- A service container gives a CI job a real, throwaway database, configured through environment variables.
- Reporting a failure is not the same as preventing it. Only a required status check stopped the bad change from being merged.
- Changes reach a protected `main` through branches and pull requests, which is how teams work.
- The same tests passed on Linux in CI and on Windows locally, without changes.

---

## References

Official documentation I used while building and testing this lab.

| What I did | Documentation |
|---|---|
| Wrote the workflow | [GitHub Actions: Workflow syntax](https://docs.github.com/en/actions/using-workflows/workflow-syntax-for-github-actions) |
| Ran one job for each lab | [GitHub Actions: Using a matrix for your jobs](https://docs.github.com/en/actions/using-jobs/using-a-matrix-for-your-jobs) |
| Gave Lab 03 a PostgreSQL database | [GitHub Actions: Creating PostgreSQL service containers](https://docs.github.com/en/actions/using-containerized-services/creating-postgresql-service-containers) |
| Set up Python with caching | [actions/setup-python](https://github.com/actions/setup-python) |
| Limited the workflow's permissions | [GitHub Actions: Assigning permissions to jobs](https://docs.github.com/en/actions/using-jobs/assigning-permissions-to-jobs) |
| Protected `main` | [GitHub: About rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets) |
| Required the checks to pass | [GitHub: Available rules for rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/available-rules-for-rulesets) |
| Added the status badge | [GitHub Actions: Adding a workflow status badge](https://docs.github.com/en/actions/monitoring-and-troubleshooting-workflows/adding-a-workflow-status-badge) |
