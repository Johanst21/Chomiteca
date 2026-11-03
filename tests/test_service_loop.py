# -*- coding: utf-8 -*-
import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from resources.lib import service


@pytest.fixture(autouse=True)
def reset_service_state():
    service._warm_up_started = False
    yield
    service._warm_up_started = False


def _join_warm_up_thread(timeout=0.5):
    for thread in threading.enumerate():
        if thread.name == "ChomitecaWarmUp":
            thread.join(timeout=timeout)


def test_run_survives_tick_exception():
    # Mockear MONITOR.waitForAbort para devolver False en los 3 primeros ticks y True en el 4º
    mock_monitor = MagicMock()
    mock_monitor.waitForAbort.side_effect = [False, False, False, True]

    # Mockear player.tick para que lance RuntimeError en el 2º tick y no haga nada en el resto
    mock_player = MagicMock()
    mock_player.tick.side_effect = [None, RuntimeError("error en tick"), None]

    with patch("resources.lib.service.xbmc.Monitor", return_value=mock_monitor), \
         patch("resources.lib.service.playstate.PlayerMonitor", return_value=mock_player), \
         patch("resources.lib.service.k.log") as mock_log:
        service.run()

    # Verificar: run() no propaga excepción, player.tick fue llamado 3 veces
    assert mock_player.tick.call_count == 3
    # Verificar que el error fue registrado en el log
    mock_log.assert_any_call("service tick: RuntimeError('error en tick')", 3)


def test_warm_up_called_once():
    # Mockear _warm_up con MagicMock para contar llamadas
    mock_warm_up = MagicMock()

    # MONITOR que permite 30 ticks antes de abortar
    mock_monitor = MagicMock()
    mock_monitor.waitForAbort.side_effect = [False] * 30 + [True]

    mock_player = MagicMock()
    mock_manager_cls = MagicMock()

    with patch("resources.lib.service.xbmc.Monitor", return_value=mock_monitor), \
         patch("resources.lib.service.playstate.PlayerMonitor", return_value=mock_player), \
         patch("resources.lib.service._warm_up", mock_warm_up), \
         patch("resources.lib.service.downloadqueue.Manager", mock_manager_cls):
        service.run()

    _join_warm_up_thread(timeout=0.5)

    assert mock_warm_up.call_count == 1


def test_warm_up_exception_isolated():
    mock_warm_up = MagicMock(side_effect=RuntimeError("warm up falló"))

    # MONITOR que corre hasta después del tick 15 (p.ej. 20 ticks) y luego aborta
    mock_monitor = MagicMock()
    mock_monitor.waitForAbort.side_effect = [False] * 20 + [True]

    mock_player = MagicMock()
    mock_manager_cls = MagicMock()

    with patch("resources.lib.service.xbmc.Monitor", return_value=mock_monitor), \
         patch("resources.lib.service.playstate.PlayerMonitor", return_value=mock_player), \
         patch("resources.lib.service._warm_up", mock_warm_up), \
         patch("resources.lib.service.downloadqueue.Manager", mock_manager_cls), \
         patch("resources.lib.service.k.log") as mock_log:
        service.run()

    _join_warm_up_thread(timeout=0.5)

    # Verificar: run() no propaga y player.tick sigue siendo llamado tras el fallo de _warm_up
    assert mock_warm_up.call_count == 1
    assert mock_player.tick.call_count == 20
    mock_log.assert_any_call("_warm_up: RuntimeError('warm up falló')", 3)
