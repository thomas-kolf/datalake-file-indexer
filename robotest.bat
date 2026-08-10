@echo off
setlocal enabledelayedexpansion

REM ============================================================
REM Keyence VHX standalone end-to-end test
REM
REM Workflow:
REM 1. Run Keyence orchestrator
REM 2. Check VHX preprocessing result
REM 3. Recursive copy
REM 4. Verify every copied file
REM 5. Delete source files/folders after successful verification
REM ============================================================


REM ------------------------------------------------------------
REM Configuration
REM ------------------------------------------------------------

set "KEYENCE_PIPELINE_DIR=C:\Processing\keyence-pipeline\datalake-file-indexer"
set "KEYENCE_ORCHESTRATOR=%KEYENCE_PIPELINE_DIR%\keyence_orchestrator.py"

set "SRC=U:\"
set "DST=\\vt1.vitesco.com\SMT\didv0776\DataTransfer\Keyence_VHX_Data"

set "RESULT_FILE=C:\Processing\keyence_vhx_test_result.txt"
set "ROBOCOPY_LOG=C:\Processing\keyence_vhx_test_robocopy.txt"
set "PIPELINE_OUTPUT=%TEMP%\keyence_vhx_pipeline_test_%RANDOM%_%RANDOM%.txt"


REM ------------------------------------------------------------
REM Start
REM ------------------------------------------------------------

if exist "%RESULT_FILE%" del /q "%RESULT_FILE%"
if exist "%ROBOCOPY_LOG%" del /q "%ROBOCOPY_LOG%"

>>"%RESULT_FILE%" echo ============================================================
>>"%RESULT_FILE%" echo KEYENCE VHX END-TO-END TEST
>>"%RESULT_FILE%" echo Start=%date% %time%
>>"%RESULT_FILE%" echo Source=%SRC%
>>"%RESULT_FILE%" echo Destination=%DST%
>>"%RESULT_FILE%" echo ============================================================
>>"%RESULT_FILE%" echo.

echo ============================================================
echo KEYENCE VHX END-TO-END TEST
echo ============================================================
echo.
echo Source:
echo %SRC%
echo.
echo Destination:
echo %DST%
echo.


REM ============================================================
REM STEP 1 - Run Keyence preprocessing
REM ============================================================

echo [1/5] Running Keyence preprocessing...
>>"%RESULT_FILE%" echo === STEP 1 - PREPROCESSING ===

if not exist "%KEYENCE_ORCHESTRATOR%" (
    echo ERROR: Keyence orchestrator not found.
    >>"%RESULT_FILE%" echo KEYENCE_ORCHESTRATOR_NOT_FOUND: %KEYENCE_ORCHESTRATOR%
    goto :FAILED
)

pushd "%KEYENCE_PIPELINE_DIR%"

python keyence_orchestrator.py > "%PIPELINE_OUTPUT%" 2>&1
set "PIPELINE_EXIT=!ERRORLEVEL!"

popd

if exist "%PIPELINE_OUTPUT%" (
    type "%PIPELINE_OUTPUT%"
    type "%PIPELINE_OUTPUT%" >>"%RESULT_FILE%"
)

>>"%RESULT_FILE%" echo.
>>"%RESULT_FILE%" echo KeyencePipelineExit=!PIPELINE_EXIT!


REM IMPORTANT:
REM The overall orchestrator may return exit code 1 because another machine
REM such as LM-X is unavailable.
REM For this standalone test we ONLY care whether VHX succeeded.

findstr /I /C:"KeyenceVHX: indexing completed successfully" "%PIPELINE_OUTPUT%" >nul

if errorlevel 1 (
    echo.
    echo ERROR: VHX preprocessing did not complete successfully.
    >>"%RESULT_FILE%" echo VHX_PREPROCESSING_FAILED

    del /q "%PIPELINE_OUTPUT%" >nul 2>&1
    goto :FAILED
)

del /q "%PIPELINE_OUTPUT%" >nul 2>&1

echo.
echo VHX preprocessing successful.
>>"%RESULT_FILE%" echo VHX_PREPROCESSING_SUCCESS
>>"%RESULT_FILE%" echo.


REM ============================================================
REM STEP 2 - Check source
REM ============================================================

echo [2/5] Checking source...
>>"%RESULT_FILE%" echo === STEP 2 - SOURCE CHECK ===

if not exist "%SRC%" (
    echo ERROR: Source not found: %SRC%
    >>"%RESULT_FILE%" echo SRC_NOT_FOUND: %SRC%
    goto :FAILED
)

echo Source found.
>>"%RESULT_FILE%" echo SOURCE_FOUND=%SRC%


REM Count transferable files.
REM Root-level .zit would be preserved if one exists.

set "ExpectedFiles=0"

