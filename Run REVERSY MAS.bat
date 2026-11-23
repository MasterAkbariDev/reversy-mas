@echo off
cd /d "%~dp0"
pyw -3 -m reversy_mas.ui.desktop
if errorlevel 1 (echo Python 3.11 or newer with Tkinter is required. & pause)
