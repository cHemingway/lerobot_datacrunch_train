# LeRobot Datacrunch Training

Automatically train LeRobot models on Datacrunch spot instances with GPU acceleration.
Vibe coded with github copilot agent mode, lightly edited for simplicity

This project automates the process of:
- Creating Datacrunch spot instances with GPU requirements
- Checking instance pricing against your budget cap
- Installing LeRobot and dependencies on the instance
- Copying and running your training script
- Auto-shutdown when training completes

## Quick Start

1. **Install dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual credentials
   ```

3. **Edit train.sh to use your training settings (repo name etc)**

3. **Run training:**
   ```bash
   python3 main.py
   ```

## Configuration

### Environment Variables

Set these in your `.env` file:

```bash
# Datacrunch API credentials
DATACRUNCH_CLIENT_ID=your_datacrunch_client_id_here
DATACRUNCH_CLIENT_SECRET=your_datacrunch_client_secret_here

# ML Platform tokens  
HUGGINGFACE_TOKEN=your_huggingface_token_here
WANDB_TOKEN=your_wandb_token_here

# Instance configuration
PRICE_CAP=1.0              # Maximum price per hour in USD
REQUIRED_GPU=H100          # Required GPU type

# SSH configuration (optional)
SSH_KEY_PATH=/path/to/your/ssh/private/key
```

### Getting API Credentials

1. **Datacrunch API**: Get from [Datacrunch Dashboard](https://datacrunch.io/dashboard/api)
2. **Hugging Face Token**: Get from [HF Settings](https://huggingface.co/settings/tokens)
3. **Weights & Biases Token**: Get from [W&B Settings](https://wandb.ai/authorize)

## Training Script Customization

Edit `train.sh` to customize your training:

```bash
python -m lerobot.scripts.train \
  --dataset.repo_id=your/dataset \
  --policy.type=act \
  --output_dir=outputs/train/your_model \
  --job_name=your_training_job \
  --policy.device=cuda \
  --policy.repo_id=your/model_repo \
  --batch_size=64 \
  --steps=20000 \
  --num_workers=16 \
  --wandb.enable=true
```

## Monitoring

- **Instance Status**: Check Datacrunch dashboard
- **Training Progress**: Monitor W&B dashboard
- **SSH Access**: Connect to instance IP for debugging

### Debug Mode

For verbose logging, set:
```bash
export LOG_LEVEL=DEBUG
```

## Requirements

- Python 3.10+
- Datacrunch account with API access
- HuggingFace account 
- Weights & Biases account (optional)