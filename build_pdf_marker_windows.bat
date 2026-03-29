@echo off
REM Build PDFMarkerTool.exe on Windows (Python 3.10+ recommended).
cd /d "%~dp0"
python -m pip install --upgrade pip pyinstaller pymupdf Pillow
pyinstaller --noconfirm pdf_marker.spec
echo.
echo Output: dist\PDFMarkerTool.exe
pause
