import os
import json
from unittest.mock import MagicMock, patch
import pytest

import xbmc
import xbmcgui
import xbmcvfs
from resources.lib import library
from resources.lib import search
from resources.lib import downloads
from resources.lib.library import WalkIncomplete


def test_walker_incomplete_no_prune():
    """1. Walker incompleto -> no poda.
    Mockear walk_folder_files para que devuelva 2 entradas y luego lance WalkIncomplete(3).
    Mockear xbmcvfs.delete.
    Llamar create_strm_files_recursive_chomiteca con prune=True.
    Verificar que NO se llamó a xbmcvfs.delete.
    """
    entries = [
        {'rel_dir': 'sub', 'title': 'Movie 1', 'ext': '.mkv', 'size': '100 MB', 'file_id': '1', 'url': 'http://chomikuj.pl/m1'},
        {'rel_dir': 'sub', 'title': 'Movie 2', 'ext': '.mkv', 'size': '200 MB', 'file_id': '2', 'url': 'http://chomikuj.pl/m2'},
    ]

    def mock_walk(*args, **kwargs):
        for e in entries:
            yield e
        raise WalkIncomplete(3)

    # Preparamos strm_index simulando que había un stale
    # base_output_dir = "/media/strm"
    # stale path en indexed
    indexed_dict = {
        "/media/strm/sub/Movie 1.strm": "plugin://plugin.video.chomiteca/?url=http%3A%2F%2Fchomikuj.pl%2Fm1&mode=25&name=Movie+1.mkv",
        "/media/strm/sub/Old Movie.strm": "plugin://plugin.video.chomiteca/?url=http%3A%2F%2Fchomikuj.pl%2Fold&mode=25&name=Old+Movie.mkv",
    }

    mock_db_cursor = MagicMock()
    mock_db_cursor.execute.return_value = mock_db_cursor
    mock_db_cursor.fetchall.return_value = list(indexed_dict.items())
    mock_db_ctx = MagicMock()
    mock_db_ctx.__enter__.return_value = mock_db_cursor
    mock_db_ctx.__exit__.return_value = False

    with patch.object(library, 'walk_folder_files', side_effect=mock_walk), \
         patch.object(library.selfAddon, 'getSetting', side_effect=lambda k: 'true' if k == 'strm_prune' else ''), \
         patch.object(library.store, 'db', return_value=mock_db_ctx), \
         patch.object(xbmcvfs, 'delete') as mock_delete, \
         patch.object(library, '_ensure_dir', return_value=True), \
         patch.object(library, '_write_text', return_value=True):

        library.create_strm_files_recursive_chomiteca("http://chomikuj.pl/user/folder", "/media/strm", None)

        mock_delete.assert_not_called()


def test_walker_complete_missing_files_prunes():
    """2. Walker completo con archivos desaparecidos -> sí poda.
    Mockear walker completo con 3 archivos, indexed con 5 (2 desaparecidos).
    seen_paths >= 50% de indexed.
    Verificar que SÍ se intentó podar los 2 ausentes.
    """
    entries = [
        {'rel_dir': 'sub', 'title': 'M1', 'ext': '.mkv', 'size': '100 MB', 'file_id': '1', 'url': 'http://chomikuj.pl/m1'},
        {'rel_dir': 'sub', 'title': 'M2', 'ext': '.mkv', 'size': '200 MB', 'file_id': '2', 'url': 'http://chomikuj.pl/m2'},
        {'rel_dir': 'sub', 'title': 'M3', 'ext': '.mkv', 'size': '300 MB', 'file_id': '3', 'url': 'http://chomikuj.pl/m3'},
    ]

    p1 = os.path.join("/media/strm", "sub", "M1.strm")
    p2 = os.path.join("/media/strm", "sub", "M2.strm")
    p3 = os.path.join("/media/strm", "sub", "M3.strm")
    p_stale1 = os.path.join("/media/strm", "sub", "Old1.strm")
    p_stale2 = os.path.join("/media/strm", "sub", "Old2.strm")

    indexed_dict = {
        p1: "url1",
        p2: "url2",
        p3: "url3",
        p_stale1: "url4",
        p_stale2: "url5",
    }

    mock_db_cursor = MagicMock()
    mock_db_cursor.execute.return_value = mock_db_cursor
    mock_db_cursor.fetchall.return_value = list(indexed_dict.items())
    mock_db_ctx = MagicMock()
    mock_db_ctx.__enter__.return_value = mock_db_cursor
    mock_db_ctx.__exit__.return_value = False

    with patch.object(library, 'walk_folder_files', return_value=iter(entries)), \
         patch.object(library.selfAddon, 'getSetting', side_effect=lambda k: 'true' if k == 'strm_prune' else ''), \
         patch.object(library.store, 'db', return_value=mock_db_ctx), \
         patch.object(xbmcvfs, 'delete') as mock_delete, \
         patch.object(xbmcvfs, 'exists', return_value=False), \
         patch.object(library, '_ensure_dir', return_value=True), \
         patch.object(library, '_write_text', return_value=True):

        library.create_strm_files_recursive_chomiteca("http://chomikuj.pl/user/folder", "/media/strm", None)

        deleted_paths = [call.args[0] for call in mock_delete.call_args_list]
        assert p_stale1 in deleted_paths
        assert p_stale2 in deleted_paths
        assert len(deleted_paths) == 2


