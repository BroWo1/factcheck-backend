from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """Custom exception handler for API"""
    
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    if response is not None:
        # Log the exception
        logger.error(f"API Exception: {str(exc)} in {context['view'].__class__.__name__}")
        
        # Customize the response format
        custom_response_data = {
            'error': True,
            'message': str(exc),
            'status_code': response.status_code
        }
        
        # Add details for validation errors
        if hasattr(response, 'data') and isinstance(response.data, dict):
            custom_response_data['details'] = response.data
        
        response.data = custom_response_data
    
    return response
