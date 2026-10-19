"""A small asset register: the Python building blocks for the FastAPI labs."""

import json
import re
from collections import Counter
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

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


def load_assets(path: Path) -> list[Asset]:
    """Read assets from a JSON file. Every item is validated as it is loaded."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Asset(**item) for item in data]


def save_assets(assets: list[Asset], path: Path) -> None:
    """Write assets to a JSON file."""
    data = [asdict(asset) for asset in assets]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_by_tag(assets: list[Asset], tag: str) -> Asset | None:
    """Return the asset with this tag, or None. Ignores case and spaces."""
    wanted = tag.strip().upper()
    return next((asset for asset in assets if asset.tag == wanted), None)


def add_asset(assets: list[Asset], new: Asset) -> list[Asset]:
    """Return a new list with the asset added. Tags must be unique."""
    if find_by_tag(assets, new.tag) is not None:
        raise ValueError(f"{new.tag} is already in the register")
    return [*assets, new]


def count_by_status(assets: list[Asset]) -> dict[str, int]:
    """How many assets are in each status, for example {'in_use': 2}."""
    return dict(Counter(asset.status.value for asset in assets))


def main() -> None:
    path = Path(__file__).with_name("sample_assets.json")
    assets = load_assets(path)

    print(f"{'Tag':<10}{'Name':<24}{'Status':<10}Assigned to")
    for asset in assets:
        print(f"{asset.tag:<10}{asset.name:<24}{asset.status:<10}{asset.assigned_to or '-'}")

    print()
    for status, count in sorted(count_by_status(assets).items()):
        print(f"{status}: {count}")


if __name__ == "__main__":
    main()