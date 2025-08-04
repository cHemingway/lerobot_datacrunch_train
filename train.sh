#!/bin/bash
# Copy-paste this into spot instance of datacrunch h100 to start training and shutdown when done

cd /root/lerobot
source ./.venv/bin/activate

# Needed to avoid warning about parallelism in tokenizers
# https://github.com/huggingface/lerobot/issues/1377
TOKENIZERS_PARALLELISM=false
export TOKENIZERS_PARALLELISM

python -m lerobot.scripts.train \
  --dataset.repo_id=cHemingway/move_purple_tape \
  --policy.type=act \
  --output_dir=outputs/train/act_move_purple_tape \
  --job_name=act_move_purple_tape \
  --policy.device=cuda \
  --policy.repo_id=cHemingway/lerobot_move_purple_tape \
  --batch_size=64 \
  --steps=20000 \
  --save_freq=2500 \
  --num_workers=16 \
  --wandb.enable=true 

# Training complete - terminate the instance via Datacrunch API
echo "Training complete. Terminating the instance via Datacrunch API."

# Get access token from Datacrunch API
echo "Getting access token..."
ACCESS_TOKEN=$(curl -s -X POST "https://api.datacrunch.io/v1/oauth2/token" \
  -H "Content-Type: application/json" \
  -d '{
    "grant_type": "client_credentials",
    "client_id": "${DATACRUNCH_CLIENT_ID}",
    "client_secret": "${DATACRUNCH_CLIENT_SECRET}"
  }' | jq -r '.access_token')

if [ "$ACCESS_TOKEN" != "null" ] && [ "$ACCESS_TOKEN" != "" ]; then
  echo "Access token obtained. Terminating instance ${INSTANCE_ID}..."
  
  # Terminate the instance
  curl -s -X PUT "https://api.datacrunch.io/v1/instances" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{
      "id": ["${INSTANCE_ID}"],
      "action": "delete"
    }'
  
  echo "Instance termination request sent."
else
  echo "Failed to get access token! Please check your client ID and secret."
  exit 1
fi