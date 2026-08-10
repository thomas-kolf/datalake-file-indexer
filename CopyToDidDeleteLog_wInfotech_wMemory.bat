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

if not exist "%ALL_LOG_FILE%" (
    echo Date,Time,MachineName,MachineOn,NrLogsCopied,NrLogsDeleted,FreeMemory,Error>>"%ALL_LOG_FILE%"
)

>>"%resultFile%" echo ResultFile=%ALL_LOG_FILE%
>>"%resultFile%" echo.

call :ProcessMachine Pink        "P:\Traceability"          "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Pink_Data"
call :ProcessMachine EKRA        "X:\SPCDataDaily"          "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\EKRA_Data\SPCDataDaily"
call :ProcessMachine Asterion    "B:\"                      "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Asterion_Data"
call :ProcessMachine Centrotherm "Y:\"                      "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Centrotherm_Data"
call :ProcessMachine Infotech    "I:\log\TraceData"         "\\vt1.vitesco.com\SMT\DIDV0776\DataTransfer\Infotech_Data"
call :ProcessMachine Table Infotech " W:\"                  "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Table_Infotech_Data"

REM the new Hesse machines
call :ProcessMachine BJ935-0174 "C:\PBS200\Charts\BJ935-0174 (000bab7755509cf742f3ccc)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0174_Data"
call :ProcessMachine BJ935-0075 "C:\PBS200\Charts\BJ935-0075 (000bab3f25629a3e6c24660)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0075_Data"
call :ProcessMachine BJ935-0178 "C:\PBS200\Charts\BJ935-0178 (000bab7a3c209d645736b41)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0178_Data"
call :ProcessMachine BJ935-0331 "C:\PBS200\Charts\BJ935-0331 (000babce2d1624506d07d7a)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ935-0331_Data"
call :ProcessMachine BJ955-0100 "C:\PBS200\Charts\BJ955-0100 (BJ955-0100)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ955-0100_Data"
call :ProcessMachine BJ955-0218 "C:\PBS200\Charts\BJ955-0218 (BJ955-0218)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\BJ955-0218_Data"
call :ProcessMachine SW10851-0138 "C:\PBS200\Charts\SW10851-0138 (SW10851-0138)" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Hesse_Machine\SW10851-0138_Data"


REM ----Keyence Processing-----
REM Keyence/metrology files need preprocessing before copy:
REM wrapper, file indexer and embedded DMC extraction.
REM
REM Each metrology machine is handled independently.
REM A failed or missing machine does not block the other machines.

call :RunKeyencePipeline

call :ProcessMetrologyIfReady KeyenceVR5200 "V:\" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VR5200_Data" "!PREP_KeyenceVR5200!" "!PREP_REASON_KeyenceVR5200!"
call :ProcessMetrologyIfReady KeyenceVHX    "U:\" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VHX_Data"    "!PREP_KeyenceVHX!"    "!PREP_REASON_KeyenceVHX!"
call :ProcessMetrologyIfReady KeyenceLMX    "Q:\" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_LMX_Data"    "!PREP_KeyenceLMX!"    "!PREP_REASON_KeyenceLMX!"
call :ProcessMetrologyIfReady OlympusDSX    "R:\" "\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Olympus_DSX_Data"    "!PREP_OlympusDSX!"    "!PREP_REASON_OlympusDSX!"

REM ----Keyence Processing-----

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

if not exist "%LOG_FILE%" (
    echo Date,Time,MachineOn,NrLogsCopied,FileName,Error>>"%LOG_FILE%"
)

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

    echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,!NrLogsCopied!,!NrLogsDeleted!,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

    exit /b
)

REM --- existing non-Infotech file-based logic unchanged ---

>>"%resultFile%" echo "!SRC!"

