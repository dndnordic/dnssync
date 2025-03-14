#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/core.py
# Description: DNS Zone Synchronization Workflow Management Engine
# Version: 4.0

import sys
import logging
import traceback
from datetime import datetime
from abc import ABC, abstractmethod
from typing import Dict, Set, Tuple, List, Any, Optional
import time

# Import local modules
from .locks import single_instance, release_lock
from .logger import setup_logging
from .utils import parse_arguments
from .config import get_settings
from .db_manager import DatabaseManager
from .error_handling import CircuitBreaker, retry_with_backoff

class DnsApiInterface(ABC):
    """Interface for DNS API operations"""
    
    @abstractmethod
    def get_zone(self, domain: str) -> Dict[str, Any]:
        """Get zone data for a domain"""
        pass

    @abstractmethod
    def update_zone(self, domain: str, zone_data: Dict[str, Any]) -> bool:
        """Update zone data for a domain"""
        pass

    @abstractmethod
    def delete_zone(self, domain: str) -> bool:
        """Delete zone for a domain"""
        pass

    @abstractmethod
    def create_zone(self, domain: str, dryrun: bool, verbose: bool = False) -> bool:
        """Create a new zone for a domain"""
        pass


class DomainManagerInterface(ABC):
    """Interface for domain management operations"""
    
    @abstractmethod
    def get_affiliated_domains(self) -> Set[str]:
        """Get set of all affiliated domains"""
        pass

    @abstractmethod
    def process_queue(self, max_domains: int, distribution: Tuple[int, int, int], dryrun: bool) -> Dict[str, Any]:
        """Process domain queue with specified distribution"""
        pass

    @abstractmethod
    def load_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Load domain tracking data"""
        pass

    @abstractmethod
    def save_tracking(self, tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save domain tracking data"""
        pass
    
    @abstractmethod
    def get_domains_by_status(self, status: str) -> List[str]:
        """Get domains with a specified status"""
        pass
    
    @abstractmethod
    def handle_removed_zones(self, dryrun: bool) -> None:
        """Handle zones that have been removed from cPanel"""
        pass


class PowerDnsApiAdapter(DnsApiInterface):
    """Adapter for PowerDNS API operations with circuit breaker and retry logic"""
    
    def __init__(self):
        from .config import get_settings
        self.settings = get_settings()
        # Initialize circuit breaker for API calls
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            name="PowerDNS API"
        )
    
    @retry_with_backoff(max_retries=3, backoff_factor=2)
    def get_zone(self, domain: str) -> Dict[str, Any]:
        """Get zone data with circuit breaker protection"""
        from .pdns import pdns_req
        
        with self.circuit_breaker:
            response = pdns_req('GET', domain)
            if response and response.ok:
                return response.json()
            else:
                msg = getattr(response, 'text', 'Unknown error')
                status_code = getattr(response, 'status_code', None)
                if status_code == 404:
                    return {"error": "not_found", "status_code": 404}
                raise Exception(f"Failed to get zone for {domain}: {msg}")

    @retry_with_backoff(max_retries=3, backoff_factor=2)
    def update_zone(self, domain: str, zone_data: Dict[str, Any]) -> bool:
        """Update zone with circuit breaker protection"""
        from .pdns import pdns_req
        
        with self.circuit_breaker:
            response = pdns_req('PUT', domain, zone_data)
            return response is not None and response.ok

    @retry_with_backoff(max_retries=3, backoff_factor=2)
    def delete_zone(self, domain: str) -> bool:
        """Delete zone with circuit breaker protection"""
        from .pdns import pdns_req
        
        with self.circuit_breaker:
            response = pdns_req('DELETE', domain)
            return response is not None and response.ok
    
    @retry_with_backoff(max_retries=3, backoff_factor=2)
    def create_zone(self, domain: str, dryrun: bool, verbose: bool = False) -> bool:
        """Create zone with circuit breaker protection"""
        from .pdns import create_pdns_zone
        
        with self.circuit_breaker:
            return create_pdns_zone(domain, dryrun, verbose)


