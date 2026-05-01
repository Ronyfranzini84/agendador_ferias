@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Ambiente virtual nao encontrado em .venv
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m pip install pyinstaller

pyinstaller ^
  --noconfirm ^
  --clean ^
  --name AgendadorFerias ^
  --onefile ^
  --collect-data streamlit ^
  --copy-metadata streamlit ^
  --hidden-import streamlit.web.cli ^
  --add-data "main.py;." ^
  --add-data "bd_crud.py;." ^
  --add-data "envio_email.py;." ^
  --add-data "app_paths.py;." ^
  --add-data "calendar_options.json;." ^
  --add-data "wave.png;." ^
  --add-data "bd_usuarios.sqlite;." ^
  launcher.py

echo.
echo Executavel gerado em dist\AgendadorFerias.exe
endlocal