@echo off
setlocal

echo ============================================================
echo  SubtitleForge - Developer Setup
echo  Builds the distributable EXE on your machine.
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found.
    pause & exit /b 1
)
echo [OK] Python found.

echo.
echo [1/5] Upgrading pip...
python -m pip install --upgrade pip --quiet

echo.
echo [2/5] Installing dependencies...
echo       Installing PyTorch CPU build (big download, be patient)...
pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet
echo       Installing Whisper...
pip install openai-whisper --quiet
echo       Installing PyInstaller...
pip install pyinstaller --quiet
echo [OK] Dependencies installed.

echo.
echo [3/5] Downloading Whisper 'small' model weights...
python -c "import whisper, os; os.makedirs('whisper_models', exist_ok=True); whisper.load_model('small', download_root='whisper_models'); print('[OK] Model ready.')"
if errorlevel 1 (
    echo [ERROR] Model download failed.
    pause & exit /b 1
)

echo.
echo [4/5] Locating ffmpeg...
where ffmpeg >nul 2>&1
if errorlevel 1 (
    echo ffmpeg not on PATH. Trying winget...
    winget install --id Gyan.FFmpeg -e --silent
    :: Refresh PATH for this session
    for /f "tokens=*" %%i in ('where ffmpeg 2^>nul') do (
        copy "%%i" "%~dp0ffmpeg.exe" >nul 2>&1
        echo [OK] ffmpeg copied to project folder.
        goto ffmpeg_ok
    )
    echo.
    echo [!] winget install succeeded but ffmpeg not found on PATH yet.
    echo     Close this window, reopen it, and run setup_dev.bat again.
    echo     OR manually copy ffmpeg.exe into this folder:
    echo     %~dp0
    pause & exit /b 1
) else (
    for /f "tokens=*" %%i in ('where ffmpeg') do (
        copy "%%i" "%~dp0ffmpeg.exe" >nul 2>&1
        echo [OK] ffmpeg found and copied to project folder.
        goto ffmpeg_ok
    )
)
:ffmpeg_ok

echo.
echo [5/5] Building EXE with PyInstaller...
echo       This will take several minutes. Do not close this window.
pyinstaller subtitler.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed.
    pause & exit /b 1
)

echo.
echo Copying model weights into distribution folder...
xcopy /E /I /Y "whisper_models" "dist\SubtitleForge\whisper_models\" >nul
copy /Y "icon.ico" "dist\SubtitleForge\icon.ico" >nul

echo.
echo Creating release ZIP...
powershell -Command "Compress-Archive -Path 'dist\SubtitleForge\*' -DestinationPath 'SubtitleForge_release.zip' -Force"
if errorlevel 1 (
    echo [WARNING] ZIP creation failed. Manually zip dist\SubtitleForge\ contents.
) else (
    echo [OK] SubtitleForge_release.zip created.
)

echo.
echo ============================================================
echo  BUILD COMPLETE
echo  Test: run dist\SubtitleForge\SubtitleForge.exe
echo  Release: upload SubtitleForge_release.zip to GitHub Releases
echo ============================================================
pause
