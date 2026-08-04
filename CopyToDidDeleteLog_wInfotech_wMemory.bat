@echo off
setlocal enabledelayedexpansion

REM Get current date and time (fix: preserve space between date and time)
for /f "usebackq delims=" %%a in (`powershell -NoLogo -NoProfile -Command "Get-Date -Format \"yyyy-MM-dd HH:mm:ss\""` ) do set "dt=%%a"
set "current_date=%dt:~0,10%"
set "current_time=%dt:~11,8%"

set "LOG_BASE=\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Logs"
set "scriptDir=%~dp0"
set "resultFile=%scriptDir%result.txt"
if exist "%resultFile%" del /q "%resultFile%"
>>"%resultFile%" echo Start=%date% %time%
>>"%resultFile%" echo RunDate=%current_date%
>>"%resultFile%" echo RunTime=%current_time%
>>"%resultFile%" echo.

REM Use network all-machines log
set "ALL_LOG_DIR=%LOG_BASE%\AllMachines"
if not exist "%ALL_LOG_DIR%" mkdir "%ALL_LOG_DIR%"
set "ALL_LOG_FILE=%ALL_LOG_DIR%\AllMachines_%current_date%.csv"
if not exist "%ALL_LOG_FILE%" echo Date,Time,MachineName,MachineOn,NrLogsCopied,NrLogsDeleted,FreeMemory,Error>>"%ALL_LOG_FILE%"


>>"%resultFile%" echo ResultFile=%ALL_LOG_FILE%
>>"%resultFile%" echo.

call :ProcessMachine Pink        "P:\Traceability"          "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Pink_Data"
call :ProcessMachine EKRA        "X:\SPCDataDaily"          "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\EKRA_Data\SPCDataDaily"
call :ProcessMachine Asterion    "B:\"                      "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Asterion_Data"
call :ProcessMachine Centrotherm "Y:\"                      "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Centrotherm_Data"
call :ProcessMachine Infotech    "I:\log\TraceData" "\\vt1.vitesco.com\SMT\DIDV0776\DataTransfer\Infotech_Data"

REM the new Hesse machines
call :ProcessMachine BJ935-0174  "C:\PBS200\Charts\BJ935-0174 (000bab7755509cf742f3ccc)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0174_Data"
call :ProcessMachine BJ935-0075  "C:\PBS200\Charts\BJ935-0075 (000bab3f25629a3e6c24660)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0075_Data"
call :ProcessMachine BJ935-0178  "C:\PBS200\Charts\BJ935-0178 (000bab7a3c209d645736b41)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0178_Data"
call :ProcessMachine BJ935-0331  "C:\PBS200\Charts\BJ935-0331 (000babce2d1624506d07d7a)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0331_Data"
call :ProcessMachine BJ955-0100  "C:\PBS200\Charts\BJ955-0100 (BJ955-0100)"   "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ955-0100_Data"
call :ProcessMachine BJ955-0218  "C:\PBS200\Charts\BJ955-0218 (BJ955-0218)"   "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ955-0218_Data"
call :ProcessMachine SW10851-0138  "C:\PBS200\Charts\SW10851-0138 (SW10851-0138)"   "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\SW10851-0138_Data"


>>"%resultFile%" echo.
>>"%resultFile%" echo Finished=%date% %time%
goto :EOF

:ProcessMachine
set "MACHINE=%~1"
set "SRC=%~2"
set "DST=%~3"
set "MachineOn=0"
set "NrLogsCopied=0"
set "NrLogsDeleted=0"
set "MachineError="

>>"%resultFile%" echo.
>>"%resultFile%" echo === %MACHINE% ===
>>"%resultFile%" echo Source=%SRC%
>>"%resultFile%" echo Destination=%DST%

REM FreeMemory: derive drive letter from SRC like "P:\..." => "P"
set "SRC_DRIVE=%SRC:~0,1%"
set "FreeMemory="
if not "%SRC_DRIVE%"=="" (
  for /f "usebackq delims=" %%m in (`
    powershell -NoLogo -NoProfile -Command ^
      "$d='%SRC_DRIVE%'; try { $di=Get-PSDrive -Name $d -ErrorAction Stop; [string]$di.Free } catch { '' }"
  `) do set "FreeMemory=%%m"
)
>>"%resultFile%" echo FreeMemory=%FreeMemory%

REM Single unified daily log
set "LOG_DIR=%LOG_BASE%\%MACHINE%"
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"
set "LOG_FILE=%LOG_DIR%\%MACHINE%_%current_date%.csv"
if not exist "%LOG_FILE%" echo Date,Time,MachineOn,NrLogsCopied,FileName,Error>>"%LOG_FILE%"
>>"%resultFile%" echo LogFile=%LOG_FILE%
>>"%resultFile%" echo.

