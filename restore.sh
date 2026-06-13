#!/bin/bash
# Restore a fork's COMPLETE git history from its archived bundle.
#
# The browsable source for every fork is in repos/<name>/ (this repo).
# The full-history bundles are attached to the GitHub Release "bundles"
# (too large for in-repo storage). To restore a working clone with history:
#
#   ./restore.sh <fork-name>
#
# e.g.  ./restore.sh trident_whisper_openai_speech_recognition
#
set -e
name="$1"
[ -z "$name" ] && { echo "usage: $0 <fork-name>   (see README.md for the list)"; exit 1; }
repo="mfrancime/trident-archive"
out="${name}.bundle"
if [ ! -f "$out" ]; then
  echo "Downloading $out from the '$out' release asset..."
  if command -v gh >/dev/null; then
    gh release download bundles --repo "$repo" --pattern "$out" || {
      echo "gh download failed; grab it manually from:"
      echo "  https://github.com/$repo/releases/tag/bundles"; exit 1; }
  else
    echo "Install gh, or download $out manually from:"
    echo "  https://github.com/$repo/releases/tag/bundles"; exit 1
  fi
fi
git clone "$out" "$name"
echo "Restored full history -> ./$name"
