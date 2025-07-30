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
from datacrunch.exceptions import APIException
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Disable info logging for paramiko to reduce noise
paramiko_logger = logging.getLogger("paramiko")
paramiko_logger.setLevel(logging.WARNING)  # Set to WARNING to reduce output noise


class DatacrunchManager:
    """Manages Datacrunch spot instances for LeRobot training"""

    def __init__(self, client_id: str, client_secret: str, price_cap: float = 1.0, required_gpu: str = "H100", image_name: str = "ubuntu-24.04-cuda-12.8-open", ssh_key_path: str = ""):
        """
        Initialize the Datacrunch manager
        
        Args:
            client_id: Datacrunch client ID
            client_secret: Datacrunch client secret
            price_cap: Maximum price per hour in USD
            required_gpu: Required GPU type (e.g., "H100", "RTX4090")
            image_name: OS image name to use
            ssh_key_path: Path to SSH private key file
        """
        self.client = DataCrunchClient(client_id, client_secret)
        self.price_cap = price_cap
        self.required_gpu = required_gpu
        self.instance_id = None
        self.instance_ip = None
        self.startup_script_id = None
        self.image_name = image_name
        self.ssh_key_path = self._find_ssh_key_path(ssh_key_path)

    def _find_ssh_key_path(self, provided_path: str) -> str:
        """Find SSH private key file, checking common locations"""
        if provided_path and os.path.exists(provided_path):
            logger.info(f"Using provided SSH key: {provided_path}")
            return provided_path
        
        # Common SSH key locations to check
        common_locations = [
            os.path.expanduser("~/.ssh/id_rsa"),
            os.path.expanduser("~/.ssh/id_ed25519"),
            os.path.expanduser("~/.ssh/id_ecdsa"),
            os.path.expanduser("~/.ssh/datacrunch"),
            os.path.expanduser("~/.ssh/datacrunch_rsa"),
            os.path.expanduser("~/.ssh/datacrunch_ed25519"),
        ]
        
        for key_path in common_locations:
            if os.path.exists(key_path):
                logger.info(f"Found SSH key at: {key_path}")
                return key_path
        
        logger.error("No SSH private key found. Please ensure you have an SSH key available.")
        logger.error("Checked locations:")
        for location in common_locations:
            logger.error(f"  - {location}")
        logger.error("You can specify a custom path with SSH_KEY_PATH environment variable")
        
        return ""

    def validate_ssh_setup(self) -> bool:
        """Validate that SSH key setup is properly configured"""
        if not self.ssh_key_path:
            logger.error("No SSH private key found")
            return False
        
        if not os.path.exists(self.ssh_key_path):
            logger.error(f"SSH key file does not exist: {self.ssh_key_path}")
            return False
        
        # Check file permissions (should be 600 or 400)
        try:
            import stat
            file_stat = os.stat(self.ssh_key_path)
            file_mode = stat.filemode(file_stat.st_mode)
            permissions = oct(file_stat.st_mode)[-3:]
            
            if permissions not in ['600', '400']:
                logger.warning(f"SSH key file has permissive permissions: {permissions}")
                logger.warning("Consider running: chmod 600 {self.ssh_key_path}")
            
            logger.info(f"SSH key validated: {self.ssh_key_path} (permissions: {permissions})")
            return True
            
        except Exception as e:
            logger.warning(f"Could not check SSH key permissions: {e}")
            return True  # Don't fail validation for permission check issues

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
            
        startup_script_content = self.create_startup_script(hf_token, wandb_token)
        
        try:
            # First, create the startup script
            logger.info("Creating startup script...")
            startup_script = self.client.startup_scripts.create(
                name=f'lerobot-install-{int(time.time())}',  # Add timestamp to avoid name conflicts
                script=startup_script_content
            )
            
            self.startup_script_id = startup_script.id
            logger.info(f"Startup script created with ID: {self.startup_script_id}")

            # Get the SSH key IDs
            # Get all SSH keys id's
            ssh_keys = self.client.ssh_keys.get()
            ssh_keys_ids = list(map(lambda ssh_key: ssh_key.id, ssh_keys))
            
            # Create the instance
            logger.info(f"Creating instance of type: {instance_type['name']}")

            # Hack: We can't find in advance which locations are available, so try them all
            for location in ["FIN-01", "FIN-02", "FIN-03", "ICE-01"]:
                logger.debug(f"Trying location: {location}")
            
                # Simplified instance config - remove potentially problematic parameters
                instance_config = {
                    'instance_type': instance_type['instance_type'],
                    'image': 'ubuntu-24.04-cuda-12.8-open',
                    'ssh_key_ids': ssh_keys_ids,  # Use the SSH keys we fetched
                    'hostname': 'lerobot-training',
                    'description': 'LeRobot training instance',
                    'is_spot': True,
                    'startup_script_id': startup_script.id,
                    'location': location
                }
            
                try:
                    response = self.client.instances.create(**instance_config)
                except APIException as e:
                    logger.debug(f"Failed to create instance in {location}: {e}")
                    continue  # Try the next location if this one fails
                self.instance_id = response.id
                break  # Exit loop if instance creation was successful
            if not self.instance_id:
                logger.error("Failed to create instance in all locations")
                return False
            
            logger.info(f"Instance created with ID: {self.instance_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create instance: {e}")
            # Clean up startup script if instance creation failed
            if self.startup_script_id:
                try:
                    self.client.startup_scripts.delete_by_id(self.startup_script_id)
                    logger.info("Cleaned up startup script after failed instance creation")
                except:
                    pass  # Don't fail if cleanup fails
                self.startup_script_id = None
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
    
    def wait_for_lerobot_installation(self, timeout: int = 1800) -> bool:
        """Wait for LeRobot installation to complete via SSH"""
        if not self.instance_ip:
            return False
        
        if not self.ssh_key_path:
            logger.error("SSH key path not available for connection")
            return False
            
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                ssh = paramiko.SSHClient()
                ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                
                # Connect with SSH key only
                ssh.connect(self.instance_ip, username='root', key_filename=self.ssh_key_path, timeout=10)
                
                # Check if installation is complete
                stdin, stdout, stderr = ssh.exec_command('test -f /root/installed_lerobot && echo "ready"')
                result = stdout.read().decode().strip()
                
                if result == "ready":
                    logger.info("LeRobot installation completed!")
                    ssh.close()
                    return True
                    
                ssh.close()
                logger.info("Waiting for LeRobot installation to complete...")
                time.sleep(30)

            except paramiko.AuthenticationException:
                logger.error("SSH authentication failed. Please check your SSH key is set up in datacrunch correctly")
                return False
            except paramiko.SSHException as e: # TODO: Catch more specific exceptions
                logger.debug(f"SSH connection attempt failed: {e}")
                time.sleep(30)
                
        logger.error("Timeout waiting for LeRobot installation")
        return False
    
    def copy_and_run_training_script(self, client_id: str, client_secret: str) -> bool:
        """Copy training script to instance and execute it"""
        if not self.instance_ip:
            return False
        
        if not self.ssh_key_path:
            logger.error("SSH key path not available for connection")
            return False
            
        if not self.instance_id:
            logger.error("Instance ID not available for termination")
            return False
            
        try:
            # Read and prepare the training script with substituted variables
            with open('./train.sh', 'r') as f:
                script_content = f.read()
            
            # Substitute environment variables
            script_content = script_content.replace('${DATACRUNCH_CLIENT_ID}', client_id)
            script_content = script_content.replace('${DATACRUNCH_CLIENT_SECRET}', client_secret)
            script_content = script_content.replace('${INSTANCE_ID}', self.instance_id)
            
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Connect with SSH key only
            ssh.connect(self.instance_ip, username='root', key_filename=self.ssh_key_path)
            
            # Copy modified training script
            sftp = ssh.open_sftp()
            with sftp.open('/root/train.sh', 'w') as remote_file:
                remote_file.write(script_content)
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
        """Delete the instance and startup script"""
        if self.instance_id:
            try:
                self.client.instances.action(self.instance_id, self.client.constants.instance_actions.DELETE)
                logger.info(f"Instance {self.instance_id} deletion requested")
            except Exception as e:
                logger.error(f"Failed to delete instance: {e}")
        
        if self.startup_script_id:
            try:
                self.client.startup_scripts.delete_by_id(self.startup_script_id)
                logger.info(f"Startup script {self.startup_script_id} deleted")
            except Exception as e:
                logger.error(f"Failed to delete startup script: {e}")


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
    image_name = os.getenv('IMAGE_NAME', 'ubuntu-24.04-cuda-12.8-open')

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
    if not image_name:
        missing_vars.append('IMAGE_NAME')

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
    assert image_name is not None

    manager = DatacrunchManager(client_id, client_secret, price_cap, required_gpu, image_name, ssh_key_path)
    
    # Validate SSH key is available and properly configured
    if not manager.validate_ssh_setup():
        logger.error("SSH key validation failed. Instance creation requires SSH key authentication.")
        logger.error("Please ensure you have a properly configured SSH key.")
        sys.exit(1)
    
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
        if not manager.wait_for_lerobot_installation():
            logger.error("LeRobot installation failed or timed out")
            manager.cleanup_instance()
            sys.exit(1)
        
        # Copy and run training script
        logger.info("Copying and running training script...")
        if not manager.copy_and_run_training_script(client_id, client_secret):
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