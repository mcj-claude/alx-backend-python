"""
Custom exception handling for the messaging platform API.

Provides structured error responses and proper HTTP status codes.
"""

from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, DatabaseError
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class APIException(Exception):
    """
    Base exception class for API errors.
    
    Attributes:
        status_code (int): HTTP status code
        error_code (str): Machine-readable error code
        message (str): Human-readable error message
        details (dict): Additional error details
    """
    
    def __init__(self, message, error_code=None, status_code=status.HTTP_400_BAD_REQUEST, details=None):
        self.message = message
        self.error_code = error_code or 'api_error'
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self):
        """Convert exception to dictionary representation."""
        return {
            'error': {
                'code': self.error_code,
                'message': self.message,
                'details': self.details,
                'timestamp': timezone.now().isoformat(),
            }
        }


class ValidationError(APIException):
    """Raised when request data validation fails."""
    
    def __init__(self, message, field_errors=None):
        details = {}
        if field_errors:
            details['field_errors'] = field_errors
        super().__init__(message, 'validation_error', status.HTTP_400_BAD_REQUEST, details)


class AuthenticationError(APIException):
    """Raised when authentication fails."""
    
    def __init__(self, message="Authentication credentials were not provided or are invalid."):
        super().__init__(message, 'authentication_error', status.HTTP_401_UNAUTHORIZED)


class PermissionError(APIException):
    """Raised when user doesn't have required permissions."""
    
    def __init__(self, message="You do not have permission to perform this action."):
        super().__init__(message, 'permission_error', status.HTTP_403_FORBIDDEN)


class NotFoundError(APIException):
    """Raised when requested resource is not found."""
    
    def __init__(self, message="The requested resource was not found."):
        super().__init__(message, 'not_found', status.HTTP_404_NOT_FOUND)


class ConflictError(APIException):
    """Raised when there's a conflict with current state."""
    
    def __init__(self, message="The request conflicts with the current state of the resource."):
        super().__init__(message, 'conflict', status.HTTP_409_CONFLICT)


class RateLimitError(APIException):
    """Raised when rate limit is exceeded."""
    
    def __init__(self, message="Rate limit exceeded. Please try again later."):
        super().__init__(message, 'rate_limit_exceeded', status.HTTP_429_TOO_MANY_REQUESTS)


class ServerError(APIException):
    """Raised for internal server errors."""
    
    def __init__(self, message="An internal server error occurred."):
        super().__init__(message, 'server_error', status.HTTP_500_INTERNAL_SERVER_ERROR)


