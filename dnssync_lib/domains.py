#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/domains.py
# Description: Domain Tracking and Management for DNS Sync
# Version: 4.0

import os
import json
import logging
import subprocess
from datetime import datetime
from typing import Dict, Set, List, Tuple, Any, Optional

from .config import get_settings
from .pdns import disconnect_zone_from_cpanel
from .zones import check_zone_sync, fix_soa_drift
from .db_manager import DatabaseManager

def load_domain_tracking() -> Dict[str, Dict[str, Any]]:
    """
    Load the domain tracking information from the database.
    
    Returns:
        dict: Dictionary with domain info in the format:
        {
            "domain.com": {
                "timestamp": "2025-03-13 04:00:00",
                "status": "active"
            },
            ...
        }
    """
    db = DatabaseManager()
    return db.load_domain_tracking()

def save_domain_tracking(domains: Dict[str, Dict[str, Any]]) -> bool:
    """
    Save the domain tracking information to the database.
    
    Args:
        domains: Dictionary with domain information
        
    Returns:
        bool: True if successful, False otherwise
    """
    db = DatabaseManager()
    return db.save_domain_tracking(domains)

def load_active_zones() -> Set[str]:
    """
    Load active domains from the database
    
    Returns:
        set: Set of active domain names
    """
    db = DatabaseManager()
    active_domains = db.get_domains_by_status("active")
    return set(active_domains)

def get_affiliated_domains() -> Set[str]:
    """
    Get all domains affiliated with active user accounts in cPanel
    
    Returns:
        set: Set of affiliated domain names
    """
    affiliated_domains = set()

    # Get all user accounts
    account_cmd = subprocess.getoutput('whmapi1 listaccts --output=json')
    try:
        account_data = json.loads(account_cmd)
        accounts = [acc['user'] for acc in account_data['data']['acct'] if acc['suspended'] == 0]
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error parsing account data: {e}")
        return affiliated_domains

    logging.info(f"Found {len(accounts)} active user accounts")

    # Get main domains from listzones
    zones_cmd = subprocess.getoutput('whmapi1 listzones --output=json')
    try:
        zones_data = json.loads(zones_cmd)
        main_domains = {z['domain'].lower().rstrip('.') for z in zones_data['data']['zone']}
        affiliated_domains.update(main_domains)
        logging.info(f"Found {len(main_domains)} main domains from listzones")
    except (json.JSONDecodeError, KeyError) as e:
        logging.error(f"Error parsing zone data: {e}")

    # Get addon domains for each account
    total_addons = 0
    for user in accounts:
        addon_cmd = subprocess.getoutput(f'uapi --user={user} DomainInfo list_domains --output=json')
        try:
            addon_data = json.loads(addon_cmd)
            if addon_data['result']['status'] == 1:
                # Add addon domains
                addon_domains = {d.lower().rstrip('.') for d in addon_data['result']['data']['addon_domains']}
                affiliated_domains.update(addon_domains)
                total_addons += len(addon_domains)

                # Add parked/aliased domains
                parked_domains = {d.lower().rstrip('.') for d in addon_data['result']['data']['parked_domains']}
                affiliated_domains.update(parked_domains)

        except (json.JSONDecodeError, KeyError) as e:
            logging.error(f"Error parsing addon domain data for user {user}: {e}")

    logging.info(f"Found {total_addons} addon domains across all accounts")

    return affiliated_domains

def handle_removed_zones(dryrun: bool = False) -> None:
    """
    Process domains marked for removal
    
    Checks for domains that have been in removal state for more than 1 hour
    and removes them from PowerDNS
    
    Args:
        dryrun (bool): If True, only log what would be done
    """
    db = DatabaseManager()
    inactive_domains = db.get_domains_by_status("inactive")
    tracking = db.load_domain_tracking()
    
    domains_to_process = []
    for domain in inactive_domains:
        if domain in tracking:
            timestamp = tracking[domain].get('timestamp')
            try:
                domain_time = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                
                # Check if domain has been in removal state for more than 1 hour (3600 seconds)
                if (datetime.now() - domain_time).total_seconds() > 3600:
                    domains_to_process.append(domain)
            except (ValueError, TypeError):
                continue

    for domain in domains_to_process:
        logging.info(f"Domain {domain} has been marked for removal for more than 1 hour. Removing...")
        if not dryrun:
            disconnect_zone_from_cpanel(domain, dryrun)
            # Remove from tracking after disconnecting
            if domain in tracking:
                del tracking[domain]
    
    # Save updated tracking
    if domains_to_process and not dryrun:
        db.save_domain_tracking(tracking)
        logging.info(f"Removed {len(domains_to_process)} domains from tracking")

