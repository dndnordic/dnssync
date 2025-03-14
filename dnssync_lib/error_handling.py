#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# File: /home/singularity/dnssync/dnssync_lib/error_handling.py
# Description: Error handling utilities including circuit breaker and retry mechanisms
# Version: 1.0

import logging
import time
import functools
from typing import Callable, Any, Dict, Optional, TypeVar, cast
import random
from datetime import datetime, timedelta

# Type variable for function return type
T = TypeVar('T')

class CircuitBreakerError(Exception):
    """Exception raised when circuit breaker is open"""
    pass

class CircuitBreaker:
    """
    Circuit breaker pattern implementation to prevent cascading failures.
    
    The circuit breaker has three states:
    - CLOSED: Normal operation, all calls pass through
    - OPEN: Circuit is broken, all calls fail fast without executing
    - HALF-OPEN: After recovery timeout, one call is allowed to test if service is recovered
    """
    
    # Circuit states
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half-open'
    
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60, name: str = "default"):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of consecutive failures before opening circuit
            recovery_timeout: Time in seconds to wait before attempting recovery
            name: Name of this circuit breaker for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self.state = self.CLOSED
        self.failure_count = 0
        self.last_failure_time = None
        
    def __enter__(self):
        """Context manager entry point"""
        if self.state == self.OPEN:
            # Check if recovery timeout has elapsed
            if self.last_failure_time and datetime.now() > self.last_failure_time + timedelta(seconds=self.recovery_timeout):
                logging.info(f"Circuit {self.name} transitioning from OPEN to HALF-OPEN")
                self.state = self.HALF_OPEN
            else:
                raise CircuitBreakerError(f"Circuit {self.name} is OPEN")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point"""
        if exc_type is None:
            # Success, reset failure count
            self.success()
            return False
        else:
            # Failure, increment failure count
            self.failure()
            return False  # Don't suppress the exception
            
    def success(self):
        """Record successful operation"""
        if self.state == self.HALF_OPEN:
            logging.info(f"Circuit {self.name} recovered, transitioning to CLOSED")
            self.state = self.CLOSED
        self.failure_count = 0
        
    def failure(self):
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == self.CLOSED and self.failure_count >= self.failure_threshold:
            # Too many failures, open the circuit
            logging.warning(f"Circuit {self.name} opened after {self.failure_count} consecutive failures")
            self.state = self.OPEN
        elif self.state == self.HALF_OPEN:
            # Failed during recovery attempt, back to open
            logging.warning(f"Circuit {self.name} recovery failed, remaining OPEN")
            self.state = self.OPEN


def retry_with_backoff(max_retries: int = 3, backoff_factor: float = 2, 
                       jitter: bool = True, exceptions: tuple = (Exception,)) -> Callable:
    """
    Decorator for retrying a function with exponential backoff.
    
    Args:
        max_retries: Maximum number of retries
        backoff_factor: Multiplier for backoff time between retries
        jitter: Whether to add random jitter to backoff time
        exceptions: Tuple of exceptions that trigger a retry
        
    Returns:
        Decorated function
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            retry_count = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    retry_count += 1
                    if retry_count > max_retries:
                        logging.error(f"Maximum retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    # Calculate backoff time
                    backoff_time = backoff_factor ** retry_count
                    if jitter:
                        backoff_time = backoff_time * (0.5 + random.random())
                    
                    logging.warning(f"Retry {retry_count}/{max_retries} for {func.__name__} after {backoff_time:.2f}s: {str(e)}")
                    time.sleep(backoff_time)
        return cast(Callable[..., T], wrapper)
    return decorator