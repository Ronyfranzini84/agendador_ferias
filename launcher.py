import os
import socket
import sys
import threading
import webbrowser

from streamlit.web import cli as stcli

from app_paths import caminho_recurso


def obter_ip_local():
    conexao = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        conexao.connect(("8.8.8.8", 80))
        return conexao.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        conexao.close()


def abrir_navegador(porta):
    webbrowser.open(f"http://127.0.0.1:{porta}")


def main():
    porta = int(os.getenv("AGENDADOR_PORT", "8501"))
    host = os.getenv("AGENDADOR_HOST", "0.0.0.0")
    app_path = str(caminho_recurso("main.py"))

    ip_local = obter_ip_local()
    print("Agendador de Ferias iniciado.")
    print(f"Acesso neste computador: http://127.0.0.1:{porta}")
    print(f"Compartilhe na rede local: http://{ip_local}:{porta}")
    print("Se o Firewall do Windows perguntar, permita acesso em rede privada.")

    threading.Timer(2, abrir_navegador, args=(porta,)).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        f"--server.port={porta}",
        f"--server.address={host}",
        "--server.headless=true",
        "--global.developmentMode=false",
        "--browser.gatherUsageStats=false",
    ]
    raise SystemExit(stcli.main())


if __name__ == "__main__":
    main()