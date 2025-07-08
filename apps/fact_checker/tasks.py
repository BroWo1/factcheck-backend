import logging
import asyncio
from celery import shared_task
from django.utils import timezone
from apps.fact_checker.models import FactCheckSession
from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def perform_fact_check_task(self, session_id: str):
    """
    Main Celery task for performing fact-checking analysis
    """
    try:
        logger.info(f"Starting fact-check task for session {session_id}")
        
        # Get session
        session = FactCheckSession.objects.get(session_id=session_id)
        
        # Create analysis service with web search setting
        from django.conf import settings
        use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
        analysis_service = EnhancedAnalysisService(use_web_search=use_web_search)
        
        # Run async analysis in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                analysis_service.perform_complete_analysis(session)
            )
            
            logger.info(f"Fact-check task completed for session {session_id}")
            
            # Send WebSocket update with final result
            send_websocket_update.delay(session_id, {
                'type': 'analysis_complete',
                'result': result
            })
            
            return result
            
        finally:
            loop.close()
            
    except FactCheckSession.DoesNotExist:
        error_msg = f"Session {session_id} not found"
        logger.error(error_msg)
        return {'error': error_msg}
        
    except Exception as e:
        error_msg = f"Error in fact-check task: {str(e)}"
        logger.error(error_msg)
        
        # Update session status on error
        try:
            session = FactCheckSession.objects.get(session_id=session_id)
            session.status = 'failed'
            session.completed_at = timezone.now()
            session.save()
        except:
            pass
        
        # Send error update via WebSocket
        send_websocket_update.delay(session_id, {
            'type': 'analysis_error',
            'error': error_msg
        })
        
        return {'error': error_msg}


@shared_task
def send_websocket_update(session_id: str, data: dict):
    """
    Send WebSocket update to connected clients
    """
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        
        # Send to group named after session_id
        async_to_sync(channel_layer.group_send)(
            f"fact_check_{session_id}",
            {
                'type': 'fact_check_update',
                'data': data
            }
        )
        
        logger.info(f"Sent WebSocket update for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error sending WebSocket update: {str(e)}")


@shared_task
def send_progress_update(session_id: str):
    """
    Send progress update via WebSocket
    """
    try:
        # Get current progress
        session = FactCheckSession.objects.get(session_id=session_id)
        from django.conf import settings
        use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
        analysis_service = EnhancedAnalysisService(use_web_search=use_web_search)
        progress_data = analysis_service.get_analysis_progress(session)
        
        # Send via WebSocket
        send_websocket_update.delay(session_id, {
            'type': 'progress_update',
            'progress': progress_data
        })
        
    except Exception as e:
        logger.error(f"Error sending progress update: {str(e)}")


@shared_task
def cleanup_old_sessions():
    """
    Periodic task to cleanup old sessions
    """
    try:
        from datetime import timedelta
        from django.utils import timezone
        
        # Delete sessions older than 30 days
        cutoff_date = timezone.now() - timedelta(days=30)
        
        old_sessions = FactCheckSession.objects.filter(
            created_at__lt=cutoff_date
        )
        
        count = old_sessions.count()
        old_sessions.delete()
        
        logger.info(f"Cleaned up {count} old sessions")
        
    except Exception as e:
        logger.error(f"Error in cleanup task: {str(e)}")


# Real-time progress tracking
class ProgressTracker:
    """Helper class for tracking and sending progress updates"""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
    
    def send_update(self, step_type: str, description: str, progress: float):
        """Send a progress update"""
        send_websocket_update.delay(self.session_id, {
            'type': 'step_update',
            'step_type': step_type,
            'description': description,
            'progress_percentage': progress,
            'timestamp': timezone.now().isoformat()
        })
