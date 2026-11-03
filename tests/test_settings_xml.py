import xml.etree.ElementTree as ET
from pathlib import Path


def test_settings_xml_well_formed():
    root = Path(__file__).parent.parent
    ET.parse(root / "resources" / "settings.xml")


def test_settings_no_empty_default():
    root = Path(__file__).parent.parent
    tree = ET.parse(root / "resources" / "settings.xml")
    bad = []
    for s in tree.iter("setting"):
        default = s.find("default")
        if default is not None and (default.text is None or default.text == ""):
            bad.append(s.get("id"))
    assert not bad, f"Settings con default vacío: {bad}"
