from rest_framework import serializers
from apps.fact_checker.models import FactCheckSession, AnalysisStep, Source, SearchQuery, ChatGPTInteraction


class FactCheckSessionSerializer(serializers.ModelSerializer):
    """Serializer for FactCheckSession model"""
    
    class Meta:
        model = FactCheckSession
        fields = [
            'session_id', 'user_input', 'uploaded_image', 'mode', 'status', 
            'final_verdict', 'confidence_score', 'analysis_summary',
            'created_at', 'updated_at', 'completed_at'
        ]
        read_only_fields = [
            'session_id', 'status', 'final_verdict', 'confidence_score',
            'analysis_summary', 'created_at', 'updated_at', 'completed_at'
        ]


class AnalysisStepSerializer(serializers.ModelSerializer):
    """Serializer for AnalysisStep model"""
    
    class Meta:
        model = AnalysisStep
        fields = [
            'step_number', 'step_type', 'description', 'status',
            'result_data', 'error_message', 'started_at', 'completed_at'
        ]


class SourceSerializer(serializers.ModelSerializer):
    """Serializer for Source model"""
    
    class Meta:
        model = Source
        fields = [
            'id', 'url', 'title', 'publisher', 'author', 'credibility_score',
            'content_summary', 'extracted_claims', 'publish_date', 'accessed_at',
            'is_primary_source', 'supports_claim', 'relevance_score'
        ]


class SearchQuerySerializer(serializers.ModelSerializer):
    """Serializer for SearchQuery model"""
    
    class Meta:
        model = SearchQuery
        fields = [
            'query_text', 'search_type', 'results_count', 'successful',
            'error_message', 'timestamp'
        ]


class ChatGPTInteractionSerializer(serializers.ModelSerializer):
    """Serializer for ChatGPTInteraction model"""
    
    class Meta:
        model = ChatGPTInteraction
        fields = [
            'interaction_type', 'prompt', 'response', 'model_used',
            'tokens_used', 'cost', 'timestamp'
        ]
        read_only_fields = ['prompt', 'response']  # Sensitive data


class FactCheckSessionDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for FactCheckSession with related data"""
    
    analysis_steps = AnalysisStepSerializer(many=True, read_only=True)
    sources = SourceSerializer(many=True, read_only=True)
    search_queries = SearchQuerySerializer(many=True, read_only=True)
    gpt_interactions = ChatGPTInteractionSerializer(many=True, read_only=True)
    
    class Meta:
        model = FactCheckSession
        fields = [
            'session_id', 'user_input', 'uploaded_image', 'status',
            'final_verdict', 'confidence_score', 'analysis_summary',
            'created_at', 'updated_at', 'completed_at',
            'analysis_steps', 'sources', 'search_queries', 'gpt_interactions'
        ]


class FactCheckRequestSerializer(serializers.Serializer):
    """Serializer for fact-check request"""
    
    user_input = serializers.CharField(max_length=5000)
    uploaded_image = serializers.ImageField(required=False, allow_null=True)
    mode = serializers.ChoiceField(
        choices=[('fact_check', 'Fact Check'), ('research', 'Research')],
        default='fact_check',
        required=False
    )
    
    def validate_user_input(self, value):
        """Validate user input"""
        if len(value.strip()) < 2:
            raise serializers.ValidationError("Input must be at least 2 characters long")
        return value.strip()


class FactCheckStatusSerializer(serializers.Serializer):
    """Serializer for fact-check status response"""
    
    session_id = serializers.UUIDField()
    status = serializers.CharField()
    progress_percentage = serializers.FloatField()
    completed_steps = serializers.IntegerField()
    total_steps = serializers.IntegerField(help_text="Actual steps created so far")
    expected_steps = serializers.IntegerField(required=False, help_text="Total steps expected for the workflow")
    failed_steps = serializers.IntegerField()
    current_step = serializers.DictField(allow_null=True)
    steps = serializers.ListField()
    web_search_mode = serializers.BooleanField(required=False, help_text="Indicates if web search workflow is used")
    
    
class FactCheckResultSerializer(serializers.Serializer):
    """Serializer for fact-check results"""
    
    session_id = serializers.UUIDField()
    status = serializers.CharField()
    verdict = serializers.CharField(allow_null=True)
    confidence_score = serializers.FloatField(allow_null=True)
    summary = serializers.CharField(allow_null=True)
    reasoning = serializers.CharField(allow_null=True)
    key_evidence = serializers.ListField(allow_null=True)
    supporting_evidence = serializers.ListField(allow_null=True)
    contradictory_evidence = serializers.ListField(allow_null=True)
    sources = SourceSerializer(many=True, allow_null=True)
    limitations = serializers.ListField(allow_null=True)
    recommendations = serializers.ListField(allow_null=True)
    created_at = serializers.DateTimeField()
    completed_at = serializers.DateTimeField(allow_null=True)
