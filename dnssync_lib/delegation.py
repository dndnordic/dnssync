#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/delegation.py
# Description: Comprehensive Domain Delegation Verification Services
# Version: 4.0

import re
import logging
import subprocess

import dns.resolver
import dns.exception

from .config import get_settings

def check_whois(domain):
    """
    Check domain's WHOIS record to verify registrar and registration status.
    
    Args:
        domain (str): Domain to check
        
    Returns:
        dict: Whois verification results with status and details
    """
    result = {
        'verified': False,
        'registrar': None,
        'status': None,
        'errors': [],
        'nameservers': []
    }
    
    try:
        # Basic whois implementation using subprocess
        cmd = f"whois {domain}"
        whois_output = subprocess.getoutput(cmd)
        
        # Extract key information using regex patterns
        registrar_match = re.search(r'Registrar:\s*(.+)', whois_output)
        if registrar_match:
            result['registrar'] = registrar_match.group(1).strip()
        
        status_match = re.search(r'Status:\s*(.+)', whois_output)
        if status_match:
            result['status'] = status_match.group(1).strip()
            
        ns_matches = re.findall(r'Name Server:\s*(.+)', whois_output)
        if ns_matches:
            result['nameservers'] = [ns.strip().lower() for ns in ns_matches]
            
        # Basic verification
        if result['status'] and 'nameservers' in result and len(result['nameservers']) > 0:
            result['verified'] = True
        
    except Exception as e:
        result['errors'].append(f"Error checking WHOIS: {str(e)}")
    
    return result

def check_authoritative_ns(domain):
    """
    Trace authoritative nameserver delegation from root
    
    Args:
        domain (str): Domain to verify delegation
    
    Returns:
        dict: Detailed delegation verification results
    """
    # Root DNS servers (IANA-managed root servers)
    root_servers = [
        '198.41.0.4',     # a.root-servers.net
        '199.9.14.201',   # b.root-servers.net
        '192.33.4.12',    # c.root-servers.net
        '199.7.91.13',    # d.root-servers.net
        '192.203.230.10', # e.root-servers.net
        '192.5.5.241',    # f.root-servers.net
        '192.112.36.4',   # g.root-servers.net
        '198.97.190.53',  # h.root-servers.net
        '192.36.148.17',  # i.root-servers.net
        '192.58.128.30',  # j.root-servers.net
        '193.0.14.129',   # k.root-servers.net
        '199.7.83.42',    # l.root-servers.net
        '202.12.27.33'    # m.root-servers.net
    ]
    
    # Delegation verification result
    delegation_result = {
        'verified': False,
        'delegation_path': [],
        'errors': []
    }
    
    # Split domain into parts
    domain_parts = domain.lower().rstrip('.').split('.')
    
    try:
        # Resolver configuration
        resolver = dns.resolver.Resolver(configure=False)
        resolver.timeout = 5
        resolver.lifetime = 5
        
        # Start with root servers
        current_nameservers = root_servers
        
        # Trace delegation from root to TLD, then to authoritative
        for i in range(len(domain_parts)-1, -1, -1):
            # Construct current zone
            current_zone = '.'.join(domain_parts[i:])
            
            # Try each root/current nameserver
            found_delegation = False
            for ns_ip in current_nameservers:
                resolver.nameservers = [ns_ip]
                
                try:
                    # Query for nameservers of current zone
                    ns_answers = resolver.resolve(current_zone, 'NS')
                    
                    # Get new nameserver IPs
                    new_nameservers = []
                    ns_hostnames = [str(rr.target) for rr in ns_answers]
                    
                    # Resolve nameserver IPs
                    for ns_host in ns_hostnames:
                        try:
                            ip_answers = resolver.resolve(ns_host, 'A')
                            new_nameservers.extend([ip.address for ip in ip_answers])
                        except Exception:
                            pass
                    
                    # Record delegation step
                    delegation_result['delegation_path'].append({
                        'zone': current_zone,
                        'nameservers': ns_hostnames,
                        'nameserver_ips': new_nameservers
                    })
                    
                    # Update current nameservers for next iteration
                    current_nameservers = new_nameservers
                    found_delegation = True
                    break
                
                except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer):
                    continue
                except Exception as e:
                    delegation_result['errors'].append(f"Error tracing {current_zone}: {e}")
            
            # Break if no delegation found
            if not found_delegation:
                delegation_result['errors'].append(f"No delegation found for {current_zone}")
                break
        
        # Verify delegation
        delegation_result['verified'] = (
            len(delegation_result['delegation_path']) > 0 and 
            len(delegation_result['errors']) == 0
        )
        
        return delegation_result
    
    except Exception as e:
        delegation_result['errors'].append(f"Comprehensive delegation check failed: {e}")
        return delegation_result

def verify_domain_delegation(domain):
    """
    Comprehensive domain delegation verification
    
    Args:
        domain (str): Domain to verify
    
    Returns:
        dict: Comprehensive delegation verification results
    """
    # Comprehensive verification result
    delegation_result = {
        'verified': False,
        'whois': check_whois(domain),
        'dns_delegation': check_authoritative_ns(domain),
        'errors': []
    }
    
    # Combine verification results
    delegation_result['verified'] = (
        delegation_result['whois']['verified'] and 
        delegation_result['dns_delegation']['verified']
    )
    
    # Collect all errors
    delegation_result['errors'].extend(
        delegation_result['whois'].get('errors', [])
    )
    delegation_result['errors'].extend(
        delegation_result['dns_delegation'].get('errors', [])
    )
    
    return delegation_result