"""Pacchetto core di Kiosk4UPlanner (Milestone v5.3)."""

from core.building_context import (
    ESTENSIONI_LOCANDINE,
    BuildingContext,
    chiave_ordinamento_naturale,
    rileva_formato_immagine,
)
from core.cineca_client import (
    AVVISI_DI_STATO,
    BACKOFF_BASE_SEC,
    BACKOFF_MAX_SEC,
    LIMITE_EVENTI_CINECA,
    SOGLIA_ASSENZE_ANNULLAMENTO,
    CinecaClient,
    get_giorno_operativo,
    get_tz_roma,
    sanitize_id_str,
)
from core.news_engine import TIMEOUT_FONTE_SEC, NewsEngine

__all__ = [
    'AVVISI_DI_STATO',
    'BACKOFF_BASE_SEC',
    'BACKOFF_MAX_SEC',
    'ESTENSIONI_LOCANDINE',
    'LIMITE_EVENTI_CINECA',
    'SOGLIA_ASSENZE_ANNULLAMENTO',
    'TIMEOUT_FONTE_SEC',
    'BuildingContext',
    'CinecaClient',
    'NewsEngine',
    'chiave_ordinamento_naturale',
    'get_giorno_operativo',
    'get_tz_roma',
    'rileva_formato_immagine',
    'sanitize_id_str',
]
