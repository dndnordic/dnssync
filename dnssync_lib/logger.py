#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/logger.py
# Description: Logging configuration for DNS Sync
# Version: 4.0

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from .config import get_config

def setup_logging(silent=False, show_log=False):
    """
    Configure logging for the application
    
    Args:
        silent (bool): Whether to suppress console output
        show_log (bool): Whether to display log messages on console
    """
    config = get_config()
    log_file = config.get('Settings', 'log_file')
    
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
        except OSError:
            sys.stderr.write(f"Error: Could not create log directory {log_dir}\n")
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    
    # File handler with rotation
    try:
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except (IOError, PermissionError) as e:
        sys.stderr.write(f"Error: Could not open log file {log_file}: {e}\n")
        sys.stderr.write("Logging to console only\n")
    
    # Console handler
    if not silent or show_log:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # Only add INFO and above if show_log is True, otherwise WARNING and above
        if show_log:
            console_handler.setLevel(logging.INFO)
        else:
            console_handler.setLevel(logging.WARNING)
            
        root_logger.addHandler(console_handler)
    
    # Set permissions on log file if possible
    try:
        if os.path.exists(log_file):
            os.chmod(log_file, 0o640)
    except OSError:
        logging.warning(f"Could not set permissions on log file {log_file}")
        
    logging.info("Logging initialized")