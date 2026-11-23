"""Pacchetto core di Kiosk4UPlanner (Milestone v5.3)."""

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

__all__ = [
    'AVVISI_DI_STATO',
    'BACKOFF_BASE_SEC',
    'BACKOFF_MAX_SEC',
    'LIMITE_EVENTI_CINECA',
    'SOGLIA_ASSENZE_ANNULLAMENTO',
    'CinecaClient',
    'get_giorno_operativo',
    'get_tz_roma',
    'sanitize_id_str',
]