class ServiceUnavailableError(APIException):
    """Raised when service is temporarily unavailable."""
    
    def __init__(self, message="Service temporarily unavailable. Please try again later."):
        super().__init__(message, 'service_unavailable', status.HTTP_503_SERVICE_UNAVAILABLE)


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF.
    
    Args:
        exc: The exception instance
        context: Context dictionary containing view information
    
    Returns:
        Response: DRF Response with structured error data
    """
    logger.error(f"Exception occurred: {exc}", exc_info=True, extra={'context': context})
    
    # Call DRF's default exception handler first
    response = exception_handler(exc, context)
    
    # Handle specific exception types
    if isinstance(exc, DjangoValidationError):
        return handle_validation_error(exc, context)
    elif isinstance(exc, IntegrityError):
        return handle_integrity_error(exc, context)
    elif isinstance(exc, DatabaseError):
        return handle_database_error(exc, context)
    elif isinstance(exc, APIException):
        return handle_api_exception(exc, context)
    
    # Return the response if DRF handled it
    if response is not None:
        return enhance_error_response(response, exc, context)
    
    # Handle unexpected exceptions
    return handle_unexpected_error(exc, context)


def handle_validation_error(exc, context):
    """Handle Django validation errors."""
    field_errors = {}
    
    if hasattr(exc, 'error_dict'):
        # Form validation errors
        for field, errors in exc.error_dict.items():
            field_errors[field] = [str(error) for error in errors]
    elif hasattr(exc, 'error_list'):
        # Field validation errors
        field_errors['general'] = [str(error) for error in exc.error_list]
    
    error = ValidationError("Validation failed", field_errors=field_errors)
    return Response(error.to_dict(), status=error.status_code)


def handle_integrity_error(exc, context):
    """Handle database integrity errors."""
    error_message = str(exc).lower()
    
    if 'unique constraint' in error_message or 'duplicate key' in error_message:
        message = "A resource with this information already exists."
        error = ConflictError(message)
    elif 'foreign key' in error_message:
        message = "The referenced resource does not exist."
        error = ValidationError(message)
    else:
        message = "A database constraint was violated."
        error = ServerError(message)
    
    return Response(error.to_dict(), status=error.status_code)


def handle_database_error(exc, context):
    """Handle general database errors."""
    logger.error(f"Database error: {exc}", exc_info=True)
    error = ServerError("A database error occurred while processing the request.")
    return Response(error.to_dict(), status=error.status_code)


def handle_api_exception(exc, context):
    """Handle custom API exceptions."""
    return Response(exc.to_dict(), status=exc.status_code)


def enhance_error_response(response, exc, context):
    """Enhance the default DRF error response."""
    # If it's already a proper error response, just return it
    if response.status_code >= 400:
        # Add timestamp if not present
        if 'timestamp' not in response.data:
            if isinstance(response.data, dict) and 'error' in response.data:
                response.data['error']['timestamp'] = timezone.now().isoformat()
        return response
    
    # For other responses, return as-is
    return response


def handle_unexpected_error(exc, context):
    """Handle unexpected exceptions."""
    logger.error(f"Unexpected error: {exc}", exc_info=True, extra={'context': context})
    error = ServerError("An unexpected error occurred.")
    return Response(error.to_dict(), status=error.status_code)


# Utility functions for consistent error responses

def raise_validation_error(message, field_errors=None):
    """Utility function to raise validation errors."""
    raise ValidationError(message, field_errors=field_errors)


def raise_not_found(message=None):
    """Utility function to raise not found errors."""
    raise NotFoundError(message)


def raise_permission_error(message=None):
    """Utility function to raise permission errors."""
    raise PermissionError(message)


def raise_authentication_error(message=None):
    """Utility function to raise authentication errors."""
    raise AuthenticationError(message)


def raise_conflict_error(message=None):
    """Utility function to raise conflict errors."""
    raise ConflictError(message)


def raise_rate_limit_error(message=None):
    """Utility function to raise rate limit errors."""
    raise RateLimitError(message)


def raise_server_error(message=None):
    """Utility function to raise server errors."""
    raise ServerError(message)


def validate_required_fields(data, required_fields):
    """Validate that required fields are present and not empty."""
    missing_fields = []
    empty_fields = []
    
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
        elif data[field] is None or (isinstance(data[field], str) and not data[field].strip()):
            empty_fields.append(field)
    
    if missing_fields or empty_fields:
        field_errors = {}
        if missing_fields:
            field_errors['missing_fields'] = missing_fields
        if empty_fields:
            field_errors['empty_fields'] = empty_fields
        
        raise_validation_error("Required fields are missing or empty", field_errors)


def validate_email_format(email):
    """Validate email format."""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if not re.match(pattern, email):
        raise_validation_error("Invalid email format", {'email': ['Email format is invalid']})


def validate_phone_format(phone):
    """Validate phone number format."""
    import re
    # Basic phone validation (can be enhanced based on requirements)
    pattern = r'^\+?1?-?\.?\s?\(?(\d{3})\)?[-.\s]?(\d{3})[-.\s]?(\d{4})$'
    if not re.match(pattern, phone):
        raise_validation_error("Invalid phone number format", {'phone': ['Phone number format is invalid']})


def sanitize_html(content):
    """Basic HTML sanitization."""
    import re
    # Remove script tags and javascript: protocols
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.IGNORECASE | re.DOTALL)
    content = re.sub(r'javascript:', '', content, flags=re.IGNORECASE)
    content = re.sub(r'on\w+\s*=', '', content, flags=re.IGNORECASE)
    return content


def validate_content_length(content, max_length=5000):
    """Validate content length."""
    if len(content) > max_length:
        raise_validation_error(
            f"Content exceeds maximum length of {max_length} characters",
            {'content': [f'Content is too long (max {max_length} characters)']}
        )