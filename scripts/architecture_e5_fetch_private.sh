#!/usr/bin/env bash
# E5 private evidence acquisition — run by an authorized human operator.
# Does NOT use the GitHub uploader-only WIF identity.
set -euo pipefail
SOURCE_SHA='72ced4d362832a0e5ebe7f51c64134b0fb88deaf'
E3_RUN_ID='41395270059'
GCS_ROOT='gs://project-tests-498508-geometry-showcase/geometry-harness/architecture-e3'
SOURCE="$GCS_ROOT/$SOURCE_SHA/$E3_RUN_ID-attempt-1/run-$E3_RUN_ID-attempt-1"
if [[ $# -ne 1 || -z "$1" ]]; then
  echo 'Usage: bash scripts/architecture_e5_fetch_private.sh /fresh/private/evidence/dir' >&2
  exit 2
fi
if ! command -v gcloud >/dev/null 2>&1; then
  echo 'Blocked: gcloud CLI not installed' >&2; exit 2
fi
if [[ -e "$1" || -L "$1" ]]; then
  echo 'Blocked: evidence destination must be fresh and not a symlink' >&2; exit 2
fi
if [[ -z "$(gcloud auth list --filter='status:ACTIVE' --format='value(account)' 2>/dev/null)" ]]; then
  echo 'Blocked: no authorized gcloud user session' >&2; exit 2
fi
# Never elevate an uploader-only identity; denied reads are real gates.
umask 077
mkdir -p "$1"
DEST="$(cd "$1" && pwd -P)"
# Exact E3 root; no wildcard or user-provided source key.
gcloud storage rsync "$SOURCE" "$DEST" --recursive --checksums-only --quiet
if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
else
  PYTHON=python3
fi
PYTHONPATH=src "$PYTHON" -m geometry_harness.domains.architecture.e5_replay \
  --bundle "$DEST" --mode inspect
echo "INTEGRITY_VERIFIED_LOCAL_COPY; expected GCS source was $SOURCE"
echo 'Operator must separately verify authenticated storage access provenance.'
echo "No LLM calls, no CAD commits. Private local evidence: $DEST"
