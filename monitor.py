#!/usr/bin/env python3
"""
Training Monitor

Monitor running Datacrunch instances and training progress.
"""

import os
import sys
import time
import paramiko
from datacrunch import DataCrunchClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def list_running_instances(client_id: str, client_secret: str):
    """List all running instances"""
    try:
        client = DataCrunchClient(client_id, client_secret)
        instances = client.instances.get()
        
        running_instances = [i for i in instances if i.get('status') == 'running']
        
        if not running_instances:
            print("No running instances found.")
            return []
            
        print("Running Instances:")
        print("=" * 80)
        print(f"{'ID':<15} {'Name':<20} {'IP':<15} {'Type':<20} {'Status':<10}")
        print("-" * 80)
        
        for instance in running_instances:
            print(f"{instance['id']:<15} {instance.get('name', 'N/A'):<20} {instance.get('ip', 'N/A'):<15} {instance.get('instance_type', 'N/A'):<20} {instance['status']:<10}")
            
        return running_instances
        
    except Exception as e:
        print(f"Error fetching instances: {e}")
        return []


def check_training_progress(instance_ip: str, ssh_key_path: str = ""):
    """Check training progress on an instance"""
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect
        if ssh_key_path and os.path.exists(ssh_key_path):
            ssh.connect(instance_ip, username='root', key_filename=ssh_key_path, timeout=10)
        else:
            ssh.connect(instance_ip, username='root', password='datacrunch', timeout=10)
        
        # Check if training is running
        stdin, stdout, stderr = ssh.exec_command('ps aux | grep python | grep lerobot')
        training_process = stdout.read().decode().strip()
        
        if training_process:
            print(f"✅ Training is running on {instance_ip}")
        else:
            print(f"⚠️  No training process found on {instance_ip}")
        
        # Check training log
        stdin, stdout, stderr = ssh.exec_command('tail -20 /root/training.log')
        log_output = stdout.read().decode().strip()
        
        if log_output:
            print(f"\nRecent training logs from {instance_ip}:")
            print("-" * 50)
            print(log_output)
        
        ssh.close()
        
    except Exception as e:
        print(f"Failed to connect to {instance_ip}: {e}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Monitor Datacrunch training instances')
    parser.add_argument('--ip', help='Check specific instance IP')
    parser.add_argument('--watch', action='store_true', help='Continuously monitor (Ctrl+C to stop)')
    
    args = parser.parse_args()
    
    # Get credentials
    client_id = os.getenv('DATACRUNCH_CLIENT_ID')
    client_secret = os.getenv('DATACRUNCH_CLIENT_SECRET')
    ssh_key_path = os.getenv('SSH_KEY_PATH', '')
    
    if not client_id or not client_secret:
        print("Error: DATACRUNCH_CLIENT_ID and DATACRUNCH_CLIENT_SECRET must be set")
        sys.exit(1)
    
    try:
        while True:
            if args.ip:
                # Check specific instance
                check_training_progress(args.ip, ssh_key_path)
            else:
                # List all instances and check training
                instances = list_running_instances(client_id, client_secret)
                
                for instance in instances:
                    instance_ip = instance.get('ip')
                    if instance_ip:
                        print(f"\nChecking training on {instance_ip}...")
                        check_training_progress(instance_ip, ssh_key_path)
                        print()
            
            if not args.watch:
                break
                
            print("\n" + "="*50)
            print("Refreshing in 60 seconds... (Ctrl+C to stop)")
            time.sleep(60)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")


if __name__ == "__main__":
    main()
