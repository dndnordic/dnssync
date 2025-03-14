#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/locks.py
# Description: Process Locking Mechanism for DNS Synchronization
# Version: 4.0

import os
import sys
import time
import json
import fcntl
import signal
import atexit
import logging
import hashlib
import subprocess
import errno
from datetime import datetime

# Constants
LOCK_FILE = '/tmp/dnssync.lock'
LOCK_STALE_THRESHOLD = 3600  # Lock considered stale after 1 hour

# Global variables
lock_file_handle = None  # Keep lock file handle in global scope

def acquire_lock():
    """
    Acquire process lock with multiple safeguards:
    1. File-based locking with fcntl
    2. PID verification to detect stale locks
    3. Timestamp tracking to detect abandoned locks
    4. Cleanup of stale locks
    
    Returns:
        file handle: Lock file handle to maintain lock
    """
    global lock_file_handle
    
    if os.path.exists(LOCK_FILE):
        # Check if lock is stale
        try:
            with open(LOCK_FILE, 'r') as f:
                try:
                    lock_data = json.loads(f.read().strip() or '{}')
                except json.JSONDecodeError:
                    lock_data = {}
                
                lock_pid = lock_data.get('pid')
                lock_time = lock_data.get('timestamp')
                
                # Check if PID exists
                pid_exists = False
                if lock_pid:
                    try:
                        os.kill(lock_pid, 0)  # Signal 0 tests if process exists
                        pid_exists = True
                    except OSError as e:
                        if e.errno == errno.ESRCH:  # No such process
                            pid_exists = False
                        else:  # Permission error or other
                            pid_exists = True  # Assume process exists if we can't check
                
                # Check if lock is stale by time
                lock_is_stale = False
                if lock_time:
                    try:
                        lock_timestamp = float(lock_time)
                        if time.time() - lock_timestamp > LOCK_STALE_THRESHOLD:
                            lock_is_stale = True
                    except (ValueError, TypeError):
                        pass  # Keep lock_is_stale as False if timestamp is invalid
                
                # If both PID doesn't exist and lock is stale, break the lock
                if (not pid_exists or lock_is_stale) and (not pid_exists or lock_is_stale):
                    logging.warning(f"Removing stale lock (PID: {lock_pid}, Time: {lock_time})")
                    # We don't remove here - we'll overwrite safely later
                else:
                    logging.error(f"Another instance is running (PID: {lock_pid}, Time: {lock_time})")
                    sys.exit(1)
        except Exception as e:
            logging.error(f"Error checking lock file: {e}")
            sys.exit(1)
    
    # Create or overwrite the lock file with our information
    script_path = os.path.abspath(__file__)
    script_hash = hashlib.md5(open(script_path, 'rb').read()).hexdigest()[:8]
    lock_data = {
        'pid': os.getpid(),
        'timestamp': time.time(),
        'hostname': subprocess.getoutput('hostname').strip(),
        'script_path': script_path,
        'script_hash': script_hash
    }
    
    try:
        lock_file_handle = open(LOCK_FILE, 'w')
        # Write PID and timestamp information
        lock_file_handle.write(json.dumps(lock_data))
        lock_file_handle.flush()
        
        # Acquire exclusive lock
        fcntl.flock(lock_file_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        logging.info(f"Lock acquired (PID: {os.getpid()})")
        
        # Register cleanup handlers
        atexit.register(release_lock)
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
        
        return lock_file_handle
    except IOError as e:
        if e.errno == errno.EAGAIN:
            logging.error("Failed to acquire lock: another instance is running")
        else:
            logging.error(f"Failed to acquire lock: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Unexpected error acquiring lock: {e}")
        sys.exit(1)

def release_lock():
    """Release the lock file if it exists"""
    global lock_file_handle
    if lock_file_handle:
        try:
            logging.info("Releasing lock...")
            fcntl.flock(lock_file_handle, fcntl.LOCK_UN)
            lock_file_handle.close()
            
            # Remove the lock file
            if os.path.exists(LOCK_FILE):
                try:
                    with open(LOCK_FILE, 'r') as f:
                        lock_data = json.loads(f.read().strip() or '{}')
                    
                    # Only remove if it's our PID
                    if lock_data.get('pid') == os.getpid():
                        os.unlink(LOCK_FILE)
                        logging.info("Lock file removed")
                    else:
                        logging.warning("Lock file owned by another process, not removing")
                except Exception as e:
                    logging.error(f"Error removing lock file: {e}")
        except Exception as e:
            logging.error(f"Error releasing lock: {e}")
        lock_file_handle = None

def signal_handler(signum, frame):
    """Handle termination signals to ensure lock release"""
    signame = signal.Signals(signum).name
    logging.info(f"Received signal {signame} ({signum}), exiting gracefully")
    release_lock()
    sys.exit(0)

def single_instance():
    """
    Ensure only one instance of the script is running
    
    Returns:
        file handle to lockfile (kept open to maintain lock)
    """
    return acquire_lock()