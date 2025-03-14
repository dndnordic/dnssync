#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync.py
# Description: DNS Sync and Monitor tool for cPanel environments (main script wrapper)
# Version: 4.0

import sys
import logging
from dnssync_lib.logger import setup_logging
from dnssync_lib.config import get_config, validate_arguments


def initialize_environment():
    """Set up logging and environment configuration"""
    # Set up logging (configuration is read from config.ini via get_config)
    config = get_config()
    # Using config but not storing the log_file variable since it's not used
    config.get('Settings', 'log_file')
    setup_logging(silent=False, show_log=True)
    logging.info("Environment initialized.")


def main_wrapper():
    """Main wrapper function that initializes environment and runs core module"""
    # Import parse_arguments from utils
    from dnssync_lib.utils import parse_arguments
    args = parse_arguments()

    # Validate command-line arguments for conflicting options.
    validate_arguments(args)

    # Initialize environment
    initialize_environment()

    # Call the core module's main function
    try:
        from dnssync_lib.core import main
        main()
    except Exception as e:
        logging.error(f"Error in main wrapper: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main_wrapper()