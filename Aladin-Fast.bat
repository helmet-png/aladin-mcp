@echo off
REM Launch Aladin Desktop on a native JVM instead of its bundled x64 JRE.
REM On ARM64 Windows the bundled JRE runs under emulation; a native ARM64
REM JDK is noticeably faster for panning, zooming and redraws.
REM Override the JVM with JAVA_BIN, or the heap size with ALADIN_HEAP.

setlocal
if "%ALADIN_HEAP%"=="" set ALADIN_HEAP=8g

set JAVA=%JAVA_BIN%
if not defined JAVA_BIN (
  for /f "delims=" %%J in ('where javaw 2^>nul') do (
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

if not exist "%JAVA%" (
  echo No native java found on PATH. Falling back to the bundled launcher.
  start "" "C:\Program Files\Aladin\Aladin.exe"
  exit /b
)

start "Aladin" "%JAVA%" -Xmx%ALADIN_HEAP% -jar "%JAR%"
endlocal
