#!/bin/bash
# Assumes datacrunch h100 spot instance ubuntu-24-04-cuda-12-8-open-1h100*
# Variables are loaded in from .env file by main.py
set -e

# Log output to install_lerobot_log.out
# From https://serverfault.com/a/103569
exec 3>&1 4>&2
trap 'exec 2>&4 1>&3' 0 1 2 3
exec 1>/root/install_lerobot_log.out 2>&1

apt-get update
apt-get install -y curl git btop ffmpeg jq # FFmpeg is needed for lerobot to load videos, jq for JSON parsing

# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh
source /root/.local/bin/env # We need to source this as we can't restart the shell

# Install Hugging Face CLI and login with token
uv tool install "huggingface_hub[cli]"
huggingface-cli login --token ${HUGGINGFACE_TOKEN}

# Install weightsandbiases and login with token
uv tool install wandb
wandb login ${WANDB_TOKEN}

# Clone the lerobot repo and install it
pushd /root
git clone http://github.com/huggingface/lerobot.git
cd lerobot
# We need python 3.11 as on 3.12 we try and build a package instead of using a prebuilt one
uv sync --extra smolvla --python=3.11
# Flag we have finished
cd /root
touch installed_lerobot
# Revert
popd
