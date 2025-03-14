#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/zones.py
# Description: DNS zone file operations and synchronization utilities
# Version: 4.0

import os
import logging
import subprocess
from datetime import datetime

import dns.resolver
import dns.zone
import dns.exception

from .config import get_settings
from .delegation import check_authoritative_ns

def validate_zone_file(domain):
    """
    Validate the integrity of a DNS zone file for a given domain.
    
    Args:
        domain (str): Domain name to validate
    
    Returns:
        dict: Validation results with status and potential errors
    """
    zone_file_paths = [
        f"/var/named/{domain}.db",
        f"/var/named/data/{domain}.db"
    ]
    
    result = {
        'valid': False,
        'path': None,
        'errors': []
    }
    
    for path in zone_file_paths:
        if os.path.exists(path):
            result['path'] = path
            cmd = f"named-checkzone {domain} {path}"
            try:
                zone_check = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                if zone_check.returncode == 0:
                    result['valid'] = True
                    break
                else:
                    result['errors'].append(zone_check.stderr.strip())
            except Exception as e:
                result['errors'].append(str(e))
    
    if not result['valid']:
        logging.error(f"Zone file validation failed for {domain}: {result['errors']}")
    
    return result

def reload_zone(domain):
    """
    Reload a specific DNS zone in BIND.
    
    Args:
        domain (str): Domain name to reload
    
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        cmd = f"whmapi1 reloadzones domains={domain}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Failed to reload zone {domain}: {result.stderr}")
            return False, f"Failed to reload zone {domain}: {result.stderr}"
        
        logging.info(f"Successfully reloaded zone for {domain}")
        return True, "Zone reloaded successfully"
    
    except Exception as e:
        logging.error(f"Error reloading zone {domain}: {str(e)}")
        return False, f"Error reloading zone {domain}: {str(e)}"

def backup_zone_file(domain):
    """
    Create a backup of a domain's zone file.
    
    Args:
        domain (str): Domain name to backup
    
    Returns:
        dict: Backup operation results
    """
    backup_result = {
        'success': False,
        'source_path': None,
        'backup_path': None,
        'error': None
    }
    
    zone_file_paths = [
        f"/var/named/{domain}.db",
        f"/var/named/data/{domain}.db"
    ]
    
    source_path = None
    for path in zone_file_paths:
        if os.path.exists(path):
            source_path = path
            break
    
    if not source_path:
        backup_result['error'] = "Zone file not found"
        return backup_result
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{source_path}.backup.{timestamp}"
    
    try:
        import shutil
        shutil.copy2(source_path, backup_path)
        backup_result.update({
            'success': True,
            'source_path': source_path,
            'backup_path': backup_path
        })
        logging.info(f"Backed up zone file for {domain}: {backup_path}")
    except Exception as e:
        backup_result['error'] = str(e)
        logging.error(f"Failed to backup zone file for {domain}: {e}")
    
    return backup_result

def get_bind_serial(domain_name):
    """
    Retrieve the SOA serial number from local BIND for a domain.
    
    Args:
        domain_name (str): The domain name to check
        
    Returns:
        str: SOA serial number from BIND, or None if not found
    """
    try:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = ['127.0.0.1']
        if not domain_name.endswith('.'):
            domain_name += '.'
        answers = resolver.resolve(domain_name, dns.rdatatype.SOA)
        for rdata in answers:
            serial = str(rdata.serial)
            logging.debug(f"BIND SOA serial for {domain_name}: {serial}")
            return serial
        logging.warning(f"No SOA record found in BIND for {domain_name}")
        return None
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException) as e:
        logging.error(f"Error getting BIND SOA for {domain_name}: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error getting BIND SOA for {domain_name}: {str(e)}")
        return None

def get_pdns_serial(domain_name):
    """
    Retrieve the SOA serial number from PowerDNS for a domain.
    
    Args:
        domain_name (str): The domain name to check
        
    Returns:
        str: SOA serial number from PowerDNS, or None if not found
    """
    settings = get_settings()
    try:
        if not domain_name.endswith('.'):
            domain_name += '.'
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [settings['masterns']]
        resolver.timeout = 5.0
        resolver.lifetime = 5.0
        answers = resolver.resolve(domain_name, dns.rdatatype.SOA)
        for rdata in answers:
            serial = str(rdata.serial)
            logging.debug(f"PowerDNS SOA serial for {domain_name}: {serial}")
            return serial
        logging.warning(f"No SOA record found in PowerDNS for {domain_name}")
        return None
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException) as e:
        logging.error(f"Error getting PowerDNS SOA for {domain_name}: {str(e)}")
        return None
    except Exception as e:
        logging.error(f"Unexpected error getting PowerDNS SOA for {domain_name}: {str(e)}")
        return None

def calculate_soa_drift(bind_serial, pdns_serial):
    """
    Calculate the absolute difference between BIND and PowerDNS serials.
    
    Args:
        bind_serial (str): SOA serial from BIND
        pdns_serial (str): SOA serial from PowerDNS
        
    Returns:
        int: Absolute difference between serials, or None if either is None
    """
    if bind_serial is None or pdns_serial is None:
        return None
    try:
        bind_serial_int = int(bind_serial)
        pdns_serial_int = int(pdns_serial)
        drift = abs(bind_serial_int - pdns_serial_int)
        return drift
    except ValueError as e:
        logging.error(f"Error calculating SOA drift: {str(e)}")
        return None

def check_zone_sync(domain_name):
    """
    Check synchronization status for a specific domain.
    
    Args:
        domain_name (str): The domain name to check
        
    Returns:
        dict: Status information including bind_serial, pdns_serial, sync_status, and soa_drift
    """
    settings = get_settings()
    result = {
        'domain_name': domain_name,
        'last_check': datetime.now().isoformat(),
        'bind_serial': None,
        'pdns_serial': None,
        'soa_drift': None,
        'sync_status': 'unknown',
        'error_message': None,
        'event_type': 'check',
        'details': f"Checking synchronization status for {domain_name}"
    }
    
    bind_serial = get_bind_serial(domain_name)
    result['bind_serial'] = bind_serial
    if bind_serial is None:
        result['sync_status'] = 'error'
        result['error_message'] = f"Failed to get BIND SOA serial for {domain_name}"
        result['details'] = result['error_message']
        return result
    
    pdns_serial = get_pdns_serial(domain_name)
    result['pdns_serial'] = pdns_serial
    if pdns_serial is None:
        result['sync_status'] = 'error'
        result['error_message'] = f"Failed to get PowerDNS SOA serial for {domain_name}"
        result['details'] = result['error_message']
        return result
    
    soa_drift = calculate_soa_drift(bind_serial, pdns_serial)
    result['soa_drift'] = soa_drift
    if soa_drift is None:
        result['sync_status'] = 'error'
        result['error_message'] = "Failed to calculate SOA drift"
        result['details'] = result['error_message']
        return result
    
    max_soa_drift = settings['max_soa_drift']
    if soa_drift == 0:
        result['sync_status'] = 'success'
        result['details'] = f"Zone is in sync: BIND SOA {bind_serial}, PowerDNS SOA {pdns_serial}"
    elif soa_drift <= max_soa_drift:
        result['sync_status'] = 'warning'
        result['error_message'] = f"SOA drift detected: {soa_drift}"
        result['details'] = f"Zone has SOA drift: BIND SOA {bind_serial}, PowerDNS SOA {pdns_serial}, Drift {soa_drift}"
    else:
        result['sync_status'] = 'error'
        result['error_message'] = f"Critical SOA drift detected: {soa_drift}"
        result['details'] = f"Zone has critical SOA drift: BIND SOA {bind_serial}, PowerDNS SOA {pdns_serial}, Drift {soa_drift}"
    
    return result

def fix_soa_drift(domain_name, bind_serial, pdns_serial, dryrun=True):
    """
    Attempt to fix SOA drift by updating the SOA record.
    
    Args:
        domain_name (str): The domain name to fix
        bind_serial (str): Current BIND serial
        pdns_serial (str): Current PowerDNS serial
        dryrun (bool): If True, only log what would be done
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        if not domain_name or not isinstance(domain_name, str):
            return False, "Invalid domain name"
        if not bind_serial or not pdns_serial:
            return False, "Missing serial numbers"
        try:
            bind_serial_int = int(bind_serial)
            pdns_serial_int = int(pdns_serial)
        except (ValueError, TypeError):
            return False, f"Invalid serial numbers: BIND={bind_serial}, PDNS={pdns_serial}"
        
        new_serial = max(bind_serial_int, pdns_serial_int) + 1
        new_serial_str = str(new_serial)
        
        zone_file_path = f"/var/named/{domain_name}.db"
        if not os.path.exists(zone_file_path):
            zone_file_path = f"/var/named/data/{domain_name}.db"
            if not os.path.exists(zone_file_path):
                return False, f"Zone file for {domain_name} not found"
        
        cmd = f"dig @127.0.0.1 {domain_name} SOA +short"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0 or not result.stdout.strip():
            return False, f"Failed to retrieve SOA record: {result.stderr}"
        
        soa_parts = result.stdout.strip().split()
        if len(soa_parts) < 7:
            return False, f"Invalid SOA record format: {result.stdout}"
        
        primary_ns = soa_parts[0]
        email = soa_parts[1]
        refresh = "86400"   # 24 hours
        retry = "7200"      # 2 hours
        expire = "3600000"  # ~41.7 days
        minimum = "3600"    # 1 hour
        
        if dryrun:
            logging.info(f"[Dry-run] Would update SOA record for {domain_name} with new serial {new_serial_str}")
            logging.info(f"[Dry-run] New SOA record: {domain_name}. 86400 IN SOA {primary_ns} {email} {new_serial_str} {refresh} {retry} {expire} {minimum}")
            return True, f"Would update SOA serial from {bind_serial} to {new_serial_str}"
        
        cmd = f"whmapi1 edit_zone_record domain={domain_name} " \
              f"class=IN type=SOA " \
              f"line=\"{domain_name}. 86400 IN SOA {primary_ns} {email} {new_serial_str} {refresh} {retry} {expire} {minimum}\""
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return False, f"Failed to update SOA record: {result.stderr}"
        
        cmd = f"whmapi1 reloadzones domains={domain_name}"
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        logging.info(f"Updated SOA serial for {domain_name} from {bind_serial} to {new_serial_str}")
        return True, f"Updated SOA serial from {bind_serial} to {new_serial_str}"
    
    except Exception as e:
        logging.error(f"Error fixing SOA drift for {domain_name}: {str(e)}")
        return False, f"Error fixing SOA drift: {str(e)}"