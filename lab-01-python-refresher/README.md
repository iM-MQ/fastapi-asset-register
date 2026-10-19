# Lab 01: Python Refresher

## Overview

| | |
|---|---|
| **Goal** | Refresh the Python features FastAPI depends on by building a small asset register, and test it with pytest from the start |
| **Runs on** | Windows, Python 3.14, in a virtual environment |
| **Cost** | Free |
| **Time** | About an hour |

FastAPI is built on standard Python features. It reads **type hints** to validate requests, uses **models** much like dataclasses, and turns **enums** into lists of allowed values. Before writing an API, I practised each of these in plain Python, on the same subject as the API: an asset register.

The code loads assets from a JSON file, validates every one, finds them by tag, adds new ones and counts them by status. Seventeen tests check that it does all of that, and that it rejects bad data.

---

## Following along?

- I ran every command in **PowerShell** on Windows, using the terminal inside **VS Code**.
- Each command is in its own box. Run **one line at a time**.
- Boxes marked **What I saw** show my output. They are not commands to run.
- Follow the [first-time setup](../README.md#first-time-setup) in the main README to create and activate the virtual environment.

---

## Files in this lab

| File | What it does |
|---|---|
| `assets.py` | The `Asset` model, its validation, and functions to load, save, find, add and count assets |
| `sample_assets.json` | Five example assets |
| `test_assets.py` | 13 test functions, which run as 17 tests |
| `requirements.txt` | The exact pytest version, so anyone can install the same one |

### The model, from `assets.py`

```python
TAG_PATTERN = re.compile(r"AST-\d{4}")


class Status(StrEnum):
    """The only states an asset can be in."""

    IN_STOCK = "in_stock"
    IN_USE = "in_use"
    REPAIR = "repair"
    RETIRED = "retired"


@dataclass
class Asset:
    """One piece of equipment in the register."""

    tag: str
    name: str
    category: str
    status: Status = Status.IN_STOCK
    assigned_to: str | None = None

    def __post_init__(self) -> None:
        # Runs straight after the object is created, so a bad asset never exists
        self.tag = self.tag.strip().upper()
        if not TAG_PATTERN.fullmatch(self.tag):
            raise ValueError(f"Tag '{self.tag}' must look like AST-0001")

        if not self.name.strip():
            raise ValueError("Name must not be empty")

        # Accepts "in_use" from a JSON file as well as Status.IN_USE.
        # An unknown value raises ValueError
        self.status = Status(self.status)

        if self.status == Status.IN_USE and not self.assigned_to:
            raise ValueError(f"{self.tag} is in use, so it must be assigned to someone")
```

| Python feature | Where | Why it matters for FastAPI |
|---|---|---|
| Type hints, such as `tag: str` and `-> list[Asset]` | Everywhere | FastAPI reads them to validate requests and build the API docs |
| `str \| None` | `assigned_to` | How an optional field is written in FastAPI |
| `@dataclass` | `Asset` | Generates the boilerplate. Pydantic models in Lab 02 work the same way, with more validation |
| `StrEnum` | `Status` | A fixed set of allowed values. FastAPI rejects anything else with a clear error |
| `__post_init__` | `Asset` | Validation that runs when the object is created, so an invalid asset never exists |
| Regular expression | `TAG_PATTERN` | `AST-` followed by exactly four digits |

### The functions, from `assets.py`

| Function | Feature it uses |
|---|---|
| `load_assets` | `pathlib`, `json`, and a list comprehension with `**item` to turn each dictionary into an `Asset` |
| `save_assets` | `dataclasses.asdict` to turn each `Asset` back into a dictionary |
| `find_by_tag` | `next(..., None)` to return the first match or nothing |
| `add_asset` | Returns a **new** list instead of changing the one it was given |
| `count_by_status` | `collections.Counter` |
| `main` | f-strings with widths, such as `{asset.tag:<10}`, to line up columns |

`if __name__ == "__main__":` at the bottom runs `main()` only when the file is run directly, not when the tests import it.

### The tests, from `test_assets.py`

```python
def make_asset(**changes) -> Asset:
    """A valid asset, with any field overridden for a test."""
    fields = {"tag": "AST-0001", "name": "Test laptop", "category": "laptop"}
    fields.update(changes)
    return Asset(**fields)


@pytest.mark.parametrize("bad_tag", ["0001", "AST-1", "AST-00001", "XYZ-0001", ""])
def test_badly_formed_tags_are_rejected(bad_tag):
    with pytest.raises(ValueError, match="must look like AST-0001"):
        make_asset(tag=bad_tag)


def test_save_then_load_gives_the_same_assets(tmp_path):
    # tmp_path is a fresh, empty folder that pytest creates for this test only
    original = [
        make_asset(),
        make_asset(tag="AST-0002", status="in_use", assigned_to="Reception"),
    ]
    path = tmp_path / "assets.json"

    save_assets(original, path)
    loaded = load_assets(path)

    assert loaded == original
```

| pytest feature | What it does |
|---|---|
| A function named `test_...` | pytest finds and runs it automatically |
| `assert` | The test fails if the statement is not true |
| `pytest.raises(ValueError, match=...)` | The test passes **only if** that error happens with that message. This is how to test that bad input is rejected |
| `@pytest.mark.parametrize` | Runs one test once per value. Five bad tags make five tests |
| `tmp_path` | A temporary folder for one test, so tests never touch real files |
| `make_asset(**changes)` | Builds a valid asset, so each test changes only the field it is checking |

---

## How I built it

### Step 1: Checked what was installed

```powershell
py --version
```

```
Python 3.14.7
```

`git --version` and `docker --version` confirmed Git and Docker were already installed from my earlier projects.

### Step 2: Created the repository and a virtual environment

```powershell
New-Item -ItemType Directory -Path C:\fastapi-asset-register
```

```powershell
cd C:\fastapi-asset-register
```

```powershell
git init -b main
```

```powershell
py -m venv .venv
```

```powershell
.\.venv\Scripts\Activate.ps1
```

PowerShell blocked the activation script. See [Issue 1](#1-powershell-blocked-the-activation-script). Once it was active, I checked Python was running from the project:

```powershell
python -c "import sys; print(sys.prefix)"
```

```
C:\fastapi-asset-register\.venv
```

### Step 3: Installed pytest

```powershell
python -m pip install pytest
```

```powershell
python -m pytest --version
```

```
pytest 9.1.1
```

I recorded the version in `requirements.txt` as `pytest==9.1.1`.

### Step 4: Ran the script

```powershell
cd lab-01-python-refresher
```

```powershell
python assets.py
```

**What I saw:**

```
Tag       Name                    Status    Assigned to
AST-0001  Dell Latitude 7450      in_use    Finance team
AST-0002  Dell Latitude 7450      in_stock  -
AST-0003  HP LaserJet Pro         repair    -
AST-0004  Cisco Catalyst 9200     in_use    Server room
AST-0005  Lenovo ThinkPad T14     retired   -

in_stock: 1
in_use: 2
repair: 1
retired: 1
```

---

## Tests I carried out

### Test 1: The test suite

```powershell
python -m pytest -v
```

**What I saw** (shortened):

```
platform win32 -- Python 3.14.7, pytest-9.1.1, pluggy-1.7.0 -- C:\fastapi-asset-register\.venv\Scripts\python.exe
collected 17 items

test_assets.py::test_new_asset_defaults_to_in_stock PASSED
test_assets.py::test_tag_is_tidied_up PASSED
test_assets.py::test_badly_formed_tags_are_rejected[0001] PASSED
test_assets.py::test_badly_formed_tags_are_rejected[AST-1] PASSED
test_assets.py::test_badly_formed_tags_are_rejected[AST-00001] PASSED
test_assets.py::test_badly_formed_tags_are_rejected[XYZ-0001] PASSED
test_assets.py::test_badly_formed_tags_are_rejected[] PASSED
...
test_assets.py::test_count_by_status PASSED

17 passed in 0.25s
```

There are 13 test functions. The bad-tags test runs once for each of its five values, which makes 17.

### Test 2: Breaking the code on purpose

I simulated a colleague "simplifying" the tag rule, changing `\d{4}` (exactly four digits) to `\d+` (one or more digits):

```python
TAG_PATTERN = re.compile(r"AST-\d+")
```

```powershell
python -m pytest -q
```

**What I saw** (shortened):

```
...FF............
____________ test_badly_formed_tags_are_rejected[AST-1] ____________

bad_tag = 'AST-1'
>       with pytest.raises(ValueError, match="must look like AST-0001"):
E       Failed: DID NOT RAISE ValueError

FAILED test_assets.py::test_badly_formed_tags_are_rejected[AST-1] - Failed: DID NOT RAISE ValueError
FAILED test_assets.py::test_badly_formed_tags_are_rejected[AST-00001] - Failed: DID NOT RAISE ValueError
2 failed, 15 passed in 0.34s
```

The tests named the exact rule that had broken and the exact values that now got through, and showed that nothing else was affected. I put the pattern back and ran them again:

```
17 passed in 0.08s
```

Nobody has to remember the tag format. The tests remember it, and in Lab 04 they will run automatically on every push.

---

## Issues I hit and how I fixed them

### 1. PowerShell blocked the activation script

**Symptom.** Running `.\.venv\Scripts\Activate.ps1` failed because running scripts is disabled on the system.

**Root cause.** Windows PowerShell's execution policy blocks scripts by default, and activating a virtual environment runs a script.

**Fix.** I allowed scripts for the current PowerShell window only, without changing the computer's settings:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

The setting ends when the window closes, so I run it again in each new window before activating.

### 2. A `.gitignore` appeared inside `.venv`

**Symptom.** VS Code showed a `.gitignore` file inside the virtual environment folder that I had not created.

**Root cause.** Since Python 3.13, `venv` adds a `.gitignore` containing `*` to every new environment, so Git ignores it even if the project's own `.gitignore` forgets to.

**Fix.** None needed. I kept my own `.venv/` rule in the root `.gitignore` as well, which does no harm.

---

## Command reference

| Command | What it does |
|---|---|
| `py --version` | Shows the default Python version on Windows |
| `py -m venv .venv` | Creates a virtual environment in `.venv` |
| `.\.venv\Scripts\Activate.ps1` | Activates it in PowerShell |
| `python -m pip install <package>` | Installs a package into the active environment |
| `python -m pip install -r requirements.txt` | Installs the exact versions listed in the file |
| `python -m pytest -v` | Runs the tests and lists each one |
| `python -m pytest -q` | Runs the tests with a short report |

I use `python -m pip` and `python -m pytest` rather than `pip` and `pytest` on their own, so they always belong to the Python that is currently active.

## What I learned

- A virtual environment keeps each project's packages separate, and `requirements.txt` lets anyone rebuild it exactly.
- Type hints, dataclasses and enums are the building blocks FastAPI uses for validation, so they are worth getting right in plain Python first.
- Validating in `__post_init__` means an invalid object can never exist in the program.
- Tests are most valuable when something changes. Breaking the code on purpose showed exactly which rule failed and that nothing else did.
- `pytest.raises` tests the rules that reject bad data, which matter as much as the happy path.

---

## References

Official documentation I used while building and testing this lab.

| What I did | Documentation |
|---|---|
| Created the virtual environment | [venv: creation of virtual environments](https://docs.python.org/3/library/venv.html) |
| Allowed the activation script in one window | [about_Execution_Policies](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies) |
| Built the `Asset` model | [dataclasses](https://docs.python.org/3/library/dataclasses.html) |
| Restricted the status values | [enum.StrEnum](https://docs.python.org/3/library/enum.html#enum.StrEnum) |
| Checked the tag format | [re: regular expressions](https://docs.python.org/3/library/re.html) |
| Read and wrote files | [pathlib](https://docs.python.org/3/library/pathlib.html) and [json](https://docs.python.org/3/library/json.html) |
| Counted assets by status | [collections.Counter](https://docs.python.org/3/library/collections.html#collections.Counter) |
| Wrote the first tests | [Get started with pytest](https://docs.pytest.org/en/stable/getting-started.html) |
| Tested that bad data is rejected | [Assertions about expected exceptions](https://docs.pytest.org/en/stable/how-to/assert.html#assertions-about-expected-exceptions) |
| Ran one test against many values | [How to parametrize tests](https://docs.pytest.org/en/stable/how-to/parametrize.html) |
| Tested saving and loading safely | [How to use temporary directories in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) |