if exist "!SRC!" (
    set "MachineOn=1"
    set "foundAnyFile=0"

    REM Enumerate only files, not directories
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

echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,!NrLogsCopied!,!NrLogsDeleted!,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

exit /b


REM ----Keyence Processing-----


:RunKeyencePipeline
set "KEYENCE_PIPELINE_DIR=C:\Processing\keyence-pipeline\datalake-file-indexer"
set "KEYENCE_ORCHESTRATOR=%KEYENCE_PIPELINE_DIR%\keyence_orchestrator.py"
set "PIPELINE_OUTPUT=%TEMP%\keyence_pipeline_output_%RANDOM%_%RANDOM%.txt"

REM Default: no machine is ready until its own preprocessing success
REM is confirmed from the orchestrator output.
set "PREP_KeyenceVR5200=0"
set "PREP_KeyenceVHX=0"
set "PREP_KeyenceLMX=0"
set "PREP_OlympusDSX=0"

set "PREP_REASON_KeyenceVR5200=PREPROCESSING_FAILED"
set "PREP_REASON_KeyenceVHX=INDEXING_FAILED"
set "PREP_REASON_KeyenceLMX=INDEXING_FAILED"
set "PREP_REASON_OlympusDSX=INDEXING_FAILED"

>>"%resultFile%" echo.
>>"%resultFile%" echo === RunKeyencePipeline ===
>>"%resultFile%" echo PipelineDir=%KEYENCE_PIPELINE_DIR%

if not exist "%KEYENCE_ORCHESTRATOR%" (
    >>"%resultFile%" echo KEYENCE_ORCHESTRATOR_NOT_FOUND: %KEYENCE_ORCHESTRATOR%
    exit /b 0
)

pushd "%KEYENCE_PIPELINE_DIR%"

python keyence_orchestrator.py > "%PIPELINE_OUTPUT%" 2>&1
set "KeyencePipelineExit=!ERRORLEVEL!"

popd

if exist "%PIPELINE_OUTPUT%" (
    type "%PIPELINE_OUTPUT%" >>"%resultFile%"
)

>>"%resultFile%" echo KeyencePipelineExit=!KeyencePipelineExit!

REM Evaluate every machine separately.
REM The combined orchestrator exit code does not block machines
REM whose own preprocessing completed successfully.

if exist "%PIPELINE_OUTPUT%" (
    findstr /I /C:"KeyenceVR5200: indexing completed successfully" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceVR5200=1"
        set "PREP_REASON_KeyenceVR5200="
    )

    findstr /I /C:"KeyenceVHX: indexing completed successfully" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceVHX=1"
        set "PREP_REASON_KeyenceVHX="
    )

    findstr /I /C:"KeyenceLMX: indexing completed successfully" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceLMX=1"
        set "PREP_REASON_KeyenceLMX="
    )

    findstr /I /C:"OlympusDSX: indexing completed successfully" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_OlympusDSX=1"
        set "PREP_REASON_OlympusDSX="
    )

    REM More specific VR5200 wrapper error
    findstr /I /C:"KeyenceVR5200: Wrapper failed" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceVR5200=0"
        set "PREP_REASON_KeyenceVR5200=WRAPPER_FAILED"
    )

    REM More specific scan-folder errors
    findstr /I /C:"KeyenceVR5200: Scan folder not found" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceVR5200=0"
        set "PREP_REASON_KeyenceVR5200=SRC_NOT_FOUND"
    )

    findstr /I /C:"KeyenceVHX: Scan folder not found" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceVHX=0"
        set "PREP_REASON_KeyenceVHX=SRC_NOT_FOUND"
    )

    findstr /I /C:"KeyenceLMX: Scan folder not found" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_KeyenceLMX=0"
        set "PREP_REASON_KeyenceLMX=SRC_NOT_FOUND"
    )

    findstr /I /C:"OlympusDSX: Scan folder not found" "%PIPELINE_OUTPUT%" >nul

    if not errorlevel 1 (
        set "PREP_OlympusDSX=0"
        set "PREP_REASON_OlympusDSX=SRC_NOT_FOUND"
    )
)

>>"%resultFile%" echo.
>>"%resultFile%" echo MetrologyPreprocessingStatus:
>>"%resultFile%" echo KeyenceVR5200=!PREP_KeyenceVR5200! !PREP_REASON_KeyenceVR5200!
>>"%resultFile%" echo KeyenceVHX=!PREP_KeyenceVHX! !PREP_REASON_KeyenceVHX!
>>"%resultFile%" echo KeyenceLMX=!PREP_KeyenceLMX! !PREP_REASON_KeyenceLMX!
>>"%resultFile%" echo OlympusDSX=!PREP_OlympusDSX! !PREP_REASON_OlympusDSX!

