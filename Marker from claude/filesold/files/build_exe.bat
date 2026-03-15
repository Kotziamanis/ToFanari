@echo off
echo ========================================
echo  PDF Marker Tool - Build EXE
echo ========================================
echo.

echo Εγκατασταση βιβλιοθηκων...
pip install PyMuPDF Pillow pyinstaller --quiet

echo.
echo Δημιουργια EXE...
pyinstaller --onefile --windowed --name "PDF_Marker_ToFanari" --icon=NONE pdf_marker.py

echo.
echo ========================================
if exist "dist\PDF_Marker_ToFanari.exe" (
    echo  ΕΠΙΤΥΧΙΑ! Το EXE ειναι στον φακελο dist\
    echo  dist\PDF_Marker_ToFanari.exe
) else (
    echo  ΣΦΑΛΜΑ - Κατι πηγε στραβα!
)
echo ========================================
pause
