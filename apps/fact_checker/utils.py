"""
Utility functions for the fact-checking system
"""
import logging
from typing import List, Dict, Any
from django.conf import settings

logger = logging.getLogger(__name__)

# Credible news sources and their reliability scores
CREDIBLE_PUBLISHERS = {
    'reuters.com': {'name': 'Reuters', 'credibility': 0.95, 'bias': 'center'},
    'ap.org': {'name': 'Associated Press', 'credibility': 0.95, 'bias': 'center'},
    'bbc.com': {'name': 'BBC', 'credibility': 0.90, 'bias': 'center-left'},
    'npr.org': {'name': 'NPR', 'credibility': 0.88, 'bias': 'center-left'},
    'pbs.org': {'name': 'PBS', 'credibility': 0.88, 'bias': 'center'},
    'wsj.com': {'name': 'Wall Street Journal', 'credibility': 0.85, 'bias': 'center-right'},
    'nytimes.com': {'name': 'New York Times', 'credibility': 0.82, 'bias': 'center-left'},
    'washingtonpost.com': {'name': 'Washington Post', 'credibility': 0.82, 'bias': 'center-left'},
    'economist.com': {'name': 'The Economist', 'credibility': 0.85, 'bias': 'center'},
    'factcheck.org': {'name': 'FactCheck.org', 'credibility': 0.92, 'bias': 'center'},
    'snopes.com': {'name': 'Snopes', 'credibility': 0.90, 'bias': 'center'},
    'politifact.com': {'name': 'PolitiFact', 'credibility': 0.88, 'bias': 'center-left'},
}

# Academic and government domains (generally high credibility)
HIGH_CREDIBILITY_DOMAINS = [
    '.edu',  # Educational institutions
    '.gov',  # Government sites
    '.org',  # Non-profit organizations (context-dependent)
]

# Low credibility indicators
LOW_CREDIBILITY_INDICATORS = [
    'fake',
    'hoax',
    'conspiracy',
    'truth',  # Ironically, sites with "truth" in name are often unreliable
    'patriot',
    'freedom',
    'real',
    'insider',
]


def get_publisher_credibility(domain: str) -> float:
    """
    Get credibility score for a publisher domain
    """
    domain = domain.lower().replace('www.', '')
    
    # Check known credible publishers
    if domain in CREDIBLE_PUBLISHERS:
        return CREDIBLE_PUBLISHERS[domain]['credibility']
    
    # Check for high credibility domains
    for high_cred_domain in HIGH_CREDIBILITY_DOMAINS:
        if domain.endswith(high_cred_domain):
            return 0.85  # High but not perfect for unknown edu/gov sites
    
    # Check for low credibility indicators
    for indicator in LOW_CREDIBILITY_INDICATORS:
        if indicator in domain:
            return 0.2  # Low credibility
    
    # Default score for unknown domains
    return 0.5


def get_publisher_bias(domain: str) -> str:
    """
    Get political bias assessment for a publisher
    """
    domain = domain.lower().replace('www.', '')
    
    if domain in CREDIBLE_PUBLISHERS:
        return CREDIBLE_PUBLISHERS[domain]['bias']
    
    return 'unknown'


def format_verdict_for_display(verdict: str) -> Dict[str, Any]:
    """
    Format verdict for frontend display
    """
    verdict_mapping = {
        'true': {
            'label': 'True',
            'color': 'green',
            'icon': 'check-circle',
            'description': 'The claim is factually accurate based on available evidence.'
        },
        'likely': {
            'label': 'Likely True',
            'color': 'light-green',
            'icon': 'check',
            'description': 'The claim is probably accurate but may lack complete verification.'
        },
        'uncertain': {
            'label': 'Uncertain',
            'color': 'yellow',
            'icon': 'help',
            'description': 'Insufficient evidence to determine the accuracy of the claim.'
        },
        'suspicious': {
            'label': 'Suspicious',
            'color': 'orange',
            'icon': 'warning',
            'description': 'The claim has questionable elements and should be viewed with caution.'
        },
        'false': {
            'label': 'False',
            'color': 'red',
            'icon': 'x-circle',
            'description': 'The claim is factually incorrect based on available evidence.'
        }
    }
    
    return verdict_mapping.get(verdict.lower(), {
        'label': 'Unknown',
        'color': 'gray',
        'icon': 'question',
        'description': 'Unable to assess the claim.'
    })