del /q "%PIPELINE_OUTPUT%" >nul 2>&1

REM Always return success here because each machine is handled separately.
exit /b 0


:ProcessMetrologyIfReady
set "READY_MACHINE=%~1"
set "READY_SRC=%~2"
set "READY_DST=%~3"
set "READY_STATUS=%~4"
set "READY_REASON=%~5"

if "!READY_STATUS!"=="1" (
    call :ProcessMetrology "!READY_MACHINE!" "!READY_SRC!" "!READY_DST!"
    exit /b
)

call :LogMetrologyPreprocessingSkip "!READY_MACHINE!" "!READY_SRC!" "!READY_REASON!"

exit /b


:LogMetrologyPreprocessingSkip
set "SKIP_MACHINE=%~1"
set "SKIP_SRC=%~2"
set "SKIP_REASON=%~3"
set "SKIP_MACHINE_ON=0"
set "SKIP_FREE_MEMORY="

if not defined SKIP_REASON (
    set "SKIP_REASON=PREPROCESSING_FAILED"
)

set "SKIP_SRC_DRIVE=!SKIP_SRC:~0,1!"

if not "!SKIP_SRC_DRIVE!"=="" (
    for /f "usebackq delims=" %%m in (`
        powershell -NoLogo -NoProfile -Command ^
        "$d='!SKIP_SRC_DRIVE!'; try { $di=Get-PSDrive -Name $d -ErrorAction Stop; [string]$di.Free } catch { '' }"
    `) do set "SKIP_FREE_MEMORY=%%m"
)

set "SKIP_LOG_DIR=%LOG_BASE%\!SKIP_MACHINE!"

if not exist "!SKIP_LOG_DIR!" mkdir "!SKIP_LOG_DIR!"

set "SKIP_LOG_FILE=!SKIP_LOG_DIR!\!SKIP_MACHINE!_%current_date%.csv"

if not exist "!SKIP_LOG_FILE!" (
    echo Date,Time,MachineOn,NrLogsCopied,FileName,Error>>"!SKIP_LOG_FILE!"
)

if not exist "!SKIP_SRC!" (
    set "SKIP_REASON=SRC_NOT_FOUND"
) else (
    set "SKIP_MACHINE_ON=1"
)

echo !current_date!,!current_time!,!SKIP_MACHINE_ON!,0,METROLOGY_FOLDER,!SKIP_REASON!>>"!SKIP_LOG_FILE!"
echo !current_date!,!current_time!,!SKIP_MACHINE!,!SKIP_MACHINE_ON!,0,0,!SKIP_FREE_MEMORY!,!SKIP_REASON!>>"%ALL_LOG_FILE%"

>>"%resultFile%" echo.
>>"%resultFile%" echo === !SKIP_MACHINE! METROLOGY ===
>>"%resultFile%" echo Source=!SKIP_SRC!
>>"%resultFile%" echo METROLOGY_MACHINE_SKIPPED: !SKIP_REASON!

exit /b


:ProcessMetrology
set "MACHINE=%~1"
set "SRC=%~2"
set "DST=%~3"
set "MachineOn=0"
set "NrLogsCopied=0"
set "NrLogsDeleted=0"
set "MachineError="

>>"%resultFile%" echo.
>>"%resultFile%" echo === %MACHINE% METROLOGY ===
>>"%resultFile%" echo Source=%SRC%
>>"%resultFile%" echo Destination=%DST%

REM FreeMemory: derive drive letter from SRC like "V:\" => "V"
set "SRC_DRIVE=%SRC:~0,1%"
set "FreeMemory="

if not "%SRC_DRIVE%"=="" (
    for /f "usebackq delims=" %%m in (`
        powershell -NoLogo -NoProfile -Command ^
        "$d='%SRC_DRIVE%'; try { $di=Get-PSDrive -Name $d -ErrorAction Stop; [string]$di.Free } catch { '' }"
    `) do set "FreeMemory=%%m"
)

