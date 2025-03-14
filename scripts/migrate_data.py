#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/scripts/migrate_data.py
# Description: Migration script to convert file-based domain tracking to SQLite database
# Version: 1.0

import os
import sys
import csv
from datetime import datetime

# Add parent directory to sys.path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parent_dir)

from dnssync_lib.db_manager import DatabaseManager
from dnssync_lib.config import get_settings

def migrate_active_zones():
    """Migrate active zones file to database"""
    settings = get_settings()
    active_zones_file = settings['active_zones_file']
    
    if not os.path.exists(active_zones_file):
        print(f"Active zones file not found: {active_zones_file}")
        return 0
    
    db = DatabaseManager()
    tracking = db.load_domain_tracking()
    
    # Read active zones
    migrated = 0
    with open(active_zones_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                domain = line.lower()
                if domain not in tracking:
                    tracking[domain] = {
                        "status": "active",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    migrated += 1
                elif tracking[domain]["status"] != "active":
                    tracking[domain]["status"] = "active"
                    tracking[domain]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    migrated += 1
    
    db.save_domain_tracking(tracking)
    return migrated

def migrate_removed_zones():
    """Migrate removed zones file to database"""
    settings = get_settings()
    remove_zones_file = settings['remove_zones_file']
    
    if not os.path.exists(remove_zones_file):
        print(f"Removed zones file not found: {remove_zones_file}")
        return 0
    
    db = DatabaseManager()
    tracking = db.load_domain_tracking()
    
    # Read removed zones
    migrated = 0
    with open(remove_zones_file, 'r') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                domain = row[0].strip().lower()
                timestamp = row[1].strip()
                if domain not in tracking:
                    tracking[domain] = {
                        "status": "inactive",
                        "timestamp": timestamp
                    }
                    migrated += 1
                elif tracking[domain]["status"] != "inactive":
                    tracking[domain]["status"] = "inactive"
                    tracking[domain]["timestamp"] = timestamp
                    migrated += 1
    
    db.save_domain_tracking(tracking)
    return migrated

def migrate_orphans():
    """Migrate orphaned domains file to database"""
    settings = get_settings()
    orphans_file = settings.get('orphans_file')
    
    if not orphans_file or not os.path.exists(orphans_file):
        print(f"Orphans file not found: {orphans_file}")
        return 0
    
    db = DatabaseManager()
    tracking = db.load_domain_tracking()
    
    # Read orphaned domains
    migrated = 0
    with open(orphans_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                domain = line.lower()
                if domain not in tracking:
                    tracking[domain] = {
                        "status": "orphan",
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    }
                    migrated += 1
                elif tracking[domain]["status"] != "orphan":
                    tracking[domain]["status"] = "orphan"
                    tracking[domain]["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    migrated += 1
    
    db.save_domain_tracking(tracking)
    return migrated

def main():
    """Main migration function"""
    print("Starting migration of domain tracking data...")
    
    # Migrate active zones
    active_migrated = migrate_active_zones()
    print(f"Migrated {active_migrated} active domains")
    
    # Migrate removed zones
    removed_migrated = migrate_removed_zones()
    print(f"Migrated {removed_migrated} inactive domains")
    
    # Migrate orphaned domains
    orphans_migrated = migrate_orphans()
    print(f"Migrated {orphans_migrated} orphaned domains")
    
    total_migrated = active_migrated + removed_migrated + orphans_migrated
    print(f"Migration complete. Total domains migrated: {total_migrated}")

if __name__ == "__main__":
    main()