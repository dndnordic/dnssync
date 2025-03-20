#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /opt/scripts/dnssync_lib/system.py
# Description: Server environment detection and system interaction
# Version: 3.3

import json
import logging
import subprocess
import ipaddress
import socket
import os
import requests
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional

def get_server_ip() -> str:
    """
    Get the primary server IP address using most reliable method
    Replaces implementation in config.py
    
    Returns:
        str: Server IP address
    """
    # First try cPanel API for reliability
    cpanel_info = get_cpanel_server_info()
    if cpanel_info.get('server_ip'):
        return cpanel_info.get('server_ip')
    
    # Fall back to hostname -I for compatibility
    return subprocess.getoutput('hostname -I').strip().split()[0]
    
def get_cpanel_hostname() -> str:
    """
    Get the FQDN of the cPanel server
    Replaces config.get('Settings', 'cpanel_hostname', fallback=...)
    
    Returns:
        str: Server FQDN
    """
    # First try cPanel API for reliability
    cpanel_info = get_cpanel_server_info()
    if cpanel_info.get('hostname'):
        return cpanel_info.get('hostname')
    
    # Fall back to hostname -f for compatibility
    return subprocess.getoutput('hostname -f').strip()

def get_cpanel_server_info() -> Dict[str, str]:
    """
    Retrieve server identification via cPanel API
    
    Returns:
        dict: Server information including IP and hostname
    """
    data = {}
    
    # Get main IP address (more reliable than hostname -I)
    ip_cmd = "whmapi1 get_shared_ip --output=json"
    ip_result = subprocess.getoutput(ip_cmd)
    try:
        ip_data = json.loads(ip_result)
        if ip_data.get("result", {}).get("status") == 1:
            data["server_ip"] = ip_data.get("data", {}).get("ip")
    except json.JSONDecodeError:
        pass

    # Get FQDN (more reliable than hostname -f)
    host_cmd = "whmapi1 gethostname --output=json"
    host_result = subprocess.getoutput(host_cmd)
    try:
        host_data = json.loads(host_result)
        if host_data.get("result", {}).get("status") == 1:
            data["hostname"] = host_data.get("data", {}).get("hostname")
    except json.JSONDecodeError:
        pass
        
    return data

def get_system_state() -> Dict[str, Any]:
    """
    Collect current system state for environment tracking
    
    Returns:
        dict: Comprehensive environment state
    """
    state = {
        'timestamp': datetime.now().isoformat(),
        'network': get_network_state(),
        'versions': get_version_info(),
        'services': get_service_state()
    }
    return state

def get_network_state() -> Dict[str, Any]:
    """
    Get network configuration details
    
    Returns:
        dict: Network configuration information
    """
    cpanel_info = get_cpanel_server_info()
    
    # Get active IPs
    ips = []
    try:
        ip_output = subprocess.getoutput("ip -4 addr show | grep -w inet").splitlines()
        for line in ip_output:
            parts = line.strip().split()
            if len(parts) > 1:
                ip_cidr = parts[1]
                if '/' in ip_cidr:
                    ip = ip_cidr.split('/')[0]
                    if ipaddress.ip_address(ip).is_global:  # Filter out private IPs
                        ips.append(ip)
    except Exception as e:
        logging.warning(f"Error getting network interfaces: {e}")
    
    # DNS resolver configuration
    resolvers = []
    try:
        with open('/etc/resolv.conf', 'r') as f:
            for line in f:
                if line.startswith('nameserver'):
                    resolvers.append(line.split()[1])
    except Exception:
        pass
    
    return {
        'primary_ip': cpanel_info.get('server_ip', ''),
        'hostname': cpanel_info.get('hostname', ''),
        'all_ips': ips,
        'resolvers': resolvers
    }

def get_version_info() -> Dict[str, str]:
    """
    Get version information for relevant components
    
    Returns:
        dict: Version information
    """
    versions = {}
    
    # Get OS version
    try:
        with open('/etc/redhat-release', 'r') as f:
            versions['os'] = f.read().strip()
    except:
        try:
            versions['os'] = subprocess.getoutput('lsb_release -d').replace('Description:', '').strip()
        except:
            versions['os'] = 'Unknown'
    
    # Get cPanel version
    try:
        cp_version = subprocess.getoutput('/usr/local/cpanel/cpanel -V')
        versions['cpanel'] = cp_version.strip()
    except:
        versions['cpanel'] = 'Unknown'
    
    # Get BIND version
    try:
        bind_version = subprocess.getoutput('named -v').split('BIND')[1].strip()
        versions['bind'] = bind_version
    except:
        versions['bind'] = 'Unknown'
    
    # Get PowerDNS version
    try:
        pdns_version = subprocess.getoutput('pdns_server --version 2>&1').split('PowerDNS')[1].strip()
        versions['pdns'] = pdns_version
    except:
        versions['pdns'] = 'Unknown'
    
    return versions

def get_service_state() -> Dict[str, bool]:
    """
    Get state of required services
    
    Returns:
        dict: Service state information
    """
    services = {}
    
    # Check if BIND is running
    try:
        bind_status = subprocess.getoutput('systemctl is-active named')
        services['bind'] = bind_status == 'active'
    except:
        services['bind'] = False
    
    # Check if PowerDNS is running
    try:
        pdns_status = subprocess.getoutput('systemctl is-active pdns')
        services['pdns'] = pdns_status == 'active'
    except:
        services['pdns'] = False
    
    # Check if master DNS is reachable
    try:
        # This would be replaced with actual configuration
        master_dns = '1.2.3.4'  # Placeholder - should be from settings
        
        # Try to connect to DNS port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((master_dns, 53))
        services['master_reachable'] = (result == 0)
        sock.close()
    except:
        services['master_reachable'] = False
    
    return services

