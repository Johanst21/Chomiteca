# -*- coding: utf-8 -*-
"""Gestión de cuentas (añadir, borrar, renombrar, activar)."""
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
import os, re, sys, time, traceback, unicodedata, sqlite3, stat
import urllib.request, urllib.parse, urllib.error
import random, threading, time as _time, json
from xml.sax.saxutils import escape as _xml_escape
from html.parser import HTMLParser
import html
from urllib.parse import urlparse
from http.cookiejar import MozillaCookieJar

from resources.lib.t0mm0 import Net, Addon
from resources.lib.dictionary import dictionary
from resources.lib import kodiutils as k
from resources.lib import auth, player, resolver, strings
from resources.lib import cache as cache_mod, metadata, playstate, store
from resources.lib import downloadqueue as dq
from resources.lib.session import make_session, describe_error, backoff
from resources.lib import state as st

from resources.lib.common import DIALOG_MESSAGE, cookies, get_active_account_details, load_accounts, notify, save_accounts, selfAddon, set_active_account_and_relogin, traducao, update_global_user_refs


def import_cookies_flow(username, session=None):
    """Interactive cookie import. Returns (success, message_key):
       success: True if cookies were imported AND verified.
       message_key: short reason for success/failure (for notify).
    """
    if session is None:
        session = make_session()

    dialog = xbmcgui.Dialog()
    options = [
        strings.t(40404),  # "Paste cookie string"
        strings.t(40405),  # "Pick cookies.txt file"
        strings.t(40406),  # "Cancel"
    ]
    choice = dialog.select(strings.t(40403), options)

    imported_count = 0
    if choice == 0:
        kb = xbmc.Keyboard('', strings.t(40404))
        kb.doModal()
        if not kb.isConfirmed() or not kb.getText():
            return False, "cancelled"
        raw_cookie = kb.getText().strip()
        if not raw_cookie:
            return False, "cancelled"
        imported_count, _ = session.set_raw_cookie_string(raw_cookie)
    elif choice == 1:
        selected = DIALOG_MESSAGE.browse(1, strings.t(40405), 'files', mask='.txt|.cookies')
        if isinstance(selected, list):
            selected = selected[0] if selected else ''
        if not selected:
            return False, "cancelled"
        imported_count, _ = session.import_mozilla_cookies(selected)
    else:
        return False, "cancelled"

    if imported_count == 0:
        notify(strings.t(40409), error=True)
        return False, "no_cookies_imported"

    if auth.verify_session(session, username):
        notify(strings.t(40407))
        return True, "ok"

    if DIALOG_MESSAGE.yesno(strings.t(40403), strings.t(40410)):
        return import_cookies_flow(username, session=session)

    return False, "verify_failed"


def add_new_account_ui():
    kb = xbmc.Keyboard('', traducao(40088))
    kb.doModal()
    if not kb.isConfirmed() or not kb.getText(): return
    new_username = kb.getText()

    store_password_setting = k.ADDON.getSetting("store_password")
    if store_password_setting == "":
        store_password = True
    else:
        store_password = store_password_setting.lower() == "true"

    if store_password:
        kb = xbmc.Keyboard('', traducao(40089), hidden=True)
        kb.doModal()
        if not kb.isConfirmed() or not kb.getText(): return
        new_password = kb.getText()
        auth_method = "password"
    else:
        new_password = ""
        auth_method = "cookies"

    kb = xbmc.Keyboard(new_username, traducao(40090))
    kb.doModal()
    new_label = kb.getText() if kb.isConfirmed() and kb.getText() else new_username

    accounts = load_accounts()
    new_id = new_username + "_" + str(int(time.time()))
    for acc_existing in accounts:
        if acc_existing.get('username') == new_username:
            if not DIALOG_MESSAGE.yesno(traducao(40091), traducao(10105)):
                return
            break
    new_account_details = {
        "id": new_id,
        "username": new_username,
        "password": new_password,
        "label": new_label,
        "auth_method": auth_method,
    }
    accounts.append(new_account_details)
    if save_accounts(accounts):
        notify(traducao(40100).format(new_label))
        if auth_method == "cookies":
            ok, reason = import_cookies_flow(new_username)
            if ok:
                if len(accounts) == 1 or not selfAddon.getSetting('active_account_id'):
                    set_active_account_and_relogin(new_id, account_details_provided=new_account_details)
                else:
                    xbmc.executebuiltin("Container.Refresh")
            else:
                if reason == "cancelled":
                    notify(strings.t(40413))
                else:
                    notify(strings.t(40408))
                xbmc.executebuiltin("Container.Refresh")
                return
        else:
            if len(accounts) == 1 or not selfAddon.getSetting('active_account_id'):
                set_active_account_and_relogin(new_id, account_details_provided=new_account_details)
            else:
                xbmc.executebuiltin("Container.Refresh")
    else:
        notify(traducao(40101), error=True)