class DomainManagerAdapter(DomainManagerInterface):
    """Adapter for domain management operations using database storage"""
    
    def __init__(self):
        self.db_manager = DatabaseManager()
        # Import here to avoid circular imports
        from .domains import (
            get_affiliated_domains as get_domains, 
            load_active_zones,
            process_domain_queue as process_queue
        )
        from .zones import check_zone_sync, fix_soa_drift
        
        self.get_domains = get_domains
        self.load_active_zones = load_active_zones
        self.process_queue_func = process_queue
        self.check_zone_sync = check_zone_sync
        self.fix_soa_drift = fix_soa_drift
    
    def get_affiliated_domains(self) -> Set[str]:
        """Get affiliated domains using the domain module function"""
        return self.get_domains()

    def process_queue(self, max_domains: int, distribution: Tuple[int, int, int], dryrun: bool) -> Dict[str, Any]:
        """Process domain queue using the domain module function"""
        return self.process_queue_func(max_domains, distribution, dryrun)

    def load_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Load domain tracking data from database"""
        return self.db_manager.load_domain_tracking()

    def save_tracking(self, tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save domain tracking data to database"""
        return self.db_manager.save_domain_tracking(tracking)
    
    def get_domains_by_status(self, status: str) -> List[str]:
        """Get domains with a specified status from database"""
        return self.db_manager.get_domains_by_status(status)
    
    def handle_removed_zones(self, dryrun: bool) -> None:
        """Handle removed zones with grace period and cleanup"""
        from .domains import handle_removed_zones as handle_zones
        handle_zones(dryrun)


def main():
    """Main function to run the DNS synchronization process with injected dependencies"""
    # Parse command-line arguments
    args = parse_arguments()
    
    # Set up logging
    setup_logging(args.silent, args.log)
    
    # Instantiate adapters
    dns_api = PowerDnsApiAdapter()
    domain_manager = DomainManagerAdapter()
    
    # Ensure only one instance is running
    lock_file = single_instance()
    
    # Get settings
    settings = get_settings()
    
    # Inform about dry-run or write mode
    if args.dryrun:
        logging.info("=" * 80)
        logging.info("RUNNING IN DRY-RUN MODE - NO CHANGES WILL BE MADE")
        logging.info("Use --write to apply changes")
        logging.info("=" * 80)
    else:
        logging.info("=" * 80)
        logging.info("RUNNING IN WRITE MODE - CHANGES WILL BE APPLIED")
        logging.info("=" * 80)
    
    logging.info("Script started.")
    
    try:
        if args.domain:
            _process_single_domain(args, dns_api, domain_manager, settings)
        
        elif args.cleanup:
            logging.info("Running cleanup process for inactive domains")
            domain_manager.handle_removed_zones(args.dryrun)
        
        elif args.orphans:
            _process_orphaned_domains(args, domain_manager)
        
        else:
            _process_bulk_domains(args, dns_api, domain_manager)
        
        logging.info("Script completed successfully.")
    
    except Exception as e:
        logging.error(f"Error during execution: {str(e)}")
        logging.error(traceback.format_exc())
        sys.exit(1)
    finally:
        release_lock()


