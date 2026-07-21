#!/usr/bin/env sh
# Launch Aladin Desktop on the system JVM rather than the one it bundles,
# with a larger heap and a class-sharing archive to shorten startup.
#
# This matters most where the bundled JRE does not match the CPU: Aladin
# ships an x64 JRE, so on an ARM64 machine (Apple Silicon, Snapdragon X)
# it runs emulated. It is still worth using elsewhere for the bigger heap
# and the faster startup.
#
# Override: JAVA_BIN (which JVM), ALADIN_JAR (which jar), ALADIN_HEAP (heap).

set -eu

HEAP="${ALADIN_HEAP:-8g}"
JAVA="${JAVA_BIN:-$(command -v java || true)}"

if [ -z "$JAVA" ]; then
    echo "No java found on PATH. Install a JDK, or set JAVA_BIN." >&2
    exit 1
fi

JAR="${ALADIN_JAR:-}"
if [ -z "$JAR" ]; then
    for c in \
        "/Applications/Aladin.app/Contents/Resources/Aladin.jar" \
        "/usr/share/aladin/Aladin.jar" \
        "/opt/Aladin/Aladin.jar" \
        "$HOME/Aladin/Aladin.jar"
    do
        [ -f "$c" ] && JAR="$c" && break
    done
fi

if [ -z "$JAR" ] || [ ! -f "$JAR" ]; then
    echo "Could not find Aladin.jar. Set ALADIN_JAR to its full path." >&2
    echo "Download it from https://aladin.cds.unistra.fr/" >&2
    exit 1
fi

# Build the class-sharing archive once. Delete the .jsa to rebuild it, which
# is needed after upgrading the JVM or Aladin; a stale one is ignored safely.
JSA="$(dirname "$0")/aladin.jsa"
if [ ! -f "$JSA" ]; then
    echo "First run: building a startup cache, this takes a few seconds..."
    echo quit | "$JAVA" -XX:ArchiveClassesAtExit="$JSA" \
        -jar "$JAR" -nogui -script >/dev/null 2>&1 || true
fi

if [ -f "$JSA" ]; then
    exec "$JAVA" -XX:SharedArchiveFile="$JSA" -Xshare:auto -Xmx"$HEAP" -jar "$JAR"
else
    exec "$JAVA" -Xmx"$HEAP" -jar "$JAR"
fi
