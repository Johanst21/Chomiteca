import os
from unittest.mock import MagicMock, patch
import pytest

from resources.lib import listing
from resources.lib import state as st


@pytest.fixture(autouse=True)
def reset_state():
    old_params = getattr(st, 'params', {})
    old_addon = getattr(st, 'addon', None)
    st.params = {'url': 'https://chomikuj.pl/Sechel/Prueba'}
    mock_addon = MagicMock()
    mock_addon.load_data.return_value = None
    st.addon = mock_addon
    yield
    st.params = old_params
    st.addon = old_addon


def _run_paginas(html_content, current_url='https://chomikuj.pl/Sechel/Prueba'):
    st.params = {'url': current_url}
    with patch.object(listing, 'addDir') as mock_add_dir:
        listing.paginas(html_content)
        return mock_add_dir.call_args_list


def test_pagination_absolute_url():
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'folder_normal.html')
    with open(fixture_path, 'r', encoding='utf-8') as f:
        html = f.read()

    calls = _run_paginas(html)
    # folder_normal.html contains next link with https://chomikuj.pl/Sechel/Prueba,2
    # and disabled prev link (no <a> tag for prev)
    assert len(calls) == 1
    call_args = calls[0][0]
    # addDir(label, url, mode, icon, total, pasta)
    assert call_args[1] == 'https://chomikuj.pl/Sechel/Prueba,2'
    assert call_args[2] == 3


def test_pagination_relative_url():
    html = '<div class="paginator"><a href="/Sechel/Prueba,2" class="right" rel="2">następna strona »</a></div>'
    calls = _run_paginas(html)
    assert len(calls) == 1
    call_args = calls[0][0]
    assert call_args[1] == 'https://chomikuj.pl/Sechel/Prueba,2'


def test_pagination_no_false_positive():
    html = '<div class="dialogWindow"><a class="uploadMinimalize right greenButton" href="javascript:;"></a></div>'
    calls = _run_paginas(html)
    assert len(calls) == 0


def test_pagination_no_paginator():
    html = '<div><p>Empty folder or no pagination here.</p></div>'
    calls = _run_paginas(html)
    assert len(calls) == 0


def test_pagination_left():
    html = '<div class="paginator"><a href="/prev" class="left" rel="1">« poprzednia strona</a></div>'
    calls = _run_paginas(html)
    assert len(calls) == 1
    call_args = calls[0][0]
    assert call_args[1] == 'https://chomikuj.pl/prev'
    assert call_args[2] == 3


def test_pagination_absolute_url_prev():
    html = '<div class="paginator"><a href="https://chomikuj.pl/x/y,1" class="left" rel="1">« poprzednia strona</a></div>'
    calls = _run_paginas(html)
    assert len(calls) == 1
    call_args = calls[0][0]
    assert call_args[1] == 'https://chomikuj.pl/x/y,1'
    assert call_args[2] == 3
