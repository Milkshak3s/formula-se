import app.services.deliverers as d
from app.services.deliverers import (
    DownloadDeliverer,
    SftpDeliverer,
    get_deliverer,
)


def test_default_is_download(monkeypatch):
    monkeypatch.setattr(d.settings, "deliverer", "download")
    dl = get_deliverer()
    assert isinstance(dl, DownloadDeliverer)
    res = dl.deliver("pw1", "prepared-worlds/pw1.zip", "Match 1.zip")
    assert res.delivered is True


def test_sftp_selected_when_configured(monkeypatch):
    monkeypatch.setattr(d.settings, "deliverer", "sftp")
    assert isinstance(get_deliverer(), SftpDeliverer)


def test_sftp_without_host_fails_gracefully(monkeypatch):
    monkeypatch.setattr(d.settings, "deliverer", "sftp")
    monkeypatch.setattr(d.settings, "sftp_host", None)
    monkeypatch.setattr(d.settings, "sftp_username", None)
    res = get_deliverer().deliver("pw1", "prepared-worlds/pw1.zip", "x.zip")
    assert res.delivered is False
    assert "not configured" in res.detail


def test_safe_name():
    assert d._safe_name("Match 1: Finals").endswith(".zip")
    assert d._safe_name("clean.zip") == "clean.zip"