def process_domain_queue(max_domains: int = 10, distribution: Tuple[int, int, int] = (4, 4, 2), dryrun: bool = True) -> Dict[str, Any]:
    """
    Process a queue of domains according to distribution quotas.
    
    Args:
        max_domains (int): Maximum domains to process in this run
        distribution (tuple): Distribution of (new, existing, orphan) domains
        dryrun (bool): If True, don't make actual changes
        
    Returns:
        dict: Processing results including domains processed and status
    """
    settings = get_settings()
    db = DatabaseManager()
    
    results = {
        'total_processed': 0,
        'success_count': 0,
        'warning_count': 0,
        'error_count': 0,
        'domains': []
    }
    
    # Get current timestamp for updating domain status
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Load domain tracking information
    domain_tracking = db.load_domain_tracking()
    
    # Categorize domains
    new_domains = []
    existing_domains = []
    orphan_domains = []
    
    for domain, info in domain_tracking.items():
        if info['status'] == 'active':
            if info.get('timestamp') is None:
                new_domains.append(domain)
            else:
                existing_domains.append(domain)
        elif info['status'] == 'orphan':
            orphan_domains.append(domain)
    
    # Sort domains by timestamp (oldest first)
    def get_timestamp(domain):
        try:
            timestamp = domain_tracking[domain].get('timestamp')
            if timestamp:
                return datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
            return datetime.min
        except (ValueError, TypeError):
            return datetime.min
    
    new_domains.sort(key=get_timestamp)
    existing_domains.sort(key=get_timestamp)
    orphan_domains.sort(key=get_timestamp)
    
    # Process domains from each category
    queue_types = [
        ('new', new_domains, distribution[0]),
        ('existing', existing_domains, distribution[1]),
        ('orphan', orphan_domains, distribution[2])
    ]
    
    for queue_type, domains, quota in queue_types:
        domains_to_process = domains[:quota]
        
        for domain in domains_to_process:
            # Skip if we've reached the maximum
            if results['total_processed'] >= max_domains:
                break
            
            logging.info(f"Processing {queue_type} domain: {domain}")
            
            # Check synchronization status
            sync_status = check_zone_sync(domain)
            
            # Update domain tracking information
            domain_tracking[domain]['timestamp'] = current_time
            
            # Update status in results
            results['total_processed'] += 1
            
            if sync_status['sync_status'] == 'success':
                results['success_count'] += 1
            elif sync_status['sync_status'] == 'warning':
                results['warning_count'] += 1
            else:
                results['error_count'] += 1
            
            results['domains'].append({
                'domain': domain,
                'status': sync_status['sync_status'],
                'message': sync_status.get('error_message')
            })
            
            # Check for critical SOA drift and attempt to fix if needed
            if sync_status['sync_status'] == 'error' and sync_status['soa_drift'] and sync_status['soa_drift'] > settings['max_soa_drift']:
                logging.warning(f"Critical SOA drift detected for {domain}: {sync_status['soa_drift']}")
                
                # Attempt to fix SOA drift
                success, message = fix_soa_drift(
                    domain, 
                    sync_status['bind_serial'], 
                    sync_status['pdns_serial'],
                    dryrun
                )
                
                if success:
                    logging.info(f"Successfully fixed SOA drift for {domain}: {message}")
                    
                    if not dryrun:
                        # Update status after fix
                        updated_sync_status = check_zone_sync(domain)
                        
                        # Update results
                        for result in results['domains']:
                            if result['domain'] == domain:
                                result['status'] = updated_sync_status['sync_status']
                                result['message'] = updated_sync_status.get('error_message')
                else:
                    logging.error(f"Failed to fix SOA drift for {domain}: {message}")
    
    # Save updated domain tracking information
    db.save_domain_tracking(domain_tracking)
    
    logging.info(f"Processed {results['total_processed']} domains: " +
                f"{results['success_count']} success, " +
                f"{results['warning_count']} warning, " +
                f"{results['error_count']} error")
    
    return results