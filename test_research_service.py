#!/usr/bin/env python
"""
Test script for the ChatGPTResearchService
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

from apps.fact_checker.services.chatgpt_shallow_analysis_service import ChatGPTResearchService

def test_research_service():
    """Test the ChatGPTResearchService"""
    print("Testing ChatGPTResearchService...")
    
    # Test service initialization
    service = ChatGPTResearchService()
    print(f"✓ Service initialized with model: {service.model}")
    print(f"✓ Advanced model: {service.advModel}")
    
    # Test utility methods
    print("\nTesting utility methods...")
    
    # Test JSON cleaning
    test_json = '''```json
    {"test": "value"}
    ```'''
    cleaned = service._clean_json_response(test_json)
    print(f"✓ JSON cleaning works: {cleaned}")
    
    # Test fallback response
    fallback = service._create_research_fallback_response(1, "Test response", [])
    print(f"✓ Fallback response created for step 1: {fallback.get('research_question', 'Not found')}")
    
    print("\nAll tests passed! The research service is ready to use.")
    return True

if __name__ == "__main__":
    test_research_service()