>>"%resultFile%" echo FreeMemory=%FreeMemory%

set "LOG_DIR=%LOG_BASE%\%MACHINE%"

if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

set "LOG_FILE=%LOG_DIR%\%MACHINE%_%current_date%.csv"

if not exist "%LOG_FILE%" (
    echo Date,Time,MachineOn,NrLogsCopied,FileName,Error>>"%LOG_FILE%"
)

set "ROBOCOPY_LOG=%LOG_DIR%\Robocopy_%MACHINE%_%current_date%.txt"

if not exist "!SRC!" (
    set "MachineError=SRC_NOT_FOUND"

    echo !current_date!,!current_time!,0,0,,SRC_NOT_FOUND>>"%LOG_FILE%"
    >>"%resultFile%" echo SRC_NOT_FOUND: !SRC!
    echo !current_date!,!current_time!,!MACHINE!,0,0,0,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

    exit /b
)

set "MachineOn=1"

if not exist "!DST!" mkdir "!DST!"

REM Count transferable files before copy.
REM Root-level .zit recipe files are copied but not counted/deleted.
set "ExpectedFiles=0"

for /f "usebackq delims=" %%F in (`dir /b /s /a:-d "!SRC!" 2^>nul`) do (
    set "SkipFile=0"

    echo %%~fF | findstr /I /C:"\System Volume Information\" /C:"\$RECYCLE.BIN\" >nul

    if not errorlevel 1 set "SkipFile=1"

    if "!SkipFile!"=="0" (
        if /I "%%~dpF"=="!SRC!" (
            if /I not "%%~xF"==".zit" (
                set /a ExpectedFiles+=1
            )
        ) else (
            set /a ExpectedFiles+=1
        )
    )
)

REM Recursive metrology copy.
REM Robocopy cannot safely use a quoted drive-root path ending directly in "\".
REM Therefore use "\." for the Robocopy source only.
set "ROBO_SRC=!SRC!"

if "!ROBO_SRC:~-1!"=="\" (
    set "ROBO_SRC=!ROBO_SRC!."
)

robocopy "!ROBO_SRC!" "!DST!" /S /COPY:DAT /DCOPY:T /R:2 /W:2 /XJ /XD "System Volume Information" "$RECYCLE.BIN" /LOG+:"!ROBOCOPY_LOG!" /TEE

set "RoboExit=!ERRORLEVEL!"

if !RoboExit! GTR 7 (
    set "MachineError=COPY_FAILED"

    echo !current_date!,!current_time!,!MachineOn!,0,METROLOGY_FOLDER,COPY_FAILED>>"%LOG_FILE%"
    >>"%resultFile%" echo METROLOGY_COPY_FAILED: !SRC! ROBOCOPY_EXIT_!RoboExit!
    echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,0,0,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

    exit /b
)

REM Verify copied files before deleting source content.
set "MissingTargetFiles=0"
set "SRC_PREFIX=!SRC!"

if not "!SRC_PREFIX:~-1!"=="\" (
    set "SRC_PREFIX=!SRC_PREFIX!\"
)

for /f "usebackq delims=" %%F in (`dir /b /s /a:-d "!SRC!" 2^>nul`) do (
    set "SkipFile=0"

    echo %%~fF | findstr /I /C:"\System Volume Information\" /C:"\$RECYCLE.BIN\" >nul

    if not errorlevel 1 set "SkipFile=1"

    if "!SkipFile!"=="0" (
        set "FULL_PATH=%%~fF"
        set "REL_PATH=!FULL_PATH:%SRC_PREFIX%=!"

        if not exist "!DST!\!REL_PATH!" (
            set /a MissingTargetFiles+=1
            >>"%resultFile%" echo MISSING_TARGET_FILE: !DST!\!REL_PATH!
        )
    )
)

