#!/bin/bash
# Copy-paste this into spot instance of datacrunch h100 to start training and shutdown when done

cd /root/lerobot
source ./.venv/bin/activate

python -m lerobot.scripts.train \
  --dataset.repo_id=cHemingway/move_purple_tape \
  --policy.type=act \
  --output_dir=outputs/train/act_move_purple_tape \
  --job_name=act_move_purple_tape \
  --policy.device=cuda \
  --policy.repo_id=cHemingway/lerobot_move_purple_tape \
  --batch_size=64 \
  --steps=20000 \
  --num_workers=16 \
  --wandb.enable=true 

# Shutdown the instance after training is complete
echo "Training complete. Shutting down the instance."
poweroff