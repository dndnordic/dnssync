#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /opt/scripts/dnssync/dnssync-script.py
# Description: DNS Sync and Monitor tool for cPanel environments (main script wrapper)
# Version: 3.5

# This main wrapper now acts as the entry point.
# It constructs the concrete adapter instances and passes them to the core orchestration.

from dnssync_lib.core import main  # Our modified core.py main
from dnssync_lib.logger import setup_logging
from dnssync_lib.config import get_config, validate_arguments

import sys
import logging

def initialize_environment():
    # Set up logging (configuration is read from config.ini via get_config)
    config = get_config()
    log_file = config.get('Settings', 'log_file')
    setup_logging(silent=False, show_log=True)
    logging.info("Environment initialized.")

def main_wrapper():
    # Import parse_arguments from utils (not modified here)
    from dnssync_lib.utils import parse_arguments
    args = parse_arguments()
    
    # Validate command-line arguments for conflicting options.
    validate_arguments(args)
    
    # Initialize environment
    initialize_environment()
    
    # Call the core module's main function. (It already handles dependency injection.)
    try:
        from dnssync_lib.core import main as core_main
        core_main()
    except Exception as e:
        logging.error(f"Error in main wrapper: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main_wrapper()
