@echo off
rem Avvia l'interfaccia grafica con un doppio clic, senza aprire il terminale.
rem Se Python non e' nel PATH, sostituire "python" con il percorso completo
rem dell'interprete (es. C:\Python313\pythonw.exe).
cd /d "%~dp0"
start "" pythonw interfaccia.py %*
