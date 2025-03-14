# CLAUDE.md – Code Guidelines, Refactoring Overview & TODOS

## Overview

This document outlines the design principles, code guidelines, and file-specific TODOS for the DNSSYNC project. The aim is to ensure consistency and maintainability across the codebase by:
- Defining clear interface contracts for key components (e.g., DNS API interactions and domain management).
- Using dependency injection to decouple core orchestration from underlying implementations.
- Validating command-line arguments early to prevent conflicting options.
- Documenting version and outstanding tasks per module so that future changes don’t require rework in already-refactored files.

---

## Code Guidelines

### 1. Clear Interface Contracts
- **Definition:**  
  Define explicit interfaces (using Python’s `abc` module) for modules that interact with external systems (such as cPanel or PowerDNS) and for managing domains.
- **Implementation:**  
  For example, in `core.py` we introduced two abstract base classes:
  - `DnsApiInterface`: Enforces methods like `get_zone(domain)`, `update_zone(domain, zone_data)`, and `delete_zone(domain)`.
  - `DomainManagerInterface`: Expects methods for obtaining affiliated domains, processing domain queues, and handling tracking data.
- **Benefit:**  
  This ensures that the core orchestration only interacts with well-defined contracts. It also allows swapping out implementations (e.g., switching DNS providers) without modifying core logic.

### 2. Dependency Injection
- **Practice:**  
  Instead of hardcoding calls to specific functions or classes, pass concrete implementations (adapters) into the core orchestration functions.
- **Example in core.py:**  
  Adapter classes (e.g., `PowerDnsApiAdapter` and `DomainManagerAdapter`) wrap existing functions (from modules like `pdns.py` and `domains.py`) so that core logic only depends on the interfaces.
- **Benefit:**  
  This decouples modules, improves testability, and makes the system more flexible and scalable.

### 3. Argument Validation
- **Focus:**  
  Validate command-line arguments as early as possible to catch conflicting options.
- **Examples of Validations:**  
  - `--write` and `--dryrun` must not be specified simultaneously.
  - `--stepbystep` should only be allowed when processing a single domain (i.e., when `--domain` is specified).
  - `--disable_bidirectional` should not be used in combination with `--cleanup`.
- **Implementation:**  
  We added a `validate_arguments(args)` function in `config.py` and invoked it early in the main script wrapper (`dnssync-script.py`).

### 4. Modularization and Scalability
- **Separation of Concerns:**  
  Each module should have a clearly defined responsibility. For instance:
  - `config.py`: Manages configuration and argument validation.
  - `core.py`: Orchestrates the overall workflow using injected dependencies.
  - `zones.py`: Handles zone file operations like validation, reload, backup, and SOA drift correction.
- **Versioning & TODOS:**  
  Each file maintains version notes and a list of outstanding tasks, ensuring future changes are coordinated.

---

## Key Refactoring in core.py

In the modified **core.py**, we applied the following:
- **Interface Definitions:**  
  Two abstract base classes (`DnsApiInterface` and `DomainManagerInterface`) define the contracts for DNS API and domain management operations.
- **Adapter Classes:**  
  - `PowerDnsApiAdapter`: Wraps functions from `pdns.py` to implement `DnsApiInterface`.
  - `DomainManagerAdapter`: Wraps functions from `domains.py` to implement `DomainManagerInterface`.
- **Dependency Injection:**  
  The `main()` function now accepts instances of these interfaces and uses them throughout the orchestration logic.
- **Command-Line Argument Handling:**  
  The script uses the parsed arguments (via `parse_arguments()`) to determine the operation mode (single-domain, cleanup, or orphans) and to prompt interactively if `--stepbystep` is enabled (only in single-domain mode).
- **Error Handling and Logging:**  
  The orchestration logic includes robust logging and error reporting, ensuring that any issues (such as failed API calls or synchronization problems) are clearly logged.

---

## File-Specific TODOS and Version Information

### config.py
- **Version:** 3.3
- **TODOS:**
  - Update argument parsing in `utils.py` to incorporate early validation.
  - Enhance documentation for configuration settings.
  - (Added) Function `validate_arguments(args)` to check for conflicting flags.

### locks.py
- **Version:** 3.3
- **TODOS:**
  - Add more granular logging for lock operations.
  - Implement configurable lock file location and custom timeouts.
  - Create a mechanism for force-breaking stuck locks.
  - Enhance cross-process lock verification.

### domains.py
- **Version:** 3.3
- **TODOS:**
  - Improve error handling and exception messages.
  - Implement caching for DNS and WHOIS lookups.
  - Add IPv6 support for nameserver resolution.
  - Increase logging detail in delegation traces.
  - Enhance resilience to temporary DNS failures.

### core.py
- **Version:** 3.4
- **TODOS:**
  - Refine interface contracts and dependency injection further if needed.
  - Consider splitting orchestration logic into smaller controllers (e.g., sync vs. cleanup).
  - (Optional) Add more inline documentation for clarity.

### zones.py
- **Version:** 3.3
- **TODOS:**
  - Implement additional validation checks for zone file modifications.
  - Add support for custom SOA record parameters.
  - Develop a comprehensive logging mechanism for zone operations.

### logger.py
- **Version:** 3.3
- **TODOS:**
  - Add support for log rotation and configurable log formats.
  - Create methods for dynamic log level adjustments.
  - Enhance contextual logging.
  - Secure log file permissions.

### dnssync-script.py
- **Version:** 3.5
- **TODOS:**
  - Validate argument conflicts early (using `validate_arguments(args)`).
  - Improve environment initialization.
  - Ensure mutual exclusivity for operation mode flags (e.g., `--domain`, `--cleanup`, `--orphans`).

### pdns-module.py
- **Version:** 3.4
- **TODOS:**
  - Standardize error handling and API response validation.
  - Expand functionality for disconnecting zones with detailed logging if necessary.

### soa-module.py
- **Version:** 3.3
- **TODOS:**
  - Consider consolidating SOA record operations with `zones.py`.
  - Improve error handling and robustness.

### system.py
- **Version:** 3.3
- **TODOS:**
  - Implement DNS service health checks.
  - Add system resource monitoring.
  - Improve version detection for OS, cPanel, BIND, and PowerDNS.

### utils.py
- **Version:** (Not explicitly versioned)
- **TODOS:**
  - Update argument parsing to incorporate validations.
  - Organize options into mutually exclusive groups.
  - Enhance documentation for utility functions.

---

## Final Notes

- **Consistency:**  
  All future modifications should follow these guidelines to maintain clear interfaces, consistent dependency injection, and robust error handling.
- **Documentation & Versioning:**  
  Keep this document updated whenever changes are made. This ensures that each file's version and outstanding tasks are visible to all contributors.
- **Testing & Security:**  
  Ensure all code is tested, adheres to security best practices, and includes comprehensive inline documentation.

This CLAUDE.md file serves as a living document to guide further development and ensure that refactoring efforts (especially in core orchestration and argument validation) are maintained consistently across the codebase.