for /f "usebackq delims=" %%F in (`dir /b /s /a:-d "%SRC%" 2^>nul`) do (

    set "SkipFile=0"

    echo %%~fF | findstr /I /C:"\System Volume Information\" /C:"\$RECYCLE.BIN\" >nul
    if not errorlevel 1 set "SkipFile=1"

    if "!SkipFile!"=="0" (

        if /I "%%~dpF"=="%SRC%" (

            if /I not "%%~xF"==".zit" (
                set /a ExpectedFiles+=1
            )

        ) else (

            set /a ExpectedFiles+=1

        )
    )
)

echo Transferable files: !ExpectedFiles!
>>"%RESULT_FILE%" echo ExpectedFiles=!ExpectedFiles!
>>"%RESULT_FILE%" echo.


REM ============================================================
REM STEP 3 - Robocopy
REM ============================================================

echo.
echo [3/5] Copying files...
>>"%RESULT_FILE%" echo === STEP 3 - ROBOCOPY ===


REM Fix drive-root quoting problem:
REM U:\ becomes U:\. only for Robocopy.

set "ROBO_SRC=%SRC%"

if "!ROBO_SRC:~-1!"=="\" (
    set "ROBO_SRC=!ROBO_SRC!."
)

echo Robocopy source: !ROBO_SRC!
>>"%RESULT_FILE%" echo RobocopySource=!ROBO_SRC!


robocopy "!ROBO_SRC!" "%DST%" /S /COPY:DAT /DCOPY:T /R:2 /W:2 /XJ /XD "System Volume Information" "$RECYCLE.BIN" /LOG+:"%ROBOCOPY_LOG%" /TEE

set "ROBO_EXIT=!ERRORLEVEL!"

echo.
echo Robocopy exit code: !ROBO_EXIT!
>>"%RESULT_FILE%" echo RobocopyExit=!ROBO_EXIT!


if !ROBO_EXIT! GTR 7 (

    echo ERROR: Robocopy failed.
    >>"%RESULT_FILE%" echo METROLOGY_COPY_FAILED

    goto :FAILED
)

echo Copy completed.
>>"%RESULT_FILE%" echo ROBOCOPY_SUCCESS
>>"%RESULT_FILE%" echo.


REM ============================================================
REM STEP 4 - Verify copy
REM ============================================================

echo.
echo [4/5] Verifying copied files...
>>"%RESULT_FILE%" echo === STEP 4 - VERIFY ===

set "MissingTargetFiles=0"

set "SRC_PREFIX=%SRC%"

if not "!SRC_PREFIX:~-1!"=="\" (
    set "SRC_PREFIX=!SRC_PREFIX!\"
)


for /f "usebackq delims=" %%F in (`dir /b /s /a:-d "%SRC%" 2^>nul`) do (

    set "SkipFile=0"

    echo %%~fF | findstr /I /C:"\System Volume Information\" /C:"\$RECYCLE.BIN\" >nul
    if not errorlevel 1 set "SkipFile=1"

    if "!SkipFile!"=="0" (

        set "FULL_PATH=%%~fF"
        set "REL_PATH=!FULL_PATH:%SRC_PREFIX%=!"

        if not exist "%DST%\!REL_PATH!" (

            set /a MissingTargetFiles+=1

            echo MISSING TARGET:
            echo %DST%\!REL_PATH!

            >>"%RESULT_FILE%" echo MISSING_TARGET_FILE: %DST%\!REL_PATH!

        )
    )
)


if not "!MissingTargetFiles!"=="0" (

    echo.
    echo ERROR: !MissingTargetFiles! copied files are missing.
    echo SOURCE WILL NOT BE DELETED.

    >>"%RESULT_FILE%" echo VERIFY_COPY_FAILED=!MissingTargetFiles!
    >>"%RESULT_FILE%" echo SOURCE_NOT_DELETED

    goto :FAILED
)


echo Verification successful.
echo Every source file exists in the destination.

>>"%RESULT_FILE%" echo COPY_VERIFICATION_SUCCESS
>>"%RESULT_FILE%" echo.


REM ============================================================
REM STEP 5 - Delete source after successful verification
REM ============================================================

echo.
echo [5/5] Deleting source content...
>>"%RESULT_FILE%" echo === STEP 5 - DELETE SOURCE ===


REM Normalize source path for direct root-file deletion.
REM U:\ becomes U:
REM Then "\filename" produces U:\filename.

set "DELETE_SRC=%SRC%"

if "!DELETE_SRC:~-1!"=="\" (
    set "DELETE_SRC=!DELETE_SRC:~0,-1!"
)

echo Delete root: !DELETE_SRC!\
>>"%RESULT_FILE%" echo DeleteRoot=!DELETE_SRC!\


