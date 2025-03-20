#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /opt/scripts/dnssync/logger.py
# Description: Logging Configuration and Management
# Version: 3.3

import os
import logging
from .config import get_config

def setup_logging(silent=False, show_log=False):
    """
    Set up logging configuration:
    - Warnings and errors are always logged to file
    - Info messages are logged when show_log=True
    - Console output is suppressed when silent=True
    
    Args:
        silent (bool): If True, suppress console output
        show_log (bool): If True, include INFO level messages
    """
    # Get log file from config
    config = get_config()
    log_file = config.get('Settings', 'log_file')
    
    # Determine log level based on arguments
    log_level = logging.INFO if show_log else logging.WARNING
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Clear any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set up file logging (always enabled)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    file_handler = logging.FileHandler(log_file)
    file_formatter = logging.Formatter(
        '[%(levelname)s] %(asctime)s: %(message)s', 
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    # Set up console logging (if not silent)
    if not silent:
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter(
            '[%(levelname)s] %(asctime)s: %(message)s', 
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        root_logger.addHandler(console_handler)
    
    # Log initialization
    logging.info("DNS Sync and Monitor - Logging initialized")

def create_module_logger(module_name):
    """
    Create a module-specific logger
    
    Args:
        module_name (str): Name of the module
    
    Returns:
        logging.Logger: Configured logger for the module
    """
    logger = logging.getLogger(module_name)
    
    # If no handlers, use root logger's configuration
    if not logger.handlers:
        # Prevent propagation to root logger
        logger.propagate = False
        
        # Add handlers from root logger
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            logger.addHandler(handler)
    
    return logger

# Potential future improvements
# Todo 1: Add support for log rotation
# Todo 2: Implement configurable log formats
# Todo 3: Create method for log level adjustment during runtime
# Todo 4: Add more detailed contextual logging
# Todo 5: Implement secure log file permissions
