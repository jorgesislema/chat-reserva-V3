"""Límites por edición: artículos y profesionales activos, visibles y aplicados."""
from __future__ import annotations

import os

LIMITE_ARTICULOS = int(os.getenv('CRM_LIMITE_ARTICULOS') or 100)
LIMITE_PROFESIONALES = int(os.getenv('CRM_LIMITE_PROFESIONALES') or 3)

MENSAJE_ARTICULOS = ('Esta edición admite hasta %d artículos activos. Desactive los que ya no '
                     'use o amplíe la edición para añadir más.' % LIMITE_ARTICULOS)
MENSAJE_PROFESIONALES = ('Esta edición admite hasta %d profesionales activos. Desactive a quien '
                         'ya no atienda o amplíe la edición para añadir más.'
                         % LIMITE_PROFESIONALES)