def extract_key_claims(text: str) -> List[str]:
    """
    Extract key factual claims from text (simple implementation)
    """
    # This is a simplified version - in production, you might use NLP libraries
    sentences = text.split('.')
    
    # Look for sentences with factual indicators
    factual_indicators = [
        'is', 'are', 'was', 'were', 'has', 'have', 'will', 'contains',
        'causes', 'results in', 'leads to', 'according to', 'study shows',
        'research indicates', 'data reveals', 'statistics show'
    ]
    
    key_claims = []
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) > 20:  # Ignore very short sentences
            if any(indicator in sentence.lower() for indicator in factual_indicators):
                key_claims.append(sentence + '.')
    
    return key_claims[:5]  # Return top 5 claims


def generate_search_queries(claim: str, topic: str = None) -> List[str]:
    """
    Generate effective search queries for fact-checking
    """
    queries = []
    
    # Add the original claim
    queries.append(claim)
    
    # Add topic-based queries if available
    if topic:
        queries.append(f"{topic} fact check")
        queries.append(f"{topic} debunked")
        queries.append(f"{topic} evidence")
    
    # Add fact-checking specific queries
    queries.append(f'"{claim}" fact check')
    queries.append(f'"{claim}" true false')
    queries.append(f'"{claim}" debunked')
    queries.append(f'"{claim}" evidence')
    
    # Add news-specific queries
    queries.append(f"{claim} news")
    queries.append(f"{claim} report")
    
    return queries


def sanitize_user_input(text: str) -> str:
    """
    Sanitize user input for safety
    """
    # Remove potentially harmful content
    import re
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Limit length
    if len(text) > 5000:
        text = text[:5000]
    
    return text


def calculate_confidence_score(analysis_data: Dict[str, Any]) -> float:
    """
    Calculate overall confidence score based on analysis data
    """
    score = 0.5  # Base score
    
    # Adjust based on source quality
    sources = analysis_data.get('sources', [])
    if sources:
        avg_credibility = sum(s.get('credibility_score', 0.5) for s in sources) / len(sources)
        score += (avg_credibility - 0.5) * 0.3
    
    # Adjust based on source consensus
    supporting = sum(1 for s in sources if s.get('supports_claim') is True)
    contradicting = sum(1 for s in sources if s.get('supports_claim') is False)
    
    if supporting + contradicting > 0:
        consensus = abs(supporting - contradicting) / (supporting + contradicting)
        score += consensus * 0.2
    
    # Adjust based on source count
    if len(sources) >= 5:
        score += 0.1
    elif len(sources) >= 3:
        score += 0.05
    
    return min(max(score, 0.0), 1.0)  # Clamp between 0 and 1


# Service configuration utilities
def get_analysis_service():
    """
    Get the configured analysis service based on settings
    
    Returns:
        EnhancedAnalysisService: Configured with web search if enabled
    """
    from apps.fact_checker.services.enhanced_analysis_service import EnhancedAnalysisService
    use_web_search = getattr(settings, 'USE_WEB_SEARCH', False)
    return EnhancedAnalysisService(use_web_search=use_web_search)


def is_web_search_enabled() -> bool:
    """
    Check if web search is enabled in the current configuration
    
    Returns:
        bool: True if web search is enabled, False otherwise
    """
    return getattr(settings, 'USE_WEB_SEARCH', False)


def get_web_search_config() -> dict:
    """
    Get the current web search configuration
    
    Returns:
        dict: Web search configuration settings
    """
    return {
        'enabled': getattr(settings, 'USE_WEB_SEARCH', False),
        'context_size': getattr(settings, 'WEB_SEARCH_CONTEXT_SIZE', 'medium'),
        'user_location': getattr(settings, 'WEB_SEARCH_USER_LOCATION', {}),
    }


def get_service_info() -> dict:
    """
    Get information about the current service configuration
    
    Returns:
        dict: Service configuration information
    """
    web_search_enabled = is_web_search_enabled()
    
    return {
        'service_type': 'web_search' if web_search_enabled else 'traditional',
        'web_search_enabled': web_search_enabled,
        'config': get_web_search_config() if web_search_enabled else {},
        'description': (
            'Using ChatGPT web search for automated fact-checking' 
            if web_search_enabled 
            else 'Using traditional workflow with manual search and crawling'
        )
    }