REM ------------------------------------------------------------
REM Delete root-level files
REM Keep .zit if one exists
REM ------------------------------------------------------------

for /f "usebackq delims=" %%F in (`dir /b /a:-d "%SRC%" 2^>nul`) do (

    if /I "%%~xF"==".zit" (

        echo KEPT RECIPE: !DELETE_SRC!\%%F
        >>"%RESULT_FILE%" echo KEPT_RECIPE_FILE: !DELETE_SRC!\%%F

    ) else (

        echo Deleting file: !DELETE_SRC!\%%F

        del /f /q "!DELETE_SRC!\%%F" 2>>"%RESULT_FILE%"

        if errorlevel 1 (

            echo DELETE FAILED: !DELETE_SRC!\%%F
            >>"%RESULT_FILE%" echo DELETE_FAILED: !DELETE_SRC!\%%F

        ) else (

            echo DELETED: !DELETE_SRC!\%%F
            >>"%RESULT_FILE%" echo DELETED_FILE: !DELETE_SRC!\%%F

        )
    )
)


REM ------------------------------------------------------------
REM Delete all source folders except Windows system folders
REM ------------------------------------------------------------

for /d %%D in ("%SRC%\*") do (

    if /I "%%~nxD"=="System Volume Information" (

        echo KEEP SYSTEM FOLDER: %%~fD
        >>"%RESULT_FILE%" echo KEPT_EXCLUDED_FOLDER: %%~fD

    ) else if /I "%%~nxD"=="$RECYCLE.BIN" (

        echo KEEP SYSTEM FOLDER: %%~fD
        >>"%RESULT_FILE%" echo KEPT_EXCLUDED_FOLDER: %%~fD

    ) else (

        echo Deleting folder: %%~fD

        call :DeleteWithRetry "%%~fD" 5 2 delErr

        if errorlevel 1 (

            echo DELETE FAILED: %%~fD
            echo Reason: !delErr!

            >>"%RESULT_FILE%" echo DELETE_FAILED: %%~fD ^| !delErr!

        ) else (

            echo DELETED FOLDER: %%~fD
            >>"%RESULT_FILE%" echo DELETED_FOLDER: %%~fD

        )
    )
)


REM ============================================================
REM Final source state
REM ============================================================

echo.
echo ============================================================
echo REMAINING CONTENT IN %SRC%
echo ============================================================

>>"%RESULT_FILE%" echo.
>>"%RESULT_FILE%" echo === REMAINING SOURCE CONTENT ===

dir /b "%SRC%" 2>nul
dir /b "%SRC%" >>"%RESULT_FILE%" 2>nul


echo.
echo ============================================================
echo VHX TEST COMPLETED
echo ============================================================
echo.
echo Result log:
echo %RESULT_FILE%
echo.
echo Robocopy log:
echo %ROBOCOPY_LOG%
echo.

>>"%RESULT_FILE%" echo.
>>"%RESULT_FILE%" echo TEST_COMPLETED=%date% %time%

pause
exit /b 0


REM ============================================================
REM Failure
REM ============================================================

:FAILED

echo.
echo ============================================================
echo VHX TEST FAILED
echo ============================================================
echo.
echo Check:
echo %RESULT_FILE%
echo.
echo Robocopy log:
echo %ROBOCOPY_LOG%
echo.

>>"%RESULT_FILE%" echo.
>>"%RESULT_FILE%" echo TEST_FAILED=%date% %time%

pause
exit /b 1


REM ============================================================
REM Delete helper
REM ============================================================

:DeleteWithRetry
REM %1=path
REM %2=retries
REM %3=seconds between retries
REM %4=output error variable

setlocal enabledelayedexpansion

set "target=%~1"
set /a "retries=%~2, wait=%~3"
set "errTok=UNKNOWN"

for /l %%R in (1,1,!retries!) do (

    if exist "!target!\" (

        2>"%TEMP%\keyence_vhx_delete_test.err" rmdir /s /q "!target!"

    ) else (

        2>"%TEMP%\keyence_vhx_delete_test.err" del /f /q "!target!"

    )

    if not errorlevel 1 (

        del /q "%TEMP%\keyence_vhx_delete_test.err" >nul 2>&1

        endlocal
        set "%~4="
        exit /b 0
    )

    set "line="

    if exist "%TEMP%\keyence_vhx_delete_test.err" (
        set /p "line=" <"%TEMP%\keyence_vhx_delete_test.err"
    )

    if defined line (
        set "line=!line: =_!"
        set "errTok=!line:~0,120!"
    )

    timeout /t !wait! /nobreak >nul
)

del /q "%TEMP%\keyence_vhx_delete_test.err" >nul 2>&1

endlocal
set "%~4=%errTok%"

exit /b 1