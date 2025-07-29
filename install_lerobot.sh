#!/bin/bash
# Assumes datacrunch h100 spot instance ubuntu-24-04-cuda-12-8-open-1h100*
set -e

apt-get update
apt-get install -y curl git btop ffmpeg # FFmpeg is needed for lerobot to load videos
curl -LsSf https://astral.sh/uv/install.sh | sh

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
