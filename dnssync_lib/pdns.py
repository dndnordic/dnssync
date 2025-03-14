#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/pdns.py
# Description: PowerDNS API interaction for DNS Sync
# Version: 4.0

import json
import logging
import requests
from .config import get_settings

def pdns_req(method, domain, data=None):
    """
    Make a request to the PowerDNS API
    
    Args:
        method (str): HTTP method ('GET', 'PUT', 'POST', 'DELETE')
        domain (str): Domain name for the request
        data (dict, optional): JSON data to send with the request
        
    Returns:
        requests.Response or None: API response or None on error
    """
    settings = get_settings()
    headers = {'X-API-Key': settings['pdns_api_key'], 'Content-Type': 'application/json'}
    
    # Ensure domain has trailing dot for API
    domain_with_dot = domain if domain.endswith('.') else f"{domain}."
    
    url = f"{settings['pdns_api_url']}/zones/{domain_with_dot}"
    
    try:
        response = requests.request(method, url, headers=headers, json=data)
        if response.status_code >= 400 and response.status_code != 404:
            logging.error(f"PowerDNS API error: {response.status_code} - {response.text}")
        return response
    except requests.exceptions.RequestException as e:
        logging.error(f"PowerDNS API request failed: {str(e)}")
        return None

def create_pdns_zone(domain, dryrun=False, verbose=False):
    """
    Create a new zone in PowerDNS
    
    Args:
        domain (str): Domain name to create
        dryrun (bool): If True, only log what would be done
        verbose (bool): If True, provide detailed logging
        
    Returns:
        bool: True if successful or dry run, False if error
    """
    settings = get_settings()
    
    # Check if zone already exists
    response = pdns_req('GET', domain)
    if response and response.ok:
        logging.info(f"Zone {domain} already exists in PowerDNS")
        return True
    
    # Basic zone data 
    zone_data = {
        'name': domain if domain.endswith('.') else f"{domain}.",
        'kind': 'Native',
        'masters': [],
        'nameservers': settings['nameservers'],
        'soa_edit_api': 'INCEPTION-INCREMENT'
    }
    
    if dryrun:
        if verbose:
            logging.info(f"[Dry-run] Would create zone {domain}: {json.dumps(zone_data)}")
        else:
            logging.info(f"[Dry-run] Would create zone {domain}")
        return True
    
    # Create zone
    response = pdns_req('POST', '/zones', zone_data)
    if response and response.status_code in (201, 204):
        logging.info(f"Created zone {domain} in PowerDNS")
        return True
    else:
        logging.error(f"Failed to create zone {domain}: {getattr(response, 'text', 'N/A')}")
        return False

def disconnect_zone_from_cpanel(domain, dryrun=False):
    """
    Disconnect a zone from cPanel in PowerDNS
    
    Args:
        domain (str): Domain name to disconnect
        dryrun (bool): If True, only log what would be done
        
    Returns:
        bool: True if successful or dry run, False if error
    """
    # Retrieve current zone data
    response = pdns_req('GET', domain)
    if response and response.ok:
        zone_data = response.json()
    else:
        logging.error(f"Failed to retrieve zone data for {domain}")
        return False
    
    # Update zone data to disconnect from cPanel
    updated_zone_data = {
        'name': zone_data['name'],
        'kind': 'Native',  # Change zone kind to Native
        'masters': [],     # Remove any masters
        'metadata': [
            item for item in zone_data.get('metadata', [])
            if item['kind'].startswith('X-DNSSEC')  # Keep only DNSSEC metadata
        ]
    }
    
    if dryrun:
        logging.info(f"[Dry-run] Would disconnect zone {domain} from cPanel: {json.dumps(updated_zone_data)}")
        return True
    
    # Update zone with the changes
    response = pdns_req('PUT', domain, updated_zone_data)
    if response and response.ok:
        logging.info(f"Disconnected zone {domain} from cPanel in PowerDNS")
        return True
    else:
        logging.error(f"Failed to disconnect zone {domain} from cPanel: {getattr(response, 'text', 'N/A')}")
        return False