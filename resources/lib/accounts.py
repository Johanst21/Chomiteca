# -*- coding: utf-8 -*-
"""Cuentas de Chomikuj. Kodi no ofrece almacén seguro: el fichero queda en el perfil
del addon con permisos 0600 donde el SO lo permita, y la contraseña no se registra nunca."""
import json
import os
import uuid

from . import kodiutils as k

ACCOUNTS_FILE = os.path.join(k.PROFILE, "accounts.json")


def load():
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, list) else []
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as exc:
        k.log("accounts.json ilegible: %s" % exc, k.xbmc.LOGERROR)
        return []


def save(accounts):
    os.makedirs(k.PROFILE, exist_ok=True)
    tmp = ACCOUNTS_FILE + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(accounts, fh, indent=2, ensure_ascii=False)
    os.replace(tmp, ACCOUNTS_FILE)  # escritura atómica: no deja el JSON a medias


def add(username, password, label=""):
    accounts = load()
    account = {
        "id": uuid.uuid4().hex,
        "username": username,
        "password": password,
        "label": label or username,
    }
    accounts.append(account)
    save(accounts)
    return account


def remove(account_id):
    save([a for a in load() if a.get("id") != account_id])


def get(account_id):
    return next((a for a in load() if a.get("id") == account_id), None)


def active():
    account_id = k.ADDON.getSetting("active_account_id")
    return get(account_id) if account_id else None


def set_active(account_id):
    k.ADDON.setSetting("active_account_id", account_id)