def test_insufficient_count_no_prune():
    """3. Recuento insuficiente -> no poda.
    Walker completo con 1 archivo, indexed con 10.
    seen_paths < 50% de indexed.
    Verificar que NO se podó.
    """
    entries = [
        {'rel_dir': 'sub', 'title': 'M1', 'ext': '.mkv', 'size': '100 MB', 'file_id': '1', 'url': 'http://chomikuj.pl/m1'},
    ]

    p1 = os.path.join("/media/strm", "sub", "M1.strm")
    indexed_dict = {p1: "url1"}
    for i in range(2, 11):
        indexed_dict[os.path.join("/media/strm", "sub", f"Old{i}.strm")] = f"url{i}"

    mock_db_cursor = MagicMock()
    mock_db_cursor.execute.return_value = mock_db_cursor
    mock_db_cursor.fetchall.return_value = list(indexed_dict.items())
    mock_db_ctx = MagicMock()
    mock_db_ctx.__enter__.return_value = mock_db_cursor
    mock_db_ctx.__exit__.return_value = False

    with patch.object(library, 'walk_folder_files', return_value=iter(entries)), \
         patch.object(library.selfAddon, 'getSetting', side_effect=lambda k: 'true' if k == 'strm_prune' else ''), \
         patch.object(library.store, 'db', return_value=mock_db_ctx), \
         patch.object(xbmcvfs, 'delete') as mock_delete, \
         patch.object(xbmcvfs, 'exists', return_value=False), \
         patch.object(library, '_ensure_dir', return_value=True), \
         patch.object(library, '_write_text', return_value=True):

        library.create_strm_files_recursive_chomiteca("http://chomikuj.pl/user/folder", "/media/strm", None)

        mock_delete.assert_not_called()


def test_build_index_incomplete_does_not_write_json():
    """4. _build_index con walker incompleto no escribe JSON:
    Mockear walker que lanza WalkIncomplete.
    Mockear open para detectar escritura.
    Verificar que no se escribió search_index_<user>.json, que notificó al usuario y que _build_index devolvió None.
    """
    def mock_walk(*args, **kwargs):
        yield {'is_dir': False, 'rel_dir': '', 'title': 'File1', 'ext': '.mp4', 'url': 'http://chomikuj.pl/f1', 'size': '1 MB'}
        raise WalkIncomplete(2)

    mock_progress = MagicMock()
    mock_progress.iscanceled.return_value = False

    with patch('resources.lib.library.walk_folder_files', side_effect=mock_walk), \
         patch.object(xbmcgui, 'DialogProgress', return_value=mock_progress), \
         patch('resources.lib.search.notify') as mock_notify, \
         patch('builtins.open', MagicMock()) as mock_file_open:

        res = search._build_index("testuser")
        assert res is None
        mock_file_open.assert_not_called()
        mock_notify.assert_called_once()


def test_download_folder_incomplete_does_not_raise():
    """5. download_folder con walker incompleto no propaga excepción:
    Mockear walker que lanza WalkIncomplete a la mitad.
    Verificar que download_folder no lanza y que se encolaron los que sí se obtuvieron.
    """
    entries = [
        {'rel_dir': 'folder', 'title': 'File 1', 'ext': '.zip', 'url': 'http://chomikuj.pl/f1'},
        {'rel_dir': 'folder', 'title': 'File 2', 'ext': '.zip', 'url': 'http://chomikuj.pl/f2'},
    ]

    def mock_walk(*args, **kwargs):
        for e in entries:
            yield e
        raise WalkIncomplete(2)

    with patch.object(downloads, 'walk_folder_files', side_effect=mock_walk), \
         patch.object(downloads, '_ensure_download_dir', return_value="/downloads"), \
         patch.object(downloads.dq, 'enqueue') as mock_enqueue, \
         patch.object(downloads, 'notify') as mock_notify:

        downloads.download_folder("http://chomikuj.pl/folder", "MyFolder")

        assert mock_enqueue.call_count == 2
        mock_notify.assert_called_once()
        notification_text = mock_notify.call_args[0][0]
        assert "2" in notification_text