def remove_account(account_id_to_remove):
    accounts = load_accounts()
    accounts_new = [acc for acc in accounts if acc.get('id') != account_id_to_remove]
    if len(accounts) == len(accounts_new):
        notify(traducao(40097).format(account_id_to_remove), error=True)
        return
    if save_accounts(accounts_new):
        notify(traducao(40102))
        current_active_id = selfAddon.getSetting('active_account_id')
        if current_active_id == account_id_to_remove:
            selfAddon.setSetting('active_account_id', '')
            update_global_user_refs(None)
            if os.path.exists(cookies):
                try: os.remove(cookies)
                except: pass
        xbmc.executebuiltin("Container.Refresh")
    else:
        notify(traducao(40103), error=True)


def manage_accounts_ui():
    accounts = load_accounts()
    active_id = selfAddon.getSetting('active_account_id')
    options_display_list = [traducao(40082)]
    account_map_idx_to_id = {}
    for idx, acc in enumerate(accounts):
        acc_id = acc.get('id', f"no_id_internal_{idx}")
        label = acc.get('label', acc.get('username', traducao(40023).strip()[:-3]))
        display_label_item = f"{label}"
        if acc_id == active_id:
            display_label_item += f" [COLOR green]({traducao(30149)})[/COLOR]"
        options_display_list.append(display_label_item)
        account_map_idx_to_id[len(options_display_list)-1] = acc_id
    dialog = xbmcgui.Dialog()
    choice_idx = dialog.select(traducao(40080), options_display_list)
    if choice_idx == -1:
        return
    elif choice_idx == 0:
        add_new_account_ui()
    else:
        selected_account_id = account_map_idx_to_id.get(choice_idx)
        if selected_account_id:
            selected_account = None
            for acc_detail_lookup in accounts:
                if acc_detail_lookup.get('id') == selected_account_id:
                    selected_account = acc_detail_lookup
                    break
            if selected_account is None:
                notify(traducao(40129).format(traducao(40022)), error=True)
                return

            selected_account_label = selected_account.get('label', selected_account.get('username', traducao(40023).strip()[:-3]))
            selected_account_username = selected_account.get('username', '')
            is_cookie_account = selected_account.get('auth_method') == 'cookies'

            sub_options_list = [traducao(40083)]
            if selected_account_id == active_id:
                sub_options_list[0] = traducao(40084)
            sub_options_list.append(traducao(40085))
            if is_cookie_account:
                sub_options_list.append(strings.t(40411))
            sub_options_list.append(traducao(40086))

            sub_choice_idx = dialog.select(f"{traducao(40022).split(' ')[0]} {traducao(40022).split(' ')[1]}: {selected_account_label}", sub_options_list)

            if sub_choice_idx == 0:
                set_active_account_and_relogin(selected_account_id)
            elif sub_choice_idx == 1:
                edit_account_label_ui(selected_account_id, selected_account_label, selected_account_username)
            elif is_cookie_account and sub_choice_idx == 2:
                if selected_account_id != active_id:
                    if not DIALOG_MESSAGE.yesno(strings.t(40411), strings.t(40412)):
                        return
                    set_active_account_and_relogin(selected_account_id)
                import_cookies_flow(selected_account_username)
            elif (is_cookie_account and sub_choice_idx == 3) or (not is_cookie_account and sub_choice_idx == 2):
                if DIALOG_MESSAGE.yesno(traducao(40087), f"{traducao(10105).split('?')[0]} {traducao(40086).lower()} '{selected_account_label}'?"):
                    remove_account(selected_account_id)
        else:
            notify(traducao(40129).format(traducao(40022)), error=True)


def edit_account_label_ui(account_id_to_edit, current_label, account_username):
    dialog_title = f"{traducao(40085)} {traducao(40054).lower()} '{account_username}'"
    default_text = current_label
    kb = xbmc.Keyboard(default_text, dialog_title)
    kb.doModal()
    if kb.isConfirmed():
        new_label = kb.getText()
        if not new_label:
            notify(traducao(40092), error=True)
            return
        if new_label == current_label:
            notify(traducao(40093))
            return
        accounts = load_accounts()
        account_found = False
        for acc in accounts:
            if acc.get('id') == account_id_to_edit:
                acc['label'] = new_label
                account_found = True
                break
        if account_found:
            if save_accounts(accounts):
                notify(traducao(40104).format(new_label))
                active_id_check = selfAddon.getSetting('active_account_id')
                if active_id_check == account_id_to_edit:
                    active_account_details = get_active_account_details()
                    if active_account_details:
                         update_global_user_refs(active_account_details)
                xbmc.executebuiltin("Container.Refresh")
            else:
                notify(traducao(40105), error=True)
        else:
            notify(traducao(40097).format(account_id_to_edit), error=True)
    else:
        notify(traducao(40094))