if not "!MissingTargetFiles!"=="0" (
    set "MachineError=VERIFY_COPY_FAILED"

    echo !current_date!,!current_time!,!MachineOn!,0,METROLOGY_FOLDER,VERIFY_COPY_FAILED>>"%LOG_FILE%"
    >>"%resultFile%" echo METROLOGY_VERIFY_FAILED: !MissingTargetFiles! missing files. Source not deleted.
    echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,0,0,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

    exit /b
)

set "NrLogsCopied=!ExpectedFiles!"

echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,METROLOGY_FOLDER,>>"%LOG_FILE%"
>>"%resultFile%" echo METROLOGY_COPIED_AND_VERIFIED: !SRC! to !DST!

REM Delete source content only after successful copy verification.
REM Root-level .zit recipe files are preserved.
REM Normalize the source root for direct file deletion so V:\ does not become V:\\file.
set "DELETE_SRC=!SRC!"

if "!DELETE_SRC:~-1!"=="\" (
    set "DELETE_SRC=!DELETE_SRC:~0,-1!"
)

for /f "usebackq delims=" %%F in (`dir /b /a:-d "!SRC!" 2^>nul`) do (
    if /I "%%~xF"==".zit" (
        >>"%resultFile%" echo KEPT_RECIPE_FILE: !DELETE_SRC!\%%F
    ) else (
        del /f /q "!DELETE_SRC!\%%F"

        if errorlevel 1 (
            if not defined MachineError set "MachineError=DELETE_FAILED"

            echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%F,DELETE_FAILED>>"%LOG_FILE%"
            >>"%resultFile%" echo DELETE_FAILED: !DELETE_SRC!\%%F
        ) else (
            set /a NrLogsDeleted+=1
            >>"%resultFile%" echo DELETED_FILE: !DELETE_SRC!\%%F
        )
    )
)

for /d %%D in ("!SRC!\*") do (
    if /I "%%~nxD"=="System Volume Information" (
        >>"%resultFile%" echo KEPT_EXCLUDED_FOLDER: %%~fD
    ) else if /I "%%~nxD"=="$RECYCLE.BIN" (
        >>"%resultFile%" echo KEPT_EXCLUDED_FOLDER: %%~fD
    ) else (
        set "FolderFileCount=0"

        for /f "usebackq delims=" %%C in (`dir /b /s /a:-d "%%~fD" 2^>nul`) do (
            set /a FolderFileCount+=1
        )

        call :DeleteWithRetry "%%~fD" 5 2 delErr

        if errorlevel 1 (
            if not defined MachineError set "MachineError=DELETE_FAILED"

            echo !current_date!,!current_time!,!MachineOn!,!NrLogsCopied!,%%~nxD,DELETE_FAILED>>"%LOG_FILE%"
            >>"%resultFile%" echo DELETE_FAILED: %%~fD ^| !delErr!
        ) else (
            set /a NrLogsDeleted+=!FolderFileCount!
            >>"%resultFile%" echo DELETED_FOLDER: %%~fD
        )
    )
)

echo !current_date!,!current_time!,!MACHINE!,!MachineOn!,!NrLogsCopied!,!NrLogsDeleted!,!FreeMemory!,!MachineError!>>"%ALL_LOG_FILE%"

exit /b


REM ----Keyence Processing-----


:GetAvailableName
setlocal enabledelayedexpansion

set "dst=%~1"
set "file=%~2"
set "name=%~n2"
set "ext=%~x2"

if not exist "!dst!\!file!" (
    for %%V in ("!file!") do (
        endlocal
        set "%~3=%%~V"
        exit /b 0
    )
)

for /l %%C in (1,1,999) do (
    set "file=!name!_%%C!ext!"

    if not exist "!dst!\!file!" (
        for %%V in ("!file!") do (
            endlocal
            set "%~3=%%~V"
            exit /b 0
        )
    )
)

endlocal
set "%~3="

exit /b 1


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

        endlocal
        set "%~4="
        exit /b 0
    )

    set "line="
    set /p "line=" <del.err

    if defined line (
        set "line=!line: =_!"
        set "errTok=!line:~0,120!"
    )

    timeout /t !wait! /nobreak >nul
)

del /q del.err >nul 2>&1

endlocal
set "%~4=%errTok%"

exit /b 1