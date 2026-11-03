import sys
from unittest.mock import MagicMock

# --- xbmc stub ---
xbmc = MagicMock()
xbmc.LOGDEBUG = 0
xbmc.LOGINFO = 1
xbmc.LOGWARNING = 2
xbmc.LOGERROR = 3
xbmc.LOGFATAL = 4

xbmc.log = MagicMock()
xbmc.translatePath = MagicMock(side_effect=lambda path: path)
xbmc.executeJSONRPC = MagicMock(return_value='{"result": {}}')
xbmc.getCondVisibility = MagicMock(return_value=False)
xbmc.getInfoLabel = MagicMock(return_value="")
xbmc.getLanguage = MagicMock(return_value="English")

class StubMonitor:
    def __init__(self):
        self.abort_requested = False
        self.call_count = 0

    def waitForAbort(self, timeout=0):
        self.call_count += 1
        return self.abort_requested

    def abortRequested(self):
        return self.abort_requested

xbmc.Monitor = StubMonitor

class StubPlayer:
    def __init__(self):
        self.isPlaying = MagicMock(return_value=False)
        self.isPlayingVideo = MagicMock(return_value=False)
        self.getTime = MagicMock(return_value=0.0)
        self.getTotalTime = MagicMock(return_value=0.0)

xbmc.Player = StubPlayer

# --- xbmcgui stub ---
xbmcgui = MagicMock()

class StubListItem:
    def __init__(self, label="", label2="", path="", **kwargs):
        self.label = label
        self.label2 = label2
        self.path = path
        self.properties = {}
        self.art = {}
        self.info = {}
        self.stream_info = {}

    def setLabel(self, label):
        self.label = label

    def setLabel2(self, label2):
        self.label2 = label2

    def setPath(self, path):
        self.path = path

    def setProperty(self, key, value):
        self.properties[key] = value

    def getProperty(self, key):
        return self.properties.get(key, "")

    def setArt(self, art):
        self.art.update(art)

    def setInfo(self, type, infoLabels):
        self.info.setdefault(type, {}).update(infoLabels)

    def addStreamInfo(self, type, values):
        self.stream_info.setdefault(type, {}).update(values)

xbmcgui.ListItem = StubListItem
xbmcgui.Window = MagicMock
xbmcgui.Dialog = MagicMock
xbmcgui.DialogProgress = MagicMock
xbmcgui.DialogProgressBG = MagicMock

# --- xbmcvfs stub ---
xbmcvfs = MagicMock()
xbmcvfs.translatePath = MagicMock(side_effect=lambda path: path)
xbmcvfs.exists = MagicMock(return_value=True)
xbmcvfs.mkdirs = MagicMock(return_value=True)
xbmcvfs.delete = MagicMock(return_value=True)

# --- xbmcaddon stub ---
xbmcaddon = MagicMock()

class StubAddon:
    def __init__(self, id=None):
        self.id = id or "plugin.video.chomiteca"
        self._settings = {}

    def getSetting(self, key):
        return self._settings.get(key, "")

    def setSetting(self, key, value):
        self._settings[key] = str(value)

    def getLocalizedString(self, id):
        return str(id)

    def getAddonInfo(self, name):
        if name == "id":
            return self.id
        if name == "name":
            return "Chomiteca"
        return "Chomiteca"

    def openSettings(self):
        pass

xbmcaddon.Addon = StubAddon

# --- xbmcplugin stub ---
xbmcplugin = MagicMock()
xbmcplugin.addDirectoryItem = MagicMock(return_value=True)
xbmcplugin.addDirectoryItems = MagicMock(return_value=True)
xbmcplugin.endOfDirectory = MagicMock(return_value=True)
xbmcplugin.setResolvedUrl = MagicMock(return_value=True)
xbmcplugin.addSortMethod = MagicMock(return_value=True)

# Inject stubs into sys.modules
for mod_name, mod in [
    ("xbmc", xbmc),
    ("xbmcgui", xbmcgui),
    ("xbmcvfs", xbmcvfs),
    ("xbmcaddon", xbmcaddon),
    ("xbmcplugin", xbmcplugin),
]:
    sys.modules.setdefault(mod_name, mod)
