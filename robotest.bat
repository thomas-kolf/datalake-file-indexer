@echo off
setlocal

REM ==============================
REM Robocopy standalone test
REM ==============================

set "SRC=V:\"
set "DST=\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VR5200_Data"
set "LOG=%~dp0robocopy_test.txt"

echo ================================================
echo ROBocopy TEST
echo Source:      %SRC%
echo Destination: %DST%
echo Log:         %LOG%
echo ================================================
echo.

robocopy "%SRC%" "%DST%" /S /COPY:DAT /DCOPY:T /R:2 /W:2 /XJ /XD "System Volume Information" "$RECYCLE.BIN" /LOG+:"%LOG%" /TEE

set "ROBO_EXIT=%ERRORLEVEL%"

echo.
echo ================================================
echo ROBOCOPY EXIT CODE: %ROBO_EXIT%
echo ================================================

if %ROBO_EXIT% LEQ 7 (
    echo Robocopy completed successfully.
) else (
    echo Robocopy FAILED.
)

echo.
echo Check the detailed log:
echo %LOG%
echo.

pause