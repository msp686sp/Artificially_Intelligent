"""Tests for ``/api/config/*``.

Covers:

- Listing only ``*.yaml`` / ``*.yml`` files from the config dir.
- Reading returns content, parsed dict, and mtime.
- PUT round-trip persists new content; the next GET sees it.
- Path traversal / absolute-path / non-yaml / nested-dir rejections.
- PUT body that doesn't parse as YAML is rejected with 400.
- PUT body that parses to a list/scalar (not a dict) is rejected.
"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def test_list_files_returns_only_yaml(
    client: TestClient, tmp_config_dir: Path
) -> None:
    _write(tmp_config_dir / "filters.yaml", "filters: {}\n")
    _write(tmp_config_dir / "weights.yaml", "weights: {}\n")
    _write(tmp_config_dir / "watchlist.yaml", "watchlist: []\n")
    _write(tmp_config_dir / "ignore_me.csv", "a,b,c\n")

    r = client.get("/api/config/files")
    assert r.status_code == 200
    body = r.json()
    assert body == {"files": ["filters.yaml", "watchlist.yaml", "weights.yaml"]}


def test_list_files_empty_dir(client: TestClient, tmp_config_dir: Path) -> None:
    r = client.get("/api/config/files")
    assert r.status_code == 200
    assert r.json() == {"files": []}


def test_get_file_returns_content_and_parsed(
    client: TestClient, tmp_config_dir: Path
) -> None:
    p = tmp_config_dir / "filters.yaml"
    _write(p, "filters:\n  median_home_price:\n    min: 100\n    max: 250\n")
    r = client.get("/api/config/filters.yaml")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "filters.yaml"
    assert "median_home_price" in body["content"]
    assert body["parsed"]["filters"]["median_home_price"]["min"] == 100
    assert isinstance(body["mtime"], (int, float))
    assert body["mtime"] > 0


def test_get_missing_file_returns_404(client: TestClient) -> None:
    r = client.get("/api/config/missing.yaml")
    assert r.status_code == 404


def test_get_non_yaml_returns_400(client: TestClient) -> None:
    r = client.get("/api/config/secrets.env")
    assert r.status_code == 400


def test_get_traversal_returns_400(client: TestClient) -> None:
    r = client.get("/api/config/..%2Fpasswd.yaml")
    # Encoded slash should fail decode -> 400 or 404. We accept either
    # so long as we never reveal a parent-dir file.
    assert r.status_code in {400, 404}


def test_put_round_trip(client: TestClient, tmp_config_dir: Path) -> None:
    _write(tmp_config_dir / "weights.yaml", "old: true\n")
    new_content = "market_score:\n  yield: 0.5\n  demand: 0.5\n"
    r = client.put("/api/config/weights.yaml", json={"content": new_content})
    assert r.status_code == 204
    on_disk = (tmp_config_dir / "weights.yaml").read_text()
    assert on_disk == new_content

    r2 = client.get("/api/config/weights.yaml")
    body = r2.json()
    assert body["content"] == new_content
    assert body["parsed"]["market_score"]["yield"] == 0.5


def test_put_invalid_yaml_returns_400(
    client: TestClient, tmp_config_dir: Path
) -> None:
    _write(tmp_config_dir / "weights.yaml", "x: 1\n")
    # Unclosed flow-style mapping is a YAML parse error.
    r = client.put(
        "/api/config/weights.yaml",
        json={"content": "{a: 1, b: [unclosed\n"},
    )
    assert r.status_code == 400


def test_put_non_dict_yaml_returns_400(
    client: TestClient, tmp_config_dir: Path
) -> None:
    _write(tmp_config_dir / "watchlist.yaml", "x: 1\n")
    # A bare list is valid YAML but not a top-level mapping; reject.
    r = client.put(
        "/api/config/watchlist.yaml",
        json={"content": "- a\n- b\n"},
    )
    assert r.status_code == 400


def test_put_path_traversal_rejected(client: TestClient) -> None:
    r = client.put(
        "/api/config/..%2Fpasswd.yaml",
        json={"content": "x: 1\n"},
    )
    assert r.status_code in {400, 404}


def test_put_absolute_path_rejected(client: TestClient) -> None:
    r = client.put(
        "/api/config/%2Fetc%2Fpasswd.yaml",
        json={"content": "x: 1\n"},
    )
    assert r.status_code in {400, 404}


def test_put_non_yaml_extension_rejected(client: TestClient) -> None:
    r = client.put(
        "/api/config/notes.txt",
        json={"content": "anything"},
    )
    assert r.status_code == 400
