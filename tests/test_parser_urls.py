import os
from unittest.mock import patch
import pytest

from resources.lib import listing


def test_returnconteudo_parses_absolute_urls():
    fixture_path = os.path.join(os.path.dirname(__file__), 'fixtures', 'folder_normal.html')
    with open(fixture_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # Test with return_file_list=True
    file_list = listing.ReturnConteudo(
        conteudo_text_param=html,
        color_param='',
        url2_param='https://chomikuj.pl/Sechel/Prueba',
        deFora_param=False,
        return_file_list=True,
    )
    assert len(file_list) > 0
    assert len(file_list) == 30

    # Test with return_file_list=False (calls addCont)
    with patch.object(listing, 'addCont') as mock_add_cont:
        listing.ReturnConteudo(
            conteudo_text_param=html,
            color_param='',
            url2_param='https://chomikuj.pl/Sechel/Prueba',
            deFora_param=False,
            return_file_list=False,
        )
        assert mock_add_cont.call_count == 30
