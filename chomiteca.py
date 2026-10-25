# -*- coding: utf-8 -*-
"""Punto de entrada mínimo: toda la lógica vive en resources/lib."""
import sys

from resources.lib import router

if __name__ == "__main__":
    router.run(sys.argv)
