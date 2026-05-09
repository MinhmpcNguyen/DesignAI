#!/usr/bin/env bash
set -euo pipefail

ENV_NAME="prj-tknt"
ENV_ROOT="${ENV_ROOT:-$(pwd)}"
ENV_DIR="${ENV_ROOT}/.conda_envs"
PKG_DIR="${ENV_ROOT}/.conda_pkgs"

export CONDA_ENVS_PATH="${ENV_DIR}"
export CONDA_PKGS_DIRS="${PKG_DIR}"

mkdir -p "${ENV_DIR}" "${PKG_DIR}"

if ! command -v conda >/dev/null 2>&1; then
  echo "conda is not available in PATH."
  exit 1
fi

conda create -y -n "${ENV_NAME}" python=3.11
conda install -y -n "${ENV_NAME}" -c conda-forge \
  openai \
  pydantic \
  python-dotenv \
  pyyaml \
  cryptography \
  psycopg \
  typing-extensions

conda config --add envs_dirs "${ENV_DIR}"

echo "Environment '${ENV_NAME}' created."
echo "Activate with: conda activate ${ENV_NAME}"
