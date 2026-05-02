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
  --collect-all streamlit_calendar ^
  --collect-submodules streamlit ^
  --copy-metadata streamlit ^
  --hidden-import streamlit.web.cli ^
  --hidden-import streamlit_calendar ^
  --hidden-import main ^
  --hidden-import bd_crud ^
  --hidden-import envio_email ^
  --hidden-import app_paths ^
  --hidden-import groq_ai ^
  --hidden-import calendar_component ^
  --hidden-import groq ^
  --add-data "main.py;." ^
  --add-data "bd_crud.py;." ^
  --add-data "envio_email.py;." ^
  --add-data "app_paths.py;." ^
  --add-data "groq_ai.py;." ^
  --add-data "calendar_component.py;." ^
  --add-data "calendar_options.json;." ^
  --add-data "wave.png;." ^
  --add-data "bd_usuarios.sqlite;." ^
  --add-data ".venv\Lib\site-packages\streamlit_calendar\frontend\build;streamlit_calendar\frontend\build" ^
  launcher.py

echo.
echo Executavel gerado em dist\AgendadorFerias.exe
endlocal