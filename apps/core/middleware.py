import logging
import time
import asyncio
from asgiref.sync import iscoroutinefunction

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    """
    Modern, async-aware middleware for logging API requests.
    This middleware works with both sync and async views.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.async_mode = iscoroutinefunction(get_response)

    def __call__(self, request):
        if self.async_mode:
            return self.__acall__(request)
        else:
            return self.__sync_call__(request)

    async def __acall__(self, request):
        start_time = time.time()
        
        if request.path.startswith('/api/'):
            logger.info(f"API Request: {request.method} {request.path} from {request.META.get('REMOTE_ADDR')}")

        try:
            response = await self.get_response(request)
            
            if request.path.startswith('/api/'):
                duration = time.time() - start_time
                logger.info(f"API Response: {response.status_code} for {request.method} {request.path} ({duration:.3f}s)")
            
            return response
        except Exception as e:
            if request.path.startswith('/api/'):
                logger.error(f"API Exception: {str(e)} for {request.method} {request.path}")
            raise

    def __sync_call__(self, request):
        start_time = time.time()
        
        if request.path.startswith('/api/'):
            logger.info(f"API Request: {request.method} {request.path} from {request.META.get('REMOTE_ADDR')}")

        try:
            response = self.get_response(request)
            
            if request.path.startswith('/api/'):
                duration = time.time() - start_time
                logger.info(f"API Response: {response.status_code} for {request.method} {request.path} ({duration:.3f}s)")
            
            return response
        except Exception as e:
            if request.path.startswith('/api/'):
                logger.error(f"API Exception: {str(e)} for {request.method} {request.path}")
            raise
