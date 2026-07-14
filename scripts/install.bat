@echo off
rem MaxDirector one-double-click installer for 3ds Max 2026.
rem Installs the one dep into Max's Python, registers the toolbar macro, and records the
rem clone path so the button always finds the code. Then just restart Max and paste your key.
setlocal EnableDelayedExpansion

rem repo root = this script's parent folder
set "REPO=%~dp0.."
for %%I in ("%REPO%") do set "REPO=%%~fI"

set "MAXPY=C:\Program Files\Autodesk\3ds Max 2026\Python\python.exe"
if not exist "%MAXPY%" (
  echo [!] Could not find Max 2026 Python at:
  echo     "%MAXPY%"
  echo     Edit the MAXPY line in this script to your 3ds Max Python path, then re-run.
  pause & exit /b 1
)

echo(
echo === MaxDirector install ===
echo repo: %REPO%
echo(

echo [1/3] installing 'requests' into Max's Python user-site...
"%MAXPY%" -m ensurepip --upgrade >nul 2>&1
"%MAXPY%" -m pip install --target "%APPDATA%\Python\Python311\site-packages" requests
if errorlevel 1 ( echo [!] pip install failed & pause & exit /b 1 )

echo [2/3] registering the startup macro...
set "STARTUP=%LOCALAPPDATA%\Autodesk\3dsMax\2026 - 64bit\ENU\scripts\startup"
if not exist "%STARTUP%" mkdir "%STARTUP%"
copy /Y "%REPO%\maxdirector\startup\maxdirector_startup.py" "%STARTUP%\" >nul
if errorlevel 1 ( echo [!] could not copy the startup script & pause & exit /b 1 )

echo [3/3] recording the clone path...
"%MAXPY%" -c "import json,os,sys;d=os.path.join(os.environ['LOCALAPPDATA'],'MaxDirector');os.makedirs(d,exist_ok=True);p=os.path.join(d,'config.json');c=(json.load(open(p)) if os.path.exists(p) else {});c['repo_path']=sys.argv[1];json.dump(c,open(p,'w'),indent=1)" "%REPO%"
setx MAXDIRECTOR "%REPO%" >nul

echo(
echo === done ===
echo Restart 3ds Max, then Customize ^> Customize User Interface ^> category MaxDirector ^>
echo drag the action onto a toolbar. Click it and paste your oc_ key.
echo(
pause
