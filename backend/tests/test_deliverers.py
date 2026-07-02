from app.services.deliverers import DownloadDeliverer, get_deliverer


def test_default_is_download():
    dl = get_deliverer()
    assert isinstance(dl, DownloadDeliverer)


def test_download_deliverer_always_available():
    res = get_deliverer().deliver("pw1", "prepared-worlds/pw1.zip")
    assert res.delivered is True
    assert "download" in res.detail.lower()
