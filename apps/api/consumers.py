import json
import logging
from django.utils import timezone
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from apps.fact_checker.models import FactCheckSession

logger = logging.getLogger(__name__)


class FactCheckConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time fact-checking updates"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get session_id from URL
            self.session_id = self.scope['url_route']['kwargs']['session_id']
            self.group_name = f"fact_check_{self.session_id}"
            
            # Verify session exists
            session_exists = await self.session_exists(self.session_id)
            if not session_exists:
                logger.warning(f"WebSocket connection attempted for non-existent session: {self.session_id}")
                await self.close()
                return
            
            # Join group
            await self.channel_layer.group_add(
                self.group_name,
                self.channel_name
            )
            
            # Accept connection
            await self.accept()
            
            logger.info(f"WebSocket connected for session {self.session_id}")
            
            # Send initial status
            await self.send_initial_status()
            
        except Exception as e:
            logger.error(f"Error connecting WebSocket: {str(e)}")
            await self.close()
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Leave group
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )
            
            logger.info(f"WebSocket disconnected for session {self.session_id}")
            
        except Exception as e:
            logger.error(f"Error disconnecting WebSocket: {str(e)}")
    
    async def receive(self, text_data):
        """Handle messages from WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            if message_type == 'get_status':
                await self.send_current_status()
            elif message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': str(timezone.now())
                }))
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {str(e)}")
    
    async def fact_check_update(self, event):
        """Handle fact-check updates from group"""
        try:
            # Send update to WebSocket
            await self.send(text_data=json.dumps({
                'type': 'update',
                'data': event['data']
            }))
            
        except Exception as e:
            logger.error(f"Error sending fact-check update: {str(e)}")
    
    async def send_initial_status(self):
        """Send initial status when client connects"""
        try:
            from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService
            from django.conf import settings
            
            session = await self.get_session(self.session_id)
            if session:
                use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
                analysis_service = EnhancedAnalysisService(use_web_search=use_web_search)
                progress_data = await analysis_service.get_analysis_progress(session)
                
                await self.send(text_data=json.dumps({
                    'type': 'initial_status',
                    'data': progress_data
                }))
                
        except Exception as e:
            logger.error(f"Error sending initial status: {str(e)}")
    
    async def send_current_status(self):
        """Send current status on request"""
        try:
            from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService
            from django.conf import settings
            
            session = await self.get_session(self.session_id)
            if session:
                use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
                analysis_service = EnhancedAnalysisService(use_web_search=use_web_search)
                progress_data = await analysis_service.get_analysis_progress(session)
                
                await self.send(text_data=json.dumps({
                    'type': 'status_response',
                    'data': progress_data
                }))
                
        except Exception as e:
            logger.error(f"Error sending current status: {str(e)}")
    
    @database_sync_to_async
    def session_exists(self, session_id):
        """Check if session exists"""
        try:
            return FactCheckSession.objects.filter(session_id=session_id).exists()
        except Exception:
            return False
    
    @database_sync_to_async
    def get_session(self, session_id):
        """Get session object"""
        try:
            return FactCheckSession.objects.get(session_id=session_id)
        except FactCheckSession.DoesNotExist:
            return None
