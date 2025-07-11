import logging
from asgiref.sync import sync_to_async
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.conf import settings
from apps.fact_checker.models import FactCheckSession
from apps.fact_checker.tasks import perform_fact_check_task
from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService
from apps.api.serializers import (
    FactCheckRequestSerializer,
    FactCheckSessionSerializer,
    FactCheckSessionDetailSerializer,
    FactCheckStatusSerializer,
    FactCheckResultSerializer
)

logger = logging.getLogger(__name__)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def fact_check_create(request):
    """
    Create a new fact-checking session and start analysis
    """
    try:
        serializer = FactCheckRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            return Response({
                'error': 'Invalid input',
                'details': serializer.errors
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Create fact-check session
        session = FactCheckSession.objects.create(
            user_input=serializer.validated_data['user_input'],
            uploaded_image=serializer.validated_data.get('uploaded_image'),
            mode=serializer.validated_data.get('mode', 'fact_check'),
            user=request.user if request.user.is_authenticated else None
        )
        
        logger.info(f"Created fact-check session {session.session_id}")
        
        # Start asynchronous analysis
        perform_fact_check_task.delay(str(session.session_id))
        
        # Return session info
        session_serializer = FactCheckSessionSerializer(session)
        
        return Response({
            'session_id': str(session.session_id),
            'status': session.status,
            'message': 'Fact-check analysis started',
            'session_data': session_serializer.data
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        logger.error(f"Error creating fact-check session: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def fact_check_status(request, session_id):
    """
    Get current status and progress of a fact-checking session
    """
    try:
        session = get_object_or_404(FactCheckSession, session_id=session_id)
        
        # Get progress information synchronously by directly querying the models
        from apps.fact_checker.models import AnalysisStep
        
        steps = list(AnalysisStep.objects.filter(session=session).order_by('step_number'))
        
        progress_steps = [{
            'step_number': step.step_number,
            'step_type': step.step_type,
            'description': step.description,
            'status': step.status,
            'summary': step.summary, # Add this line to include the summary
            'completed_at': step.completed_at.isoformat() if step.completed_at else None
        } for step in steps]
        
        total_steps = len(progress_steps)
        completed_steps = len([step for step in progress_steps if step['status'] == 'completed'])
        failed_steps = len([step for step in progress_steps if step['status'] == 'failed'])
        current_step = next((step for step in progress_steps if step['status'] == 'in_progress'), None)
        
        # For web search mode, expect 4 steps instead of traditional 5-6 steps
        use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
        expected_steps = 4 if use_web_search else 5
        progress_percentage = (completed_steps / expected_steps) * 100 if expected_steps > 0 else 0
        
        progress_data = {
            'session_id': str(session.session_id),
            'status': session.status,
            'progress_percentage': min(progress_percentage, 100),  # Cap at 100%
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'expected_steps': expected_steps,
            'failed_steps': failed_steps,
            'current_step': {
                'step_number': current_step['step_number'] if current_step else None,
                'description': current_step['description'] if current_step else None,
                'step_type': current_step['step_type'] if current_step else None
            } if current_step else None,
            'steps': progress_steps,
            'web_search_mode': use_web_search
        }
        
        serializer = FactCheckStatusSerializer(progress_data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except FactCheckSession.DoesNotExist:
        return Response({
            'error': 'Session not found',
            'session_id': session_id
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error getting session status: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def fact_check_results(request, session_id):
    """
    Get detailed results of a completed fact-checking session
    """
    try:
        session = get_object_or_404(FactCheckSession, session_id=session_id)
        
        if session.status != 'completed':
            return Response({
                'error': 'Analysis not completed',
                'status': session.status,
                'message': 'Analysis is still in progress or failed'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Get detailed session data
        session_serializer = FactCheckSessionDetailSerializer(session)
        
        # Format results for response
        result_data = {
            'session_id': str(session.session_id),
            'status': session.status,
            'verdict': session.final_verdict,
            'confidence_score': session.confidence_score,
            'summary': session.analysis_summary,
            'created_at': session.created_at,
            'completed_at': session.completed_at,
            'sources': session_serializer.data['sources'],
            'analysis_steps': session_serializer.data['analysis_steps']
        }
        
        # Extract detailed results from analysis steps
        # For multi-step web search analysis, look for final_conclusion step
        # For traditional analysis, look for final_analysis or final_verdict step
        final_step = None
        
        # First try to find final_conclusion step (multi-step web search)
        final_step = session.analysis_steps.filter(
            step_type='final_conclusion',
            status='completed'
        ).first()
        
        # Fallback to final_analysis step (legacy single-step web search)
        if not final_step:
            final_step = session.analysis_steps.filter(
                step_type='final_analysis',
                status='completed'
            ).first()
        
        # Fallback to final_verdict step (traditional analysis)
        if not final_step:
            final_step = session.analysis_steps.filter(
                step_type='final_verdict',
                status='completed'
            ).first()
        
        if final_step and final_step.result_data:
            # Handle multi-step analysis results
            if final_step.step_type == 'final_conclusion':
                detailed_analysis = final_step.result_data.get('detailed_analysis', {})
                result_data.update({
                    'reasoning': detailed_analysis.get('reasoning'),
                    'key_evidence': detailed_analysis.get('key_evidence'),
                    'supporting_evidence': detailed_analysis.get('supporting_evidence'),
                    'contradictory_evidence': detailed_analysis.get('contradictory_evidence'),
                    'limitations': detailed_analysis.get('limitations'),
                    'recommendations': final_step.result_data.get('recommendations')
                })
            else:
                # Handle legacy single-step or traditional analysis results
                result_data.update({
                    'reasoning': final_step.result_data.get('reasoning'),
                    'key_evidence': final_step.result_data.get('key_evidence'),
                    'supporting_evidence': final_step.result_data.get('supporting_evidence'),
                    'contradictory_evidence': final_step.result_data.get('contradictory_evidence'),
                    'limitations': final_step.result_data.get('limitations'),
                    'recommendations': final_step.result_data.get('recommendations')
                })
        
        serializer = FactCheckResultSerializer(result_data)
        
        return Response(serializer.data, status=status.HTTP_200_OK)
        
    except FactCheckSession.DoesNotExist:
        return Response({
            'error': 'Session not found',
            'session_id': session_id
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error getting session results: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def fact_check_steps(request, session_id):
    """
    Get detailed analysis steps for transparency/debugging
    """
    try:
        session = get_object_or_404(FactCheckSession, session_id=session_id)
        
        # Get detailed session data including all related information
        session_serializer = FactCheckSessionDetailSerializer(session)
        
        # Add information about whether this was a multi-step analysis
        use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
        analysis_steps = session_serializer.data['analysis_steps']
        
        # Determine if this was a multi-step web search analysis
        multi_step_web_search = any(
            step['step_type'] in ['initial_web_search', 'deeper_exploration', 'source_credibility_evaluation', 'final_conclusion']
            for step in analysis_steps
        )
        
        return Response({
            'session_id': str(session.session_id),
            'status': session.status,
            'analysis_type': 'multi_step_web_search' if multi_step_web_search else ('web_search' if use_web_search else 'traditional'),
            'analysis_steps': analysis_steps,
            'search_queries': session_serializer.data['search_queries'],
            'sources_found': len(session_serializer.data['sources']),
            'gpt_interactions': len(session_serializer.data['gpt_interactions'])
        }, status=status.HTTP_200_OK)
        
    except FactCheckSession.DoesNotExist:
        return Response({
            'error': 'Session not found',
            'session_id': session_id
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error getting session steps: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def fact_check_list(request):
    """
    List recent fact-checking sessions (optionally filtered by user)
    """
    try:
        sessions = FactCheckSession.objects.all()
        
        # Filter by user if authenticated
        if request.user.is_authenticated:
            sessions = sessions.filter(user=request.user)
        
        # Apply pagination
        page_size = min(int(request.GET.get('page_size', 20)), 100)
        offset = int(request.GET.get('offset', 0))
        
        sessions = sessions[offset:offset + page_size]
        
        serializer = FactCheckSessionSerializer(sessions, many=True)
        
        return Response({
            'count': len(serializer.data),
            'results': serializer.data
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.error(f"Error listing sessions: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
def fact_check_delete(request, session_id):
    """
    Delete a fact-checking session
    """
    try:
        session = get_object_or_404(FactCheckSession, session_id=session_id)
        
        # Check permissions (only allow deletion of own sessions or if admin)
        if request.user.is_authenticated and session.user != request.user and not request.user.is_staff:
            return Response({
                'error': 'Permission denied'
            }, status=status.HTTP_403_FORBIDDEN)
        
        session.delete()
        
        return Response({
            'message': 'Session deleted successfully',
            'session_id': session_id
        }, status=status.HTTP_200_OK)
        
    except FactCheckSession.DoesNotExist:
        return Response({
            'error': 'Session not found',
            'session_id': session_id
        }, status=status.HTTP_404_NOT_FOUND)
        
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        return Response({
            'error': 'Internal server error',
            'message': str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def health_check(request):
    """
    Health check endpoint
    """
    return Response({
        'status': 'healthy',
        'message': 'Fact-check API is running'
    }, status=status.HTTP_200_OK)