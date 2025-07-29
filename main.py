#!/usr/bin/env python3
"""
Datacrunch Spot Instance Manager for LeRobot Training

See README.md for details on how to use this script.
"""

import os
import sys
import time
import logging
from typing import Dict, List, Optional, Any
import paramiko
from datacrunch import DataCrunchClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class DatacrunchManager:
    """Manages Datacrunch spot instances for LeRobot training"""
    
    def __init__(self, client_id: str, client_secret: str, price_cap: float = 1.0, required_gpu: str = "H100"):
        """
        Initialize the Datacrunch manager
        
        Args:
            client_id: Datacrunch client ID
            client_secret: Datacrunch client secret
            price_cap: Maximum price per hour in USD
            required_gpu: Required GPU type (e.g., "H100", "RTX4090")
        """
        self.client = DataCrunchClient(client_id, client_secret)
        self.price_cap = price_cap
        self.required_gpu = required_gpu
        self.instance_id = None
        self.instance_ip = None
        
    def get_available_instances(self) -> List[Any]:
        """Get available instance types with pricing"""
        try:
            instances = self.client.instance_types.get()
            return instances
        except Exception as e:
            logger.error(f"Failed to get instance types: {e}")
            return []
    
    def find_suitable_instance(self) -> Optional[Dict]:
        """Find an instance type that meets GPU and price requirements"""
        instances = self.get_available_instances()
        
        for instance in instances:
            # Get GPU information from InstanceType object
            gpu_name = instance.gpu['description'] if instance.gpu else ''
            
            if self.required_gpu.lower() not in gpu_name.lower():
                continue
                
            # Check pricing
            spot_price = instance.spot_price_per_hour
            if spot_price <= self.price_cap:
                logger.info(f"Found suitable instance: {instance.instance_type} - GPU: {gpu_name} - Price: ${spot_price}/hour")
                # Convert InstanceType object to dict-like structure for compatibility
                return {
                    'name': instance.instance_type,
                    'instance_type': instance.instance_type,
                    'gpu': instance.gpu,
                    'spot_price_per_hour': instance.spot_price_per_hour,
                    'price_per_hour': instance.price_per_hour
                }
                
        logger.warning(f"No suitable instance found with {self.required_gpu} GPU under ${self.price_cap}/hour")
        return None
    
    def create_startup_script(self, hf_token: str, wandb_token: str) -> str:
        """Create startup script with environment variables substituted"""
        try:
            # Read the install_lerobot.sh file
            with open('install_lerobot.sh', 'r') as f:
                script_content = f.read()
            
            # Substitute environment variables
            script_content = script_content.replace('${HUGGINGFACE_TOKEN}', hf_token)
            script_content = script_content.replace('${WANDB_TOKEN}', wandb_token)
            
            return script_content
            
        except FileNotFoundError:
            logger.error("install_lerobot.sh file not found")
            raise
        except Exception as e:
            logger.error(f"Failed to read install_lerobot.sh: {e}")
            raise
    
    def create_instance(self, hf_token: str, wandb_token: str) -> bool:
        """Create a new spot instance"""
        instance_type = self.find_suitable_instance()
        if not instance_type:
            return False
            
        startup_script = self.create_startup_script(hf_token, wandb_token)
        
        try:
            # Create the instance
            logger.info(f"Creating instance of type: {instance_type['name']}")
            
            instance_config = {
                'instance_type': instance_type['instance_type'],
                'image': 'ubuntu-24.04-cuda-12.8-open-docker',  # Ubuntu with CUDA
                'ssh_key_ids': [],  # Add your SSH key ID here if you have one
                'hostname': 'lerobot-training',
                'description': 'LeRobot training instance',
                'is_spot': True,
                'startup_script': startup_script,
                'location': 'FIN-01'  # Finland datacenter, adjust as needed
            }
            
            response = self.client.instances.create(**instance_config)
            self.instance_id = response.id
            
            logger.info(f"Instance created with ID: {self.instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create instance: {e}")
            return False
    
    def wait_for_instance_ready(self, timeout: int = 1800) -> bool:
        """Wait for instance to be ready and get IP address"""
        if not self.instance_id:
            return False
            
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                instances = self.client.instances.get()
                instance = None
                for inst in instances:
                    if inst.id == self.instance_id:
                        instance = inst
                        break
                
                if not instance:
                    logger.error(f"Instance {self.instance_id} not found")
                    return False
                
                status = instance.status
                
                if status == 'running':
                    self.instance_ip = instance.ip
                    if self.instance_ip:
                        logger.info(f"Instance ready! IP: {self.instance_ip}")
                        return True
                        
                logger.info(f"Instance status: {status}, waiting...")
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"Error checking instance status: {e}")
                time.sleep(30)
                
        logger.error("Timeout waiting for instance to be ready")
        return False
    
    def wait_for_lerobot_installation(self, ssh_key_path: str, timeout: int = 1800) -> bool:
        """Wait for LeRobot installation to complete via SSH"""
        if not self.instance_ip:
            return False
            
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect with SSH key or password
                if ssh_key_path and os.path.exists(ssh_key_path):
                    ssh.connect(self.instance_ip, username='root', key_filename=ssh_key_path, timeout=10)
                else:
                    # For simplicity, using password auth - in production use SSH keys
                    ssh.connect(self.instance_ip, username='root', password='datacrunch', timeout=10)
                
                # Check if installation is complete
                stdin, stdout, stderr = ssh.exec_command('test -f /root/installed_lerobot && echo "ready"')
                result = stdout.read().decode().strip()
                
                if result == "ready":
                    logger.info("LeRobot installation completed!")
                    ssh.close()
                    return True
                    
                ssh.close()
                logger.info("Waiting for LeRobot installation to complete...")
                time.sleep(60)
                
            except Exception as e:
                logger.debug(f"SSH connection attempt failed: {e}")
                time.sleep(60)
                
        logger.error("Timeout waiting for LeRobot installation")
        return False
    
    def copy_and_run_training_script(self, ssh_key_path: str) -> bool:
        """Copy training script to instance and execute it"""
        if not self.instance_ip:
            return False
            
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect
            if ssh_key_path and os.path.exists(ssh_key_path):
                ssh.connect(self.instance_ip, username='root', key_filename=ssh_key_path)
            else:
                ssh.connect(self.instance_ip, username='root', password='datacrunch')
            
            # Copy training script
            sftp = ssh.open_sftp()
            sftp.put('./train.sh', '/root/train.sh')
            sftp.close()
            
            # Make executable and run
            ssh.exec_command('chmod +x /root/train.sh')
            
            logger.info("Starting training script...")
            stdin, stdout, stderr = ssh.exec_command('cd /root && nohup ./train.sh > training.log 2>&1 &')
            
            logger.info("Training script started. Check instance logs for progress.")
            ssh.close()
            return True
            
        except Exception as e:
            logger.error(f"Failed to copy and run training script: {e}")
            return False
    
    def cleanup_instance(self):
        """Delete the instance"""
        if self.instance_id:
            try:
                self.client.instances.action(self.instance_id, self.client.constants.instance_actions.DELETE)
                logger.info(f"Instance {self.instance_id} deletion requested")
            except Exception as e:
                logger.error(f"Failed to delete instance: {e}")


