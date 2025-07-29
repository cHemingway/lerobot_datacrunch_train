#!/usr/bin/env python3
"""
SSH Key Setup Utility for DataCrunch LeRobot Training

This utility helps users set up SSH keys for DataCrunch instances.
"""

import os
import subprocess
import sys
from pathlib import Path

def check_existing_keys():
    """Check for existing SSH keys"""
    common_locations = [
        os.path.expanduser("~/.ssh/id_rsa"),
        os.path.expanduser("~/.ssh/id_ed25519"),
        os.path.expanduser("~/.ssh/id_ecdsa"),
        os.path.expanduser("~/.ssh/datacrunch"),
        os.path.expanduser("~/.ssh/datacrunch_rsa"),
        os.path.expanduser("~/.ssh/datacrunch_ed25519"),
    ]
    
    existing_keys = []
    for key_path in common_locations:
        if os.path.exists(key_path):
            existing_keys.append(key_path)
    
    return existing_keys

def generate_ssh_key():
    """Generate a new SSH key for DataCrunch"""
    ssh_dir = os.path.expanduser("~/.ssh")
    key_path = os.path.join(ssh_dir, "datacrunch_ed25519")
    
    # Create .ssh directory if it doesn't exist
    Path(ssh_dir).mkdir(mode=0o700, exist_ok=True)
    
    print(f"Generating new SSH key at: {key_path}")
    
    try:
        # Generate ED25519 key (more secure and faster than RSA)
        subprocess.run([
            "ssh-keygen",
            "-t", "ed25519",
            "-f", key_path,
            "-N", "",  # No passphrase for automation
            "-C", "datacrunch-lerobot-training"
        ], check=True)
        
        # Set proper permissions
        os.chmod(key_path, 0o600)
        os.chmod(f"{key_path}.pub", 0o644)
        
        print(f"✅ SSH key generated successfully!")
        print(f"Private key: {key_path}")
        print(f"Public key: {key_path}.pub")
        
        return key_path
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to generate SSH key: {e}")
        return None
    except FileNotFoundError:
        print("❌ ssh-keygen command not found. Please install OpenSSH client.")
        return None

def display_public_key(key_path):
    """Display the public key for uploading to DataCrunch"""
    pub_key_path = f"{key_path}.pub"
    
    if os.path.exists(pub_key_path):
        print(f"\n📋 Public key content (copy this to DataCrunch dashboard):")
        print("-" * 60)
        with open(pub_key_path, 'r') as f:
            print(f.read().strip())
        print("-" * 60)
    else:
        print(f"❌ Public key file not found: {pub_key_path}")

def main():
    """Main function"""
    print("🔑 DataCrunch SSH Key Setup Utility")
    print("=" * 50)
    
    # Check for existing keys
    existing_keys = check_existing_keys()
    
    if existing_keys:
        print(f"✅ Found {len(existing_keys)} existing SSH key(s):")
        for key in existing_keys:
            print(f"  - {key}")
        
        print(f"\n🔧 You can use any of these keys by setting SSH_KEY_PATH in your .env file")
        print(f"Example: SSH_KEY_PATH={existing_keys[0]}")
        
        # Show public key for the first found key
        display_public_key(existing_keys[0])
        
    else:
        print("❌ No existing SSH keys found")
        
        response = input("\n🤔 Would you like to generate a new SSH key? (y/N): ")
        if response.lower() in ['y', 'yes']:
            key_path = generate_ssh_key()
            if key_path:
                display_public_key(key_path)
                print(f"\n🎯 To use this key, add this to your .env file:")
                print(f"SSH_KEY_PATH={key_path}")
        else:
            print("\n📖 To manually create an SSH key, run:")
            print("ssh-keygen -t ed25519 -f ~/.ssh/datacrunch_ed25519 -C 'datacrunch-lerobot'")

if __name__ == "__main__":
    main()