def _process_single_domain(args, dns_api, domain_manager, settings):
    """Process a single domain specified by the --domain argument"""
    from .delegation import check_authoritative_ns
    from .zones import check_zone_sync, fix_soa_drift
    
    logging.info(f"Processing single domain: {args.domain}")
    excluded_domains = settings['excluded_domains']
    if args.domain in excluded_domains:
        logging.info(f"{args.domain} explicitly excluded.")
        sys.exit(0)
    
    ns_result = check_authoritative_ns(args.domain)
    if not ns_result['verified']:
        logging.error(f"{args.domain} does not have correct NS records or delegation.")
        for error in ns_result.get('errors', []):
            logging.error(f"- {error}")
        sys.exit(1)
    
    try:
        zone_data = dns_api.get_zone(args.domain)
        
        # Check if zone doesn't exist
        if zone_data.get('error') == 'not_found':
            dns_api.create_zone(args.domain, args.dryrun, verbose=True)
        else:
            if args.stepbystep:
                proceed = input(f"Check zone sync for {args.domain}? (y/n): ").strip().lower() == 'y'
                if not proceed:
                    sys.exit(0)
                    
            sync_status = check_zone_sync(args.domain)
            if sync_status['sync_status'] != 'success':
                logging.warning(f"Sync issues detected for {args.domain}: {sync_status['error_message']}")
                if sync_status['soa_drift'] and sync_status['soa_drift'] > settings['max_soa_drift']:
                    logging.error(f"Critical SOA drift detected: {sync_status['soa_drift']}")
                    if args.stepbystep:
                        proceed = input(f"Attempt to fix SOA drift for {args.domain}? (y/n): ").strip().lower() == 'y'
                        if not proceed:
                            sys.exit(0)
                    success, message = fix_soa_drift(
                        args.domain,
                        sync_status['bind_serial'],
                        sync_status['pdns_serial'],
                        args.dryrun
                    )
                    if success:
                        logging.info(f"SOA drift correction: {message}")
                    else:
                        logging.error(f"Failed to fix SOA drift: {message}")
            else:
                logging.info(f"Zone {args.domain} is in sync!")
            
            tracking = domain_manager.load_tracking()
            tracking[args.domain] = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "active"
            }
            domain_manager.save_tracking(tracking)
            
    except Exception as e:
        logging.error(f"Error processing domain {args.domain}: {str(e)}")
        sys.exit(1)


def _process_orphaned_domains(args, domain_manager):
    """Process orphaned domains to check if they've been correctly delegated"""
    from .delegation import check_authoritative_ns
    
    logging.info("Processing orphaned domains")
    tracking = domain_manager.load_tracking()
    orphan_domains = domain_manager.get_domains_by_status("orphan")
    
    if orphan_domains:
        logging.info(f"Found {len(orphan_domains)} orphaned domains")
        for domain in orphan_domains:
            logging.info(f"Checking orphaned domain: {domain}")
            ns_result = check_authoritative_ns(domain)
            if ns_result['verified']:
                logging.info(f"Orphaned domain {domain} now resolves correctly, marking as active")
                tracking[domain]['status'] = 'active'
                tracking[domain]['timestamp'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            elif ns_result.get('errors'):
                logging.info(f"Orphaned domain {domain} still has delegation issues:")
                for error in ns_result.get('errors', []):
                    logging.info(f"- {error}")
        domain_manager.save_tracking(tracking)
    else:
        logging.info("No orphaned domains found")


def _process_bulk_domains(args, dns_api, domain_manager):
    """Process all affiliated domains in bulk mode"""
    from .domains import load_active_zones
    
    # Bulk processing of affiliated domains
    affiliated = domain_manager.get_affiliated_domains()
    logging.info(f"Found {len(affiliated)} affiliated domains in cPanel")
    active_tracking = load_active_zones()
    new_domains = affiliated - active_tracking
    if new_domains:
        logging.info(f"Found {len(new_domains)} new domains to process")
    
    tracking = domain_manager.load_tracking()
    
    # Mark new domains as active
    for domain in affiliated:
        if domain not in tracking:
            tracking[domain] = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "status": "active"
            }
    
    # Mark removed domains as inactive
    removed = {domain for domain, info in tracking.items() 
              if info['status'] == 'active'} - affiliated
    if removed:
        logging.info(f"Found {len(removed)} domains removed from cPanel")
        for domain in removed:
            tracking[domain]["status"] = "inactive"
            tracking[domain]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logging.info(f"Marked {domain} as inactive")
    
    # Process domain queue
    results = domain_manager.process_queue(
        max_domains=10, 
        distribution=(4,4,2), 
        dryrun=args.dryrun
    )
    
    # Save updated tracking data
    domain_manager.save_tracking(tracking)
    
    # Handle removed zones
    domain_manager.handle_removed_zones(args.dryrun)


# If this module is run directly, call main with adapter instances
if __name__ == "__main__":
    main()