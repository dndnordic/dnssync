# DNSSync

A DNS zone synchronization and monitoring tool for cPanel environments. Manages synchronization between BIND and PowerDNS configurations.

## Features

- Synchronize DNS zones between cPanel's BIND configuration and PowerDNS
- Monitor delegation status for domains
- Clean up inactive domains after a grace period
- Detect and fix SOA serial drift
- Handle bidirectional synchronization

## Key Improvements (March 2025)

1. **Standardized File Structure**
   - Implemented proper Python package structure
   - Standardized file naming conventions
   - Created appropriate `__init__.py` files

2. **Interface-Based Architecture**
   - Completed interface-based design with dependency injection
   - Added abstract base classes with clear contracts
   - Implemented adapter pattern for core components

3. **Database Storage**
   - Replaced file-based domain tracking with SQLite
   - Implemented auto-recovery for database corruption
   - Added efficient querying for domain status

4. **Error Handling**
   - Added circuit breaker pattern to prevent cascading failures
   - Implemented retry mechanism with exponential backoff
   - Enhanced error reporting and recovery

5. **Code Organization**
   - Split functionality into manageable modules
   - Removed code duplication
   - Implemented proper type hints
   - Better command-line argument validation

## Usage

```
python dnssync.py [options]
```

### Options

- `--domain DOMAIN`: Process a single domain
- `--cleanup`: Run cleanup process for inactive domains
- `--orphans`: Check orphaned domains
- `--dryrun`: Run without making changes (default)
- `--write`: Apply changes
- `--stepbystep`: Interactive mode for single domain processing
- `--disable_bidirectional`: Disable bidirectional sync
- `--silent`: Suppress console output
- `--log`: Show log messages

## Configuration

Configuration is stored in `config.ini` in the application directory. See `config.ini.example` for available options.