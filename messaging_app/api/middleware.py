"""
Custom middleware for the messaging platform API.

Provides request timing, security headers, and performance monitoring.
"""

import time
import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


class RequestTimingMiddleware(MiddlewareMixin):
    """
    Middleware to measure and log request processing time.
    
    Tracks request duration and adds it to response headers for monitoring.
    """
    
    def process_request(self, request):
        """Start timing when request is received."""
        request._start_time = time.time()
    
    def process_response(self, request, response):
        """Calculate and log request duration."""
        if hasattr(request, '_start_time'):
            duration = time.time() - request._start_time
            
            # Add timing header to response
            response['X-Request-Duration'] = f"{duration:.3f}s"
            
            # Log slow requests
            if duration > 2.0:  # Log requests taking more than 2 seconds
                logger.warning(
                    f"Slow request: {request.method} {request.path} "
                    f"took {duration:.3f}s from {request.META.get('REMOTE_ADDR')}"
                )
            
            # Log to database query logs if available
            if hasattr(connection, 'queries') and connection.queries:
                query_count = len(connection.queries)
                query_time = sum(float(q.get('time', 0)) for q in connection.queries)
                
                # Cache slow database queries
                if query_time > 1.0:
                    cache_key = f"slow_query:{request.path}:{hash(str(request.GET))}"
                    cache.set(cache_key, {
                        'path': request.path,
                        'duration': query_time,
                        'query_count': query_count,
                        'timestamp': time.time()
                    }, 300)  # Cache for 5 minutes
        
        return response


class SecurityHeadersMiddleware(MiddlewareMixin):
    """
    Middleware to add security headers to all responses.
    
    Provides additional security protections against common web vulnerabilities.
    """
    
    def process_response(self, request, response):
        """Add security headers to response."""
        # Content Security Policy
        response['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self' wss: ws:; "
            "frame-ancestors 'none';"
        )
        
        # XSS Protection
        response['X-XSS-Protection'] = '1; mode=block'
        
        # Content Type Options
        response['X-Content-Type-Options'] = 'nosniff'
        
        # Frame Options
        response['X-Frame-Options'] = 'DENY'
        
        # Referrer Policy
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Permissions Policy (formerly Feature Policy)
        response['Permissions-Policy'] = (
            'camera=(), '
            'microphone=(), '
            'geolocation=(), '
            'interest-cohort=()'
        )
        
        return response


class APIHealthCheckMiddleware(MiddlewareMixin):
    """
    Middleware to provide health check information.
    
    Adds health status information to responses.
    """
    
    def process_response(self, request, response):
        """Add health check information to response headers."""
        # Add basic health check info
        response['X-API-Status'] = 'healthy'
        response['X-API-Version'] = '1.0.0'
        
        return response