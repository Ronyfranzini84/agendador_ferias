import os
import shutil
import sys
from pathlib import Path


APP_DIR_NAME = "AgendadorFerias"


def _esta_empacotado():
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def pasta_recursos():
    if _esta_empacotado():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def caminho_recurso(nome_arquivo):
    return pasta_recursos() / nome_arquivo


def pasta_dados_usuario():
    if not _esta_empacotado():
        return Path(__file__).resolve().parent

    base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
    destino = base / APP_DIR_NAME
    destino.mkdir(parents=True, exist_ok=True)
    return destino


def garantir_arquivo_gravavel(nome_arquivo):
    if not _esta_empacotado():
        return caminho_recurso(nome_arquivo)

    destino = pasta_dados_usuario() / nome_arquivo
    if destino.exists():
        return destino

    origem = caminho_recurso(nome_arquivo)
    if origem.exists():
        shutil.copy2(origem, destino)

    return destino