def check_environment_drift(stored_state: Dict[str, Any], current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Compare stored environment state with current to detect drift
    
    Args:
        stored_state (dict): Previously stored environment state
        current_state (dict, optional): Current state (fetched if not provided)
        
    Returns:
        dict: Drift analysis with detected changes
    """
    if not current_state:
        current_state = get_system_state()
    
    if not stored_state:
        return {'status': 'no_previous_state', 'changes': []}
    
    changes = []
    
    # Check network changes
    if stored_state.get('network', {}).get('primary_ip') != current_state.get('network', {}).get('primary_ip'):
        changes.append({
            'component': 'network.primary_ip',
            'previous': stored_state.get('network', {}).get('primary_ip'),
            'current': current_state.get('network', {}).get('primary_ip')
        })
    
    if stored_state.get('network', {}).get('hostname') != current_state.get('network', {}).get('hostname'):
        changes.append({
            'component': 'network.hostname',
            'previous': stored_state.get('network', {}).get('hostname'),
            'current': current_state.get('network', {}).get('hostname')
        })
    
    # Check version changes
    for version_key in ['os', 'cpanel', 'bind', 'pdns']:
        if stored_state.get('versions', {}).get(version_key) != current_state.get('versions', {}).get(version_key):
            changes.append({
                'component': f'versions.{version_key}',
                'previous': stored_state.get('versions', {}).get(version_key),
                'current': current_state.get('versions', {}).get(version_key)
            })
    
    # Check service state changes
    for service_key in ['bind', 'pdns', 'master_reachable']:
        if stored_state.get('services', {}).get(service_key) != current_state.get('services', {}).get(service_key):
            changes.append({
                'component': f'services.{service_key}',
                'previous': stored_state.get('services', {}).get(service_key),
                'current': current_state.get('services', {}).get(service_key)
            })
    
    return {
        'status': 'drift_detected' if changes else 'unchanged',
        'changes': changes,
        'last_check': current_state.get('timestamp')
    }

def save_environment_state(state_file, state=None):
    """
    Save environment state to JSON file
    
    Args:
        state_file (str): Path to state file
        state (dict, optional): State to save (fetched if not provided)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not state:
        state = get_system_state()
    
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(state_file), exist_ok=True)
        
        # Use atomic write pattern
        temp_file = f"{state_file}.tmp"
        with open(temp_file, 'w') as f:
            json.dump(state, f, indent=2)
        
        # Replace original file
        os.rename(temp_file, state_file)
        return True
    except Exception as e:
        logging.error(f"Failed to save environment state: {e}")
        return False

def load_environment_state(state_file):
    """
    Load environment state from JSON file
    
    Args:
        state_file (str): Path to state file
        
    Returns:
        dict: Environment state or empty dict if not found
    """
    try:
        if os.path.exists(state_file):
            with open(state_file, 'r') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load environment state: {e}")
    
    return {}

def validate_services(settings: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Verify required services before attempting zone operations
    
    Args:
        settings (dict): Configuration settings
    
    Returns:
        tuple: (is_valid, errors) where is_valid is bool and errors is list
    """
    errors = []
    
    # Check BIND service
    try:
        bind_status = subprocess.getoutput('systemctl is-active named')
        if bind_status != 'active':
            errors.append(f"BIND service not running (status: {bind_status})")
            
        # Test if BIND is responding to queries
        bind_test = subprocess.run(
            'dig @127.0.0.1 +short google.com',
            shell=True, capture_output=True, text=True
        )
        if bind_test.returncode != 0 or not bind_test.stdout.strip():
            errors.append("BIND not responding to DNS queries")
    except Exception as e:
        errors.append(f"Error checking BIND service: {e}")
    
    # Check PowerDNS API accessibility
    if settings.get('pdns_api_url') and settings.get('pdns_api_key'):
        try:
            headers = {'X-API-Key': settings['pdns_api_key'], 'Accept': 'application/json'}
            response = requests.get(f"{settings['pdns_api_url']}/api/v1/servers/localhost", 
                                  headers=headers, timeout=5)
            
            if response.status_code != 200:
                errors.append(f"PowerDNS API error: HTTP {response.status_code}")
        except requests.exceptions.RequestException as e:
            errors.append(f"PowerDNS API connection error: {e}")
    else:
        errors.append("PowerDNS API settings missing (pdns_api_url or pdns_api_key)")
    
    # Check MasterNS reachability
    if settings.get('masterns'):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((settings['masterns'], 53))
            if result != 0:
                errors.append(f"MasterNS server unreachable: {settings['masterns']}")
            sock.close()
        except Exception as e:
            errors.append(f"Error checking MasterNS reachability: {e}")
    else:
        errors.append("MasterNS setting missing or empty")
    
    return len(errors) == 0, errors

# Todo 1: Implement DNS service health checks to verify zone transfer functionality
# Todo 2: Add monitoring for system resource usage to prevent service degradation
