from django.core.management.base import BaseCommand
from apps.fact_checker.models import FactCheckSession


class Command(BaseCommand):
    help = 'Check the status of a fact-checking session'
    
    def add_arguments(self, parser):
        parser.add_argument('session_id', type=str, help='Session ID to check')
    
    def handle(self, *args, **options):
        session_id = options['session_id']
        
        try:
            session = FactCheckSession.objects.get(session_id=session_id)
            
            self.stdout.write(f"Session: {session.session_id}")
            self.stdout.write(f"Status: {session.status}")
            self.stdout.write(f"Input: {session.user_input[:100]}...")
            self.stdout.write(f"Created: {session.created_at}")
            
            if session.status == 'completed':
                self.stdout.write(f"Verdict: {session.final_verdict}")
                self.stdout.write(f"Confidence: {session.confidence_score}")
                self.stdout.write(f"Summary: {session.analysis_summary}")
                
            # Show analysis steps
            steps = session.analysis_steps.all()
            self.stdout.write(f"\nAnalysis Steps ({len(steps)}):")
            for step in steps:
                self.stdout.write(f"  {step.step_number}. {step.description} - {step.status}")
                
        except FactCheckSession.DoesNotExist:
            self.stdout.write(f"Session {session_id} not found")
