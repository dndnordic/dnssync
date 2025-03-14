#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/config.py
# Description: DNS Server Configuration & Settings Management Toolkit
# Version: 4.0

import os
import sys
import configparser
import subprocess
from typing import Dict, Set, Tuple, List, Any

# Constants
SCRIPT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_FILE = os.path.join(SCRIPT_DIR, 'config.ini')

# Singleton pattern for config
_config_instance = None


def get_config():
    """
    Load configuration from config.ini file

    Returns:
        configparser.ConfigParser: Configuration object
    """
    global _config_instance

    if _config_instance is None:
        # Load configuration
        _config_instance = configparser.ConfigParser()
        
        if not os.path.exists(CONFIG_FILE):
            # Create default config file if it doesn't exist
            create_default_config()
        
        _config_instance.read(CONFIG_FILE)

        # Validate required settings
        required_settings = [
            'active_zones_file',
            'remove_zones_file',
            'log_file',
            'pdns_api_url',
            'pdns_api_key',
            'nameservers',
            'masterns'
        ]

        missing_settings = []
        for setting in required_settings:
            if not _config_instance.has_option('Settings', setting):
                missing_settings.append(setting)

        if missing_settings:
            missing_str = ', '.join(missing_settings)
            sys.stderr.write(
                f"Missing required configuration options: {missing_str}\n")
            sys.stderr.write("Please check your config.ini file\n")
            sys.exit(1)

    return _config_instance


def create_default_config():
    """Create a default configuration file if none exists"""
    config = configparser.ConfigParser()
    config['Settings'] = {
        'active_zones_file': os.path.join(SCRIPT_DIR, 'active_zones.txt'),
        'remove_zones_file': os.path.join(SCRIPT_DIR, 'remove_zones.txt'),
        'log_file': os.path.join(SCRIPT_DIR, 'dnssync.log'),
        'pdns_api_url': 'http://localhost:8081/api/v1/servers/localhost',
        'pdns_api_key': 'changeme',
        'nameservers': 'ns1.example.com,ns2.example.com',
        'masterns': 'master.example.com',
        'excluded_domains': '',
        'enable_bidirectional': 'yes',
        'max_soa_drift': '5'
    }
    
    with open(CONFIG_FILE, 'w') as f:
        config.write(f)


def get_server_ip():
    """Get the primary server IP address"""
    return subprocess.getoutput('hostname -I').strip().split()[0]


def parse_nameservers() -> Tuple[List[str], List[str]]:
    """
    Parse nameserver configuration from config.ini

    Returns:
        tuple: Contains primary_ns and secondary_ns lists of sorted nameservers
    """
    config = get_config()

    # Parse primary nameservers
    primary_ns_str = config.get('Settings', 'nameservers')
    primary_ns = sorted(
        ns.strip().lower().rstrip('.') for ns in primary_ns_str.split(',')
    )

    # Parse secondary nameservers
    default_secondary = ('ns1.servercentralen.net,ns2.servercentralen.net,'
                         'ns3.servercentralen.net,ns4.servercentralen.net')
    secondary_ns_str = config.get(
        'Settings', 'secondary_nameservers', fallback=default_secondary)
    secondary_ns = sorted([
        ns.strip().lower() for ns in secondary_ns_str.split(',') if ns.strip()
    ])

    return primary_ns, secondary_ns


def get_excluded_domains() -> Set[str]:
    """Get domains excluded from synchronization"""
    config = get_config()
    excluded_str = config.get('Settings', 'excluded_domains', fallback='')
    return {d.strip().lower() for d in excluded_str.split(',') if d.strip()}


def get_settings() -> Dict[str, Any]:
    """
    Get all configuration settings as a dictionary

    Returns:
        dict: Configuration settings with defaults applied
    """
    config = get_config()

    # Get filesystem paths
    active_zones_file = config.get('Settings', 'active_zones_file')
    remove_zones_file = config.get('Settings', 'remove_zones_file')
    orphans_file = config.get('Settings', 'orphans_file',
                              fallback=os.path.join(SCRIPT_DIR, 'orphans.txt'))
    log_file = config.get('Settings', 'log_file')

    # Get PowerDNS settings
    pdns_api_url = config.get('Settings', 'pdns_api_url').rstrip('/')
    pdns_api_key = config.get('Settings', 'pdns_api_key')

    # Get nameserver configuration
    primary_ns, secondary_ns = parse_nameservers()
    masterns = config.get('Settings', 'masterns')

    # Get excluded domains
    excluded_domains = get_excluded_domains()

    # Get cPanel hostname
    hostname_cmd = subprocess.getoutput('hostname -f').strip()
    cpanel_hostname = config.get('Settings', 'cpanel_hostname',
                                 fallback=hostname_cmd)

    # Get sync settings
    enable_bidirectional = config.getboolean(
        'Settings', 'enable_bidirectional', fallback=True)
    max_soa_drift = config.getint(
        'Settings', 'max_soa_drift', fallback=5)

    return {
        'active_zones_file': active_zones_file,
        'remove_zones_file': remove_zones_file,
        'orphans_file': orphans_file,
        'log_file': log_file,
        'pdns_api_url': pdns_api_url,
        'pdns_api_key': pdns_api_key,
        'primary_ns': primary_ns,
        'secondary_ns': secondary_ns,
        'masterns': masterns,
        'excluded_domains': excluded_domains,
        'cpanel_hostname': cpanel_hostname,
        'enable_bidirectional': enable_bidirectional,
        'max_soa_drift': max_soa_drift,
        'server_ip': get_server_ip()
    }


# Function to validate command-line arguments
def validate_arguments(args):
    """
    Validate command-line arguments for conflicts and incompatible options

    Args:
        args: The parsed command-line arguments

    Raises:
        ValueError: If conflicting or incompatible arguments are detected
    """
    # Check that write and dryrun are not used together
    if getattr(args, 'write', False) and getattr(args, 'dryrun', False):
        raise ValueError("Error: --write and --dryrun cannot be used together")

    # Check that stepbystep is only used with domain
    if (getattr(args, 'stepbystep', False) and
            not getattr(args, 'domain', None)):
        raise ValueError("Error: --stepbystep can only be used with --domain")

    # Check that disable_bidirectional is not used with cleanup
    if (getattr(args, 'disable_bidirectional', False) and
            getattr(args, 'cleanup', False)):
        raise ValueError(
            "Error: --disable_bidirectional cannot be used with --cleanup")
            
    # Ensure only one operation mode is specified
    modes = [
        getattr(args, 'domain', None),
        getattr(args, 'cleanup', False),
        getattr(args, 'orphans', False)
    ]
    if sum(1 for mode in modes if mode) > 1:
        raise ValueError(
            "Error: Only one of --domain, --cleanup, or --orphans may be specified")