def main():
    """Main execution function"""
    # Environment variables
    client_id = os.getenv('DATACRUNCH_CLIENT_ID')
    client_secret = os.getenv('DATACRUNCH_CLIENT_SECRET')
    hf_token = os.getenv('HUGGINGFACE_TOKEN')
    wandb_token = os.getenv('WANDB_TOKEN')
    ssh_key_path = os.getenv('SSH_KEY_PATH', '')
    
    # Configuration
    price_cap = float(os.getenv('PRICE_CAP', '1.0'))
    required_gpu = os.getenv('REQUIRED_GPU', 'H100')
    
    # Validate required environment variables
    missing_vars = []
    if not client_id:
        missing_vars.append('DATACRUNCH_CLIENT_ID')
    if not client_secret:
        missing_vars.append('DATACRUNCH_CLIENT_SECRET')
    if not hf_token:
        missing_vars.append('HUGGINGFACE_TOKEN')
    if not wandb_token:
        missing_vars.append('WANDB_TOKEN')
        
    if missing_vars:
        logger.error("Missing required environment variables:")
        for var in missing_vars:
            logger.error(f"  - {var}")
        logger.error("Please set these variables in your .env file or environment")
        sys.exit(1)
    
    # Initialize manager (we know these are not None due to validation above)
    assert client_id is not None
    assert client_secret is not None  
    assert hf_token is not None
    assert wandb_token is not None
    
    manager = DatacrunchManager(client_id, client_secret, price_cap, required_gpu)
    
    try:
        # Create instance
        logger.info("Creating Datacrunch spot instance...")
        if not manager.create_instance(hf_token, wandb_token):
            logger.error("Failed to create instance")
            sys.exit(1)
        
        # Wait for instance to be ready
        logger.info("Waiting for instance to be ready...")
        if not manager.wait_for_instance_ready():
            logger.error("Instance failed to become ready")
            manager.cleanup_instance()
            sys.exit(1)
        
        # Wait for LeRobot installation
        logger.info("Waiting for LeRobot installation to complete...")
        if not manager.wait_for_lerobot_installation(ssh_key_path):
            logger.error("LeRobot installation failed or timed out")
            manager.cleanup_instance()
            sys.exit(1)
        
        # Copy and run training script
        logger.info("Copying and running training script...")
        if not manager.copy_and_run_training_script(ssh_key_path):
            logger.error("Failed to start training")
            manager.cleanup_instance()
            sys.exit(1)
        
        logger.info("Training started successfully!")
        logger.info(f"Instance IP: {manager.instance_ip}")
        logger.info("Training will auto-shutdown the instance when complete.")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        if input("Delete instance? (y/N): ").lower() == 'y':
            manager.cleanup_instance()
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        manager.cleanup_instance()
        sys.exit(1)


if __name__ == "__main__":
    main()