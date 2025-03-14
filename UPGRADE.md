# Upgrade Guide for DNSSync

This document describes the changes made to DNSSync and how to upgrade from the previous version.

## Key Changes

1. **New Package Structure**
   The code has been organized into a proper Python package structure with the following directories:
   ```
   dnssync/
   ├── dnssync.py (main script)
   ├── config.ini.example
   ├── README.md
   ├── UPGRADE.md
   └── dnssync_lib/
       ├── __init__.py
       ├── config.py
       ├── core.py
       ├── db_manager.py
       ├── error_handling.py
       ├── logger.py
       ├── utils.py
       └── ... (other modules)
   ```

2. **SQLite Database**
   - Domain tracking now uses SQLite instead of text files
   - Database file is created at `domain_tracking.db` in the main directory
   - Auto-recovery mechanism handles database corruption

3. **Error Handling**
   - Added circuit breaker to prevent cascading failures
   - Implemented retry mechanism with exponential backoff

## Upgrade Instructions

1. **Backup Your Data**
   ```bash
   cp -r /path/to/old/dnssync /path/to/dnssync.backup
   ```

2. **Install the New Version**
   ```bash
   # Copy the new files
   cp -r /path/to/new/dnssync/* /path/to/dnssync/
   
   # Make the main script executable
   chmod +x /path/to/dnssync/dnssync.py
   ```

3. **Update Configuration**
   ```bash
   # Create config.ini from the example if you don't have one
   cp /path/to/dnssync/config.ini.example /path/to/dnssync/config.ini
   
   # Edit the config file with your settings
   nano /path/to/dnssync/config.ini
   ```

4. **Migrate Domain Tracking Data**
   The system will automatically create a new database on first run. If you want to preserve your existing domain tracking data, run:
   ```bash
   python3 /path/to/dnssync/scripts/migrate_data.py
   ```

5. **Test the Installation**
   ```bash
   # Run in dry-run mode
   python3 /path/to/dnssync/dnssync.py --dryrun
   ```

## Rollback Instructions

If you need to revert to the previous version:
   ```bash
   # Remove the new version
   rm -rf /path/to/dnssync
   
   # Restore the backup
   cp -r /path/to/dnssync.backup /path/to/dnssync
   ```

## Common Issues

1. **ImportError: No module named dnssync_lib**
   - Make sure you're running the script from the correct directory
   - Check that the `dnssync_lib` directory exists and contains `__init__.py`

2. **Database Errors**
   - If you encounter database errors, the system will automatically recreate the database
   - Check permissions on the directory where the database file is located

3. **API Connection Issues**
   - The circuit breaker will prevent repeated failed API calls
   - Check your PowerDNS API settings in config.ini