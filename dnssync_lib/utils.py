#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/utils.py
# Description: Utility functions for DNS Sync
# Version: 4.0

import argparse
import sys
import os
from typing import Any, Dict, List, Optional, Union

def parse_arguments():
    """
    Parse command-line arguments for the DNS sync tool
    
    Returns:
        argparse.Namespace: Parsed command-line arguments
    """
    parser = argparse.ArgumentParser(
        description="DNS Synchronization and Management Tool for cPanel environments"
    )
    
    # Operation Mode Group (mutually exclusive)
    operation_group = parser.add_mutually_exclusive_group()
    operation_group.add_argument(
        "--domain", 
        help="Process a single domain"
    )
    operation_group.add_argument(
        "--cleanup", 
        action="store_true", 
        help="Run the cleanup process for inactive domains"
    )
    operation_group.add_argument(
        "--orphans", 
        action="store_true", 
        help="Check orphaned domains for delegation status"
    )
    
    # Execution Mode Group (mutually exclusive)
    execution_group = parser.add_mutually_exclusive_group()
    execution_group.add_argument(
        "--dryrun", 
        action="store_true", 
        help="Run in dry-run mode (no changes applied)"
    )
    execution_group.add_argument(
        "--write", 
        action="store_true", 
        help="Apply changes (default is dry-run mode)"
    )
    
    # Other options
    parser.add_argument(
        "--stepbystep", 
        action="store_true", 
        help="Interactive step-by-step mode for single domain processing"
    )
    parser.add_argument(
        "--disable_bidirectional", 
        action="store_true", 
        help="Disable bidirectional sync (PowerDNS to BIND)"
    )
    parser.add_argument(
        "--silent", 
        action="store_true", 
        help="Suppress output messages"
    )
    parser.add_argument(
        "--log", 
        action="store_true", 
        help="Show log messages"
    )
    
    args = parser.parse_args()
    
    # Default to dry-run mode if --write not specified
    if not args.write:
        args.dryrun = True
    
    return args


def get_file_path(filename: str) -> str:
    """
    Get absolute path for a file in the script directory
    
    Args:
        filename: Name of the file
        
    Returns:
        str: Absolute path to the file
    """
    script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(script_dir, filename)


def read_file_lines(filepath: str) -> List[str]:
    """
    Read lines from a file, removing empty lines and comments
    
    Args:
        filepath: Path to the file
        
    Returns:
        list: List of non-empty, non-comment lines
    """
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Remove comments and strip whitespace
    return [line.strip() for line in lines 
            if line.strip() and not line.strip().startswith('#')]


def write_file_lines(filepath: str, lines: List[str]) -> None:
    """
    Write lines to a file
    
    Args:
        filepath: Path to the file
        lines: List of lines to write
    """
    with open(filepath, 'w') as f:
        for line in lines:
            f.write(f"{line}\n")