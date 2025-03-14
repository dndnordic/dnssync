#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/db_manager.py
# Description: SQLite database manager for dnssync domain tracking
# Version: 1.0

import os
import sqlite3
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

class DatabaseManager:
    """Manages SQLite database operations for domain tracking with failsafe recovery"""
    
    def __init__(self, db_path: str = None):
        """Initialize database manager with specified or default path"""
        if db_path is None:
            # Default to a database in the same directory as this file
            self.db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'domain_tracking.db')
        else:
            self.db_path = db_path
            
        self.conn = None
        self.initialize_database()
    
    def initialize_database(self) -> None:
        """Create tables if they don't exist or recreate if corrupt"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            # Enable foreign keys
            self.conn.execute("PRAGMA foreign_keys = ON")
            
            # Create domains table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS domains (
                    domain TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            ''')
            
            # Test query to verify database is functional
            self.conn.execute("SELECT COUNT(*) FROM domains")
            self.conn.commit()
            
        except sqlite3.DatabaseError as e:
            logging.error(f"Database error: {e}. Recreating database.")
            self._recreate_database()
    
    def _recreate_database(self) -> None:
        """Recreate database in case of corruption"""
        # Close connection if open
        if self.conn:
            try:
                self.conn.close()
            except:
                pass
        
        # Remove corrupt database
        try:
            if os.path.exists(self.db_path):
                os.remove(self.db_path)
                logging.warning(f"Removed corrupt database at {self.db_path}")
        except Exception as e:
            logging.error(f"Failed to remove corrupt database: {e}")
        
        # Create new database
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute("PRAGMA foreign_keys = ON")
            
            # Create domains table
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS domains (
                    domain TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT
                )
            ''')
            
            self.conn.commit()
            logging.info("Database recreated successfully")
        except Exception as e:
            logging.critical(f"Failed to recreate database: {e}")
            raise
    
    def load_domain_tracking(self) -> Dict[str, Dict[str, Any]]:
        """Load domain tracking data from database"""
        tracking = {}
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT domain, status, timestamp, metadata FROM domains")
            
            for row in cursor.fetchall():
                domain, status, timestamp, metadata = row
                tracking[domain] = {
                    "status": status,
                    "timestamp": timestamp
                }
                
                # Add metadata if it exists
                if metadata:
                    try:
                        metadata_dict = json.loads(metadata)
                        for key, value in metadata_dict.items():
                            tracking[domain][key] = value
                    except json.JSONDecodeError:
                        logging.warning(f"Invalid metadata format for domain {domain}")
            
            return tracking
        except sqlite3.Error as e:
            logging.error(f"Error loading domain tracking: {e}")
            self._recreate_database()
            return {}
    
    def save_domain_tracking(self, tracking: Dict[str, Dict[str, Any]]) -> bool:
        """Save domain tracking data to database"""
        try:
            cursor = self.conn.cursor()
            
            # Begin transaction
            self.conn.execute("BEGIN TRANSACTION")
            
            for domain, data in tracking.items():
                # Extract required fields
                status = data.get("status", "unknown")
                timestamp = data.get("timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                
                # Extract metadata (any fields besides status and timestamp)
                metadata = {k: v for k, v in data.items() if k not in ["status", "timestamp"]}
                metadata_json = json.dumps(metadata) if metadata else None
                
                # Upsert domain record
                cursor.execute(
                    """
                    INSERT INTO domains (domain, status, timestamp, metadata)
                    VALUES (?, ?, ?, ?) 
                    ON CONFLICT(domain) DO UPDATE SET
                        status = ?,
                        timestamp = ?,
                        metadata = ?
                    """,
                    (domain, status, timestamp, metadata_json, status, timestamp, metadata_json)
                )
            
            # Commit transaction
            self.conn.commit()
            return True
            
        except sqlite3.Error as e:
            logging.error(f"Error saving domain tracking: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            self._recreate_database()
            return False
    
    def get_domains_by_status(self, status: str) -> List[str]:
        """Get list of domains with specified status"""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT domain FROM domains WHERE status = ?", (status,))
            return [row[0] for row in cursor.fetchall()]
        except sqlite3.Error as e:
            logging.error(f"Error getting domains by status: {e}")
            self._recreate_database()
            return []
    
    def update_domain_status(self, domain: str, status: str) -> bool:
        """Update status for a specific domain"""
        try:
            cursor = self.conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            cursor.execute(
                """
                UPDATE domains 
                SET status = ?, timestamp = ? 
                WHERE domain = ?
                """, 
                (status, timestamp, domain)
            )
            
            if cursor.rowcount == 0:
                # Domain doesn't exist, insert it
                cursor.execute(
                    "INSERT INTO domains (domain, status, timestamp) VALUES (?, ?, ?)",
                    (domain, status, timestamp)
                )
            
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logging.error(f"Error updating domain status: {e}")
            try:
                self.conn.rollback()
            except:
                pass
            return False
    
    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            try:
                self.conn.close()
            except sqlite3.Error:
                pass