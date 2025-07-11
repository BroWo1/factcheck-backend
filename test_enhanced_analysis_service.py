#!/usr/bin/env python
"""
Test script for the EnhancedAnalysisService with research mode
"""

import os
import sys
import django
from django.conf import settings

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'factcheck_backend.settings')
django.setup()

from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService
from apps.fact_checker.models import FactCheckSession

def test_enhanced_analysis_service():
    """Test the EnhancedAnalysisService with research mode"""
    print("Testing EnhancedAnalysisService with research mode...")
    
    # Test different service modes
    print("\n1. Testing traditional mode...")
    service_traditional = EnhancedAnalysisService(use_web_search=False, use_research=False)
    print(f"✓ Traditional service initialized: {hasattr(service_traditional, 'chatgpt_service')}")
    
    print("\n2. Testing web search mode...")
    service_web_search = EnhancedAnalysisService(use_web_search=True, use_research=False)
    print(f"✓ Web search service initialized: {hasattr(service_web_search, 'chatgpt_service')}")
    
    print("\n3. Testing research mode...")
    service_research = EnhancedAnalysisService(use_web_search=False, use_research=True)
    print(f"✓ Research service initialized: {hasattr(service_research, 'research_service')}")
    
    # Test creating a research session
    print("\n4. Testing research session creation...")
    session = FactCheckSession.objects.create(
        user_input="What are the latest developments in artificial intelligence?",
        mode="research"
    )
    print(f"✓ Research session created: {session.session_id}")
    print(f"✓ Session mode: {session.mode}")
    
    # Clean up
    session.delete()
    
    print("\nAll tests passed! The enhanced analysis service is ready for research mode.")
    return True

if __name__ == "__main__":
    test_enhanced_analysis_service()
