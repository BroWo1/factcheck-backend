import uuid
from django.db import models
from django.contrib.auth.models import User


class FactCheckSession(models.Model):
    """Main fact-checking session tracking"""
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('analyzing', 'Analyzing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    VERDICT_CHOICES = [
        ('true', 'True'),
        ('likely', 'Likely True'),
        ('uncertain', 'Uncertain'),
        ('suspicious', 'Suspicious'),
        ('false', 'False'),
    ]
    
    MODE_CHOICES = [
        ('fact_check', 'Fact Check'),
        ('research', 'Research'),
    ]
    
    session_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    user_input = models.TextField()
    uploaded_image = models.ImageField(upload_to='fact_check_images/', null=True, blank=True)
    mode = models.CharField(max_length=20, choices=MODE_CHOICES, default='fact_check')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    final_verdict = models.CharField(max_length=20, choices=VERDICT_CHOICES, null=True, blank=True)
    confidence_score = models.FloatField(null=True, blank=True)
    analysis_summary = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Session {self.session_id} - {self.status}"


class AnalysisStep(models.Model):
    """Individual analysis steps for real-time tracking"""
    
    STEP_TYPES = [
        # Traditional Workflow
        ('topic_analysis', 'Topic Analysis'),
        ('source_search', 'Source Search'),
        ('content_extraction', 'Content Extraction'),
        ('source_evaluation', 'Source Evaluation'),
        ('final_verdict', 'Final Verdict'),
        
        # Multi-Step Web Search Workflow
        ('initial_web_search', 'Initial Web Search'),
        ('deeper_exploration', 'Deeper Exploration'),
        ('source_credibility_evaluation', 'Source Credibility Evaluation'),
        ('final_conclusion', 'Final Conclusion'),

        # Research Workflow
        ('research_understanding', 'Research Understanding'),
        ('general_research', 'General Research'),
        ('specific_research', 'Specific Research'),
        ('research_report', 'Research Report'),

        # Legacy/Other (can be removed if no longer used)
        ('search', 'Legacy Search'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    session = models.ForeignKey(FactCheckSession, on_delete=models.CASCADE, related_name='analysis_steps')
    step_number = models.IntegerField()
    step_type = models.CharField(max_length=30, choices=STEP_TYPES)
    description = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    result_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    summary = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['step_number']
        unique_together = ['session', 'step_number']
    
    def __str__(self):
        return f"Step {self.step_number}: {self.step_type} - {self.status}"


class Source(models.Model):
    """Sources found and analyzed during fact-checking"""
    
    session = models.ForeignKey(FactCheckSession, on_delete=models.CASCADE, related_name='sources')
    url = models.URLField(max_length=2000)
    title = models.CharField(max_length=500, null=True, blank=True)
    publisher = models.CharField(max_length=200, null=True, blank=True)
    author = models.CharField(max_length=200, null=True, blank=True)
    credibility_score = models.FloatField(null=True, blank=True)
    content_summary = models.TextField(null=True, blank=True)
    extracted_claims = models.JSONField(default=list, blank=True)
    publish_date = models.DateTimeField(null=True, blank=True)
    accessed_at = models.DateTimeField(auto_now_add=True)
    is_primary_source = models.BooleanField(default=False)
    supports_claim = models.BooleanField(null=True, blank=True)
    relevance_score = models.FloatField(null=True, blank=True)
    
    class Meta:
        ordering = ['-relevance_score', '-credibility_score']
    
    def __str__(self):
        return f"Source: {self.title or self.url[:50]}"


class SearchQuery(models.Model):
    """Search queries and results tracking"""
    
    SEARCH_TYPES = [
        ('google', 'Google Search'),
        ('publisher_specific', 'Publisher Specific'),
        ('fact_check', 'Fact Check Sites'),
        ('academic', 'Academic Sources'),
    ]
    
    session = models.ForeignKey(FactCheckSession, on_delete=models.CASCADE, related_name='search_queries')
    query_text = models.CharField(max_length=500)
    search_type = models.CharField(max_length=30, choices=SEARCH_TYPES, default='google')
    results_count = models.IntegerField(default=0)
    successful = models.BooleanField(default=True)
    error_message = models.TextField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Query: {self.query_text[:50]} ({self.search_type})"


class ChatGPTInteraction(models.Model):
    """ChatGPT API interactions tracking"""
    
    INTERACTION_TYPES = [
        ('initial_analysis', 'Initial Analysis'),
        ('claim_extraction', 'Claim Extraction'),
        ('source_evaluation', 'Source Evaluation'),
        ('final_verdict', 'Final Verdict'),
    ]
    
    session = models.ForeignKey(FactCheckSession, on_delete=models.CASCADE, related_name='gpt_interactions')
    interaction_type = models.CharField(max_length=30, choices=INTERACTION_TYPES)
    prompt = models.TextField()
    response = models.TextField()
    model_used = models.CharField(max_length=50, default='gpt-4')
    tokens_used = models.IntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"GPT {self.interaction_type} - {self.timestamp}"
