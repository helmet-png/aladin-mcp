@echo off
REM Launch Aladin Desktop on a native JVM instead of its bundled x64 JRE.
REM On ARM64 Windows the bundled JRE runs under emulation; a native ARM64
REM JDK is noticeably faster for panning, zooming and redraws.
REM
REM Also uses an AppCDS archive to shorten JVM class loading (~1.5 s off
REM startup). The archive is built once, on first run.
REM
REM Override the JVM with JAVA_BIN, the heap with ALADIN_HEAP, the jar with
REM ALADIN_JAR.

setlocal
if "%ALADIN_HEAP%"=="" set ALADIN_HEAP=8g

set JAVA=%JAVA_BIN%
set JAVAW=%JAVA_BIN%
if not defined JAVA_BIN (
  for /f "delims=" %%J in ('where javaw 2^>nul') do (
    set JAVAW=%%J
    goto :foundw
  )
)
:foundw
if not defined JAVA_BIN (
  for /f "delims=" %%J in ('where java 2^>nul') do (
    set JAVA=%%J
    goto :found
  )
)
:found

set JAR=%ALADIN_JAR%
if not defined ALADIN_JAR set JAR=C:\Program Files\Aladin\Aladin.jar

if not exist "%JAR%" (
  echo Could not find Aladin.jar. Set ALADIN_JAR to its full path.
  pause
  exit /b 1
)

if not exist "%JAVAW%" (
  echo No native java found on PATH. Falling back to the bundled launcher.
  start "" "C:\Program Files\Aladin\Aladin.exe"
  exit /b
)

REM Build the class-sharing archive once. Rebuild it by deleting the .jsa
REM (necessary after a JVM or Aladin upgrade; a stale one is ignored safely).
set JSA=%~dp0aladin.jsa
if not exist "%JSA%" (
  echo First run: building a startup cache, this takes a few seconds...
  echo quit | "%JAVA%" -XX:ArchiveClassesAtExit="%JSA%" -jar "%JAR%" -nogui -script >nul 2>&1
)

if exist "%JSA%" (
  start "Aladin" "%JAVAW%" -XX:SharedArchiveFile="%JSA%" -Xshare:auto -Xmx%ALADIN_HEAP% -jar "%JAR%"
) else (
  start "Aladin" "%JAVAW%" -Xmx%ALADIN_HEAP% -jar "%JAR%"
)
endlocal