REM --- Infotech: folder-based copy/delete with unified CSV logging ---
if /I "!MACHINE!"=="Infotech" (
  >>"%resultFile%" echo Infotech
  if exist "!SRC!" (
    set "MachineOn=1"
    if not exist "!DST!" mkdir "!DST!"

    for /d %%D in ("!SRC!\*") do (
      if /I "%%~nxD" neq "Allgemein" (
        robocopy "%%~fD" "!DST!\%%~nxD" /E /DCOPY:T >nul
        if !ERRORLEVEL! LEQ 7 (
          set /a NrLogsCopied+=1
          echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%~nxD,>>"%LOG_FILE%"
          >>"%resultFile%" echo COPIED: %%~fD

          call :DeleteWithRetry "%%~fD" 5 2 delErr
          if errorlevel 1 (
            if not defined MachineError set "MachineError=DELETE_FAILED"
            echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%~nxD,DELETE_FAILED>>"%LOG_FILE%"
            >>"%resultFile%" echo DELETE_FAILED: %%~fD ^| !delErr!
          ) else (
            set /a NrLogsDeleted+=1
            >>"%resultFile%" echo DELETED: %%~fD
          )
        ) else (
          if not defined MachineError set "MachineError=COPY_FAILED"
          echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%~nxD,COPY_FAILED>>"%LOG_FILE%"
          >>"%resultFile%" echo COPY_FAILED: %%~fD
        )
      ) else (
        echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%~nxD,SKIPPED>>"%LOG_FILE%"
        >>"%resultFile%" echo SKIPPED: %%~fD
      )
    )
  ) else (
    set "MachineError=SRC_NOT_FOUND"
    echo !current_date!,!current_time!,0,0,,SRC_NOT_FOUND>>"%LOG_FILE%"
    >>"%resultFile%" echo SRC_NOT_FOUND: !SRC!
  )

  REM NEW: one summary row for this machine in AllMachines log
  echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,!NrLogsCopied!,!NrLogsDeleted!,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"
  exit /b
)

REM --- existing non-Infotech (file-based) logic unchanged ---

>>"%resultFile%" echo "!SRC!"
if exist "!SRC!" (
  set "MachineOn=1"
  REM Enumerate only files (no directories)
  set "foundAnyFile=0"
  for /f "usebackq delims=" %%F in (`dir /b /a:-d "!SRC!"`) do (
        set "foundAnyFile=1"
        if not exist "!DST!" mkdir "!DST!"
        >>"%resultFile%" echo FOUND_FILE: %%F
        call :GetAvailableName "!DST!" "%%F" "finalName"
        if defined finalName (
            copy /Y "!SRC!\%%F" "!DST!\!finalName!" >nul
            if errorlevel 1 (
                if not defined MachineError set "MachineError=COPY_FAILED"
                echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%F,COPY_FAILED>>"%LOG_FILE%"
                >>"%resultFile%" echo COPY_FAILED: %%F
            ) else (
                del /f /q "!SRC!\%%F"
                if errorlevel 1 (
                    if not defined MachineError set "MachineError=DELETE_FAILED"
                    echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%F,DELETE_FAILED>>"%LOG_FILE%"
                    >>"%resultFile%" echo DELETE_FAILED: %%F
                ) else (
                    set /a NrLogsCopied+=1
                    set /a NrLogsDeleted+=1
                    echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,!finalName!,>>"%LOG_FILE%"
                    >>"%resultFile%" echo COPIED_AS: %%F to !finalName!
                )
            )
        ) else (
            if not defined MachineError set "MachineError=RENAME_FAILED"
            echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%F,RENAME_FAILED>>"%LOG_FILE%"
            >>"%resultFile%" echo RENAME_FAILED: %%F
        )
  )
  if "!foundAnyFile!"=="0" (
      >>"%resultFile%" echo NO_FILES_FOUND_IN_SRC: !SRC!
      if not defined MachineError set "MachineError=NO_FILES_FOUND"
  )
) else (
  set "MachineError=SRC_NOT_FOUND"
  echo !current_date!,!current_time!,0,0,,SRC_NOT_FOUND>>"%LOG_FILE%"
)

REM NEW: one summary row for this machine in AllMachines log
echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,!NrLogsCopied!,!NrLogsDeleted!,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

exit /b

:GetAvailableName
setlocal enabledelayedexpansion
set "dst=%~1"
set "file=%~2"
set "name=%~n2"
set "ext=%~x2"
if not exist "!dst!\!file!" (
    for %%V in ("!file!") do endlocal & set "%~3=%%~V" & exit /b 0
)
for /l %%C in (1,1,999) do (
    set "file=!name!_%%C!ext!"
    if not exist "!dst!\!file!" (
        for %%V in ("!file!") do endlocal & set "%~3=%%~V" & exit /b 0
    )
)
endlocal & set "%~3=" & exit /b 1

:DeleteWithRetry
REM %1=path, %2=retries, %3=seconds between retries, %4=outVar
setlocal enabledelayedexpansion
set "target=%~1"
set /a "retries=%~2, wait=%~3"
set "errTok=UNKNOWN"
for /l %%R in (1,1,!retries!) do (
    if exist "!target!\" (
        2>del.err rmdir /s /q "!target!"
    ) else (
        2>del.err del /f /q "!target!"
    )
    if not errorlevel 1 (
        del /q del.err >nul 2>&1
        endlocal & set "%~4=" & exit /b 0
    )
    set "line="
    set /p "line=" < del.err
    if defined line (
        set "line=!line: =_!"
        set "errTok=!line:~0,120!"
    )
    timeout /t !wait! /nobreak >nul
)
del /q del.err >nul 2>&1
endlocal & set "%~4=%errTok%" & exit /b 1
