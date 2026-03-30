@echo off
REM Build PDFMarkerTool.exe — PDF Marker app only (see pdf_marker/).
cd /d "%~dp0"
python -m pip install --upgrade pip pyinstaller pymupdf Pillow
pyinstaller --noconfirm --distpath=dist --workpath=build\pdf_marker pdf_marker\pdf_marker.spec
echo.
echo Output: dist\PDFMarkerTool.exe
pause
