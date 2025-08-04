#!/usr/bin/env python3
"""
Datacrunch Instance Explorer

Utility script to check available instances, pricing, and GPU options.
"""

import os
import sys
from typing import Dict, List
from datacrunch import DataCrunchClient
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def check_instances(client_id: str, client_secret: str, gpu_filter: str = "", max_price: float = float('inf')):
    """Check available instances with optional filtering"""
    
    try:
        client = DataCrunchClient(client_id, client_secret)
        instances = client.instance_types.get()
        
        print(f"Available Datacrunch Instances")
        print("=" * 80)
        print(f"{'Instance Type':<25} {'GPU':<15} {'GPU Count':<10} {'CPU Count':<10} {'Spot Price/hr':<15} {'On-Demand/hr':<15}")
        print("-" * 80)
        
        filtered_instances = []
        
        for instance in instances:
            # Get GPU information - instance.gpu is a dict
            gpu_name = instance.gpu.get('description', 'N/A')
            gpu_count = instance.gpu.get('number_of_gpus', 0)
            cpu_count = instance.cpu.get('number_of_cores', 0)
            spot_price = instance.spot_price_per_hour
            ondemand_price = instance.price_per_hour
            
            # Apply filters
            if gpu_filter and gpu_filter.lower() not in gpu_name.lower():
                continue
                
            if spot_price > max_price:
                continue
                
            filtered_instances.append(instance)

            print(f"{instance.instance_type:<25} {gpu_name:<15} {gpu_count:<10} {cpu_count:<10} ${spot_price:<14.3f} ${ondemand_price:<14.3f}")

        print(f"\nFound {len(filtered_instances)} instances matching criteria")
        
        if gpu_filter:
            print(f"GPU filter: {gpu_filter}")
        if max_price < float('inf'):
            print(f"Max price: ${max_price}/hour")
            
    except Exception as e:
        print(f"Error fetching instances: {e}")
        sys.exit(1)


def check_account_info(client_id: str, client_secret: str):
    """Check account information and credits"""
    try:
        client = DataCrunchClient(client_id, client_secret)
        # Note: This might not work depending on API availability
        print("Account information:")
        print("(Account details require additional API endpoints)")
        
    except Exception as e:
        print(f"Error fetching account info: {e}")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Explore Datacrunch instances and pricing')
    parser.add_argument('--gpu', help='Filter by GPU type (e.g., H100, RTX4090)')
    parser.add_argument('--max-price', type=float, help='Maximum price per hour')
    parser.add_argument('--account', action='store_true', help='Show account information')
    
    args = parser.parse_args()
    
    # Get credentials
    client_id = os.getenv('DATACRUNCH_CLIENT_ID')
    client_secret = os.getenv('DATACRUNCH_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("Error: DATACRUNCH_CLIENT_ID and DATACRUNCH_CLIENT_SECRET must be set")
        print("Set them in your .env file or environment variables")
        print("\nDebugging info:")
        print(f"  CLIENT_ID found: {'Yes' if client_id else 'No'}")
        print(f"  CLIENT_SECRET found: {'Yes' if client_secret else 'No'}")
        print(f"  .env file exists: {'Yes' if os.path.exists('.env') else 'No'}")
        if os.path.exists('.env'):
            print("  .env file contents (first few lines):")
            with open('.env', 'r') as f:
                lines = f.readlines()[:5]
                for i, line in enumerate(lines, 1):
                    # Don't print actual secrets, just show structure
                    if 'CLIENT_ID' in line or 'CLIENT_SECRET' in line:
                        print(f"    Line {i}: {line.split('=')[0]}=***")
                    else:
                        print(f"    Line {i}: {line.strip()}")
        sys.exit(1)
    
    if args.account:
        check_account_info(client_id, client_secret)
    else:
        check_instances(
            client_id, 
            client_secret, 
            args.gpu or "", 
            args.max_price or float('inf')
        )


if __name__ == "__main__":
    main()
