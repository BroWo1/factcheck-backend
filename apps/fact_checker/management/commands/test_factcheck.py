from django.core.management.base import BaseCommand
from apps.fact_checker.models import FactCheckSession
from apps.fact_checker.tasks import perform_fact_check_task


class Command(BaseCommand):
    help = 'Test the fact-checking system with a sample claim'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'claim',
            nargs='?',
            type=str,
            default='The Earth is flat',
            help='Claim to fact-check'
        )
        parser.add_argument(
            '--async',
            action='store_true',
            help='Run asynchronously with Celery'
        )
    
    def handle(self, *args, **options):
        claim = options['claim']
        use_async = options['async']
        
        self.stdout.write(f"Testing fact-check system with claim: '{claim}'")
        
        # Create session
        session = FactCheckSession.objects.create(
            user_input=claim,
            status='pending'
        )
        
        self.stdout.write(f"Created session: {session.session_id}")
        
        if use_async:
            # Run with Celery
            self.stdout.write("Starting asynchronous analysis...")
            perform_fact_check_task.delay(str(session.session_id))
            self.stdout.write("Task queued. Check session status with: python manage.py check_session <session_id>")
        else:
            # Run synchronously (for testing)
            self.stdout.write("Starting synchronous analysis...")
            try:
                import asyncio
                from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService
                from django.conf import settings
                
                use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
                analysis_service = EnhancedAnalysisService(use_web_search=use_web_search)
                
                # Run async analysis
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
                try:
                    result = loop.run_until_complete(
                        analysis_service.perform_complete_analysis(session)
                    )
                    
                    self.stdout.write(f"Analysis completed: {result}")
                    
                finally:
                    loop.close()
                    
            except Exception as e:
                self.stdout.write(f"Error: {str(e)}")
        
        self.stdout.write(f"Session ID: {session.session_id}")
