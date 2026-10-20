"""Tests for the Asset Register API, run against the test database."""

import pytest

LAPTOP = {"name": "Dell Latitude 7450", "type": "laptop", "assigned_to": "Finance team"}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_register_starts_empty(client):
    assert client.get("/assets").json() == []


def test_create_asset(client):
    response = client.post("/assets", json=LAPTOP)

    assert response.status_code == 201
    body = response.json()
    assert body["id"] == 1
    assert body["name"] == "Dell Latitude 7450"
    assert body["assigned_to"] == "Finance team"
    assert "added" in body


def test_assigned_to_is_optional(client):
    response = client.post("/assets", json={"name": "HP LaserJet Pro", "type": "printer"})
    assert response.status_code == 201
    assert response.json()["assigned_to"] is None


def test_spaces_are_trimmed(client):
    response = client.post("/assets", json={"name": "  Spare monitor ", "type": " monitor"})
    assert response.json()["name"] == "Spare monitor"
    assert response.json()["type"] == "monitor"


@pytest.mark.parametrize(
    "bad_asset",
    [
        {"type": "laptop"},
        {"name": "Laptop"},
        {"name": "   ", "type": "laptop"},
        {"name": "Laptop", "type": ""},
        {"name": "x" * 101, "type": "laptop"},
    ],
    ids=["no name", "no type", "blank name", "empty type", "name too long"],
)
def test_invalid_assets_are_rejected(client, bad_asset):
    response = client.post("/assets", json=bad_asset)
    assert response.status_code == 422
    assert client.get("/assets").json() == []


def test_client_cannot_choose_the_id(client):
    response = client.post("/assets", json={**LAPTOP, "id": 999})
    assert response.json()["id"] == 1


def test_get_one_asset(client):
    client.post("/assets", json=LAPTOP)
    response = client.get("/assets/1")
    assert response.status_code == 200
    assert response.json()["name"] == "Dell Latitude 7450"


def test_missing_asset_returns_404(client):
    response = client.get("/assets/42")
    assert response.status_code == 404
    assert response.json() == {"detail": "Asset 42 not found"}


def test_list_is_in_id_order(client):
    for name in ["First", "Second", "Third"]:
        client.post("/assets", json={"name": name, "type": "laptop"})

    names = [asset["name"] for asset in client.get("/assets").json()]
    assert names == ["First", "Second", "Third"]


def test_update_keeps_id_and_added_date(client):
    created = client.post("/assets", json=LAPTOP).json()

    response = client.put("/assets/1", json={"name": "Dell Latitude 7450", "type": "laptop", "assigned_to": "Reception"})

    assert response.status_code == 200
    updated = response.json()
    assert updated["assigned_to"] == "Reception"
    assert updated["id"] == created["id"]
    assert updated["added"] == created["added"]


def test_update_missing_asset_returns_404(client):
    assert client.put("/assets/42", json=LAPTOP).status_code == 404


def test_delete_asset(client):
    client.post("/assets", json=LAPTOP)

    response = client.delete("/assets/1")

    assert response.status_code == 204
    assert client.get("/assets/1").status_code == 404


def test_delete_missing_asset_returns_404(client):
    assert client.delete("/assets/42").status_code == 404


def test_ids_are_never_reused(client):
    client.post("/assets", json=LAPTOP)
    client.delete("/assets/1")
    response = client.post("/assets", json=LAPTOP)
    assert response.json()["id"] == 2


def test_asset_is_saved_in_the_database(client, database_rows):
    """Read the table directly with SQL, without going through the API."""
    client.post("/assets", json=LAPTOP)
    assert database_rows() == [("Dell Latitude 7450", "laptop", "Finance team")]