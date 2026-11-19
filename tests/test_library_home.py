"""The asset library lives outside the checkout, and an old in-checkout
library moves there on the first start."""

import io
import os
import zipfile

import config
from app import move_library_on_start
from utils.asset_home import default_assets_folder, move_legacy_library
from tests.test_template_api import upload


def test_the_default_library_is_not_under_the_repo():
    folder = default_assets_folder(environ={}, home="/Users/someone", platform="darwin")
    assert folder == "/Users/someone/Library/Application Support/EWOK/template_assets"
    real = default_assets_folder(environ={})
    assert not os.path.realpath(real).startswith(os.path.realpath(config.BASE_DIR) + os.sep)


def test_linux_uses_xdg_data_home_or_local_share():
    assert default_assets_folder(environ={}, home="/home/a", platform="linux") \
        == "/home/a/.local/share/EWOK/template_assets"
    assert default_assets_folder(environ={"XDG_DATA_HOME": "/data"}, home="/home/a", platform="linux") \
        == "/data/EWOK/template_assets"


def test_ewok_assets_dir_overrides_the_default(tmp_path):
    assert default_assets_folder(environ={"EWOK_ASSETS_DIR": str(tmp_path / "lib")}) == str(tmp_path / "lib")
    assert default_assets_folder(environ={"EWOK_ASSETS_DIR": "~/lib"}, home="/h") \
        == os.path.join(os.path.expanduser("~"), "lib")


def _legacy(tmp_path):
    legacy = tmp_path / "checkout" / "template_assets"
    (legacy / ".trash").mkdir(parents=True)
    (legacy / "logo.png").write_bytes(b"logo")
    (legacy / ".trash" / "old.1.png").write_bytes(b"old")
    return legacy


def test_an_old_library_moves_with_its_trash_and_says_so(tmp_path):
    legacy, new = _legacy(tmp_path), tmp_path / "support" / "EWOK" / "template_assets"
    message = move_legacy_library(str(legacy), str(new))
    assert message == f"EWOK moved your asset library from {legacy} to {new}."
    assert not legacy.exists()
    assert (new / "logo.png").read_bytes() == b"logo"
    assert (new / ".trash" / "old.1.png").read_bytes() == b"old"
    # Said once: the next start finds nothing to move.
    assert move_legacy_library(str(legacy), str(new)) is None


def test_an_empty_new_folder_does_not_stop_the_move(tmp_path):
    legacy, new = _legacy(tmp_path), tmp_path / "new"
    new.mkdir()
    assert move_legacy_library(str(legacy), str(new)).startswith("EWOK moved")
    assert (new / "logo.png").exists()


def test_a_library_already_at_the_new_place_is_never_overwritten(tmp_path):
    legacy, new = _legacy(tmp_path), tmp_path / "new"
    new.mkdir()
    (new / "logo.png").write_bytes(b"newer")
    message = move_legacy_library(str(legacy), str(new))
    assert message == (f"Warning: EWOK uses the asset library at {new}. An older one is still at "
                       f"{legacy}: copy what you need from it, then remove it.")
    assert (new / "logo.png").read_bytes() == b"newer"
    assert (legacy / "logo.png").read_bytes() == b"logo"


def test_nothing_happens_without_an_old_library_or_when_they_are_the_same(tmp_path):
    assert move_legacy_library(str(tmp_path / "none"), str(tmp_path / "new")) is None
    legacy = _legacy(tmp_path)
    assert move_legacy_library(str(legacy), str(legacy)) is None
    assert (legacy / "logo.png").exists()


def test_the_ewok_command_moves_the_library_and_prints_one_line(tmp_path, monkeypatch, capsys):
    legacy, new = _legacy(tmp_path), tmp_path / "new"
    monkeypatch.setattr(config, "LEGACY_ASSETS_FOLDER", str(legacy))
    monkeypatch.setattr(config, "TEMPLATE_ASSETS_FOLDER", str(new))
    move_library_on_start()
    assert capsys.readouterr().out == f"EWOK moved your asset library from {legacy} to {new}.\n"
    move_library_on_start()
    assert capsys.readouterr().out == ""


def test_download_library_zips_every_asset_and_nothing_else(client, tmp_path):
    upload(client, "logo.png")
    upload(client, "photo.jpg", fmt="JPEG")
    upload(client, "gone.png")
    client.delete("/api/template/assets/gone")
    client.get("/api/template/assets/logo/thumb")
    resp = client.get("/api/template/assets.zip")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    assert "attachment" in resp.headers["Content-Disposition"]
    assert "ewok-asset-library" in resp.headers["Content-Disposition"]
    with zipfile.ZipFile(io.BytesIO(resp.data)) as library:
        assert sorted(library.namelist()) == ["logo.png", "photo.jpg"]
        assert library.read("logo.png") == (tmp_path / "template_assets" / "logo.png").read_bytes()


def test_download_library_of_an_empty_library_says_so(client):
    resp = client.get("/api/template/assets.zip")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "The asset library is empty."


def test_tests_never_point_at_the_real_library():
    assert config.LEGACY_ASSETS_FOLDER != os.path.join(config.BASE_DIR, "template_assets")
    assert config.TEMPLATE_ASSETS_FOLDER != default_assets_folder()
