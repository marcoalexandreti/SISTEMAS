"""Fontes disponíveis nos sistemas de destino."""
import os

FONTE_UI = 'Segoe UI' if os.name == 'nt' else 'Helvetica'
FONTE_CODIGO = 'Consolas' if os.name == 'nt' else 'Courier'
