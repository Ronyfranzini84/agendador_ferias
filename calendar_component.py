from pathlib import Path

import streamlit.components.v1 as components

from app_paths import caminho_recurso


def _resolver_build_dir():
    candidatos = [
        caminho_recurso("streamlit_calendar/frontend/build"),
        Path(__file__).resolve().parent / ".venv" / "Lib" / "site-packages" / "streamlit_calendar" / "frontend" / "build",
    ]
    for candidato in candidatos:
        if candidato.exists():
            return candidato
    return candidatos[0]


_component_func = components.declare_component("calendar", path=str(_resolver_build_dir()))


def calendar(
    events=None,
    options=None,
    custom_css="",
    callbacks=None,
    license_key="CC-Attribution-NonCommercial-NoDerivatives",
    key=None,
):
    return _component_func(
        events=events or [],
        options=options or {},
        custom_css=custom_css,
        callbacks=callbacks or ["dateClick", "eventClick", "eventChange", "eventsSet", "select"],
        license_key=license_key,
        key=key,
        default={},
    )