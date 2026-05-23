#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

CONDA_SH="${CONDA_SH:-$HOME/miniconda3/etc/profile.d/conda.sh}"
if [ ! -f "$CONDA_SH" ]; then
  CONDA_SH="$HOME/anaconda3/etc/profile.d/conda.sh"
fi
if [ ! -f "$CONDA_SH" ]; then
  echo "Cannot find conda.sh. Set CONDA_SH=/path/to/conda.sh before running." >&2
  exit 1
fi

source "$CONDA_SH"
conda activate gencad_gemini
mkdir -p outputs

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

if [ -n "${GENCAD_HTTP_PROXY:-}" ]; then
  export http_proxy="$GENCAD_HTTP_PROXY"
  export https_proxy="${GENCAD_HTTPS_PROXY:-$GENCAD_HTTP_PROXY}"
  export HTTP_PROXY="$http_proxy"
  export HTTPS_PROXY="$https_proxy"
  unset all_proxy ALL_PROXY
  export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"
  export NO_PROXY="$no_proxy"
fi

exec uvicorn app:app --host 0.0.0.0 --port "${PORT:-8000}"
