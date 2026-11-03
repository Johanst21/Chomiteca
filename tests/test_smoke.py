import xbmc
import xbmcaddon


def test_import_session():
    import resources.lib.session  # noqa: F401


def test_xbmcaddon_get_setting():
    assert xbmcaddon.Addon().getSetting("x") == ""


def test_xbmc_monitor_wait_for_abort():
    assert xbmc.Monitor().waitForAbort(0.01) is False
