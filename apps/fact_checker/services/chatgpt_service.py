import logging
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
from django.conf import settings
from asgiref.sync import sync_to_async
from apps.fact_checker.models import ChatGPTInteraction, FactCheckSession

logger = logging.getLogger(__name__)


class ChatGPTService:
    """Service for interacting with OpenAI's ChatGPT API"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4.1-mini"
    
    def _clean_json_response(self, response_text: str) -> str:
        """
        Clean JSON response by removing markdown code blocks if present
        """
        # Remove markdown code blocks if present
        if response_text.strip().startswith('```'):
            # Find the start of JSON content
            lines = response_text.strip().split('\n')
            # Skip the opening ```json line
            if lines[0].startswith('```'):
                lines = lines[1:]
            # Remove the closing ``` line
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            response_text = '\n'.join(lines)
        
        return response_text.strip()
        
    async def analyze_initial_claim(self, session: FactCheckSession, user_input: str, image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Perform initial analysis of the user's claim
        Identifies key topics, potential publishers, and factual claims
        """
        try:
            prompt = f"""
            You are an expert fact-checker. Analyze the following claim and provide a structured analysis.
            
            Claim: {user_input}
            
            Please provide a JSON response with the following structure:
            {{
                "main_topic": "The primary topic or subject matter",
                "factual_claims": ["List of specific factual claims that can be verified"],
                "potential_publishers": ["List of credible news sources likely to have covered this topic"],
                "search_keywords": ["List of effective search terms for finding relevant information"],
                "claim_type": "news_event|historical_fact|scientific_claim|statistical_claim|other",
                "urgency_level": "high|medium|low",
                "complexity_score": 1-10,
                "initial_assessment": "Brief initial assessment of the claim's plausibility"
            }}
            
            Focus on being thorough but concise. Identify the most important aspects to verify.
            """
            
            messages = [{"role": "user", "content": prompt}]
            
            # Add image if provided
            if image_data:
                import base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                messages[0]["content"] = [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
                self.model = "gpt-4.1-mini"
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=1000
            )
            
            response_text = response.choices[0].message.content
            
            # Log the interaction
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='initial_analysis',
                prompt=prompt,
                response=response_text,
                model_used=self.model,
                tokens_used=response.usage.total_tokens if response.usage else None
            )
            
            # Parse JSON response
            try:
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return {"error": "Failed to parse response", "raw_response": response_text}
                
        except Exception as e:
            logger.error(f"Error in initial claim analysis: {str(e)}")
            return {"error": str(e)}
    
    async def evaluate_sources(self, session: FactCheckSession, sources_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate the credibility and relevance of found sources
        """
        try:
            sources_summary = []
            for source in sources_data:
                sources_summary.append({
                    "url": source.get("url", ""),
                    "title": source.get("title", ""),
                    "publisher": source.get("publisher", ""),
                    "summary": source.get("content_summary", "")[:500]  # Limit summary length
                })
            
            prompt = f"""
            You are an expert fact-checker evaluating sources for credibility and relevance.
            
            Original claim: {session.user_input}
            
            Sources to evaluate:
            {json.dumps(sources_summary, indent=2)}
            
            For each source, provide a JSON response with:
            {{
                "source_evaluations": [
                    {{
                        "url": "source_url",
                        "credibility_score": 0.0-1.0,
                        "relevance_score": 0.0-1.0,
                        "supports_claim": true|false|null,
                        "key_points": ["Important points from this source"],
                        "publisher_reliability": "high|medium|low|unknown",
                        "bias_assessment": "left|center|right|unknown",
                        "fact_check_notes": "Notes about this source's reliability"
                    }}
                ],
                "overall_assessment": "Summary of source quality and consensus"
            }}
            
            Be thorough in evaluating publisher credibility, content quality, and relevance to the original claim.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content
            
            # Log the interaction
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='source_evaluation',
                prompt=prompt,
                response=response_text,
                model_used=self.model,
                tokens_used=response.usage.total_tokens if response.usage else None
            )
            
            try:
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return {"error": "Failed to parse response", "raw_response": response_text}
                
        except Exception as e:
            logger.error(f"Error in source evaluation: {str(e)}")
            return {"error": str(e)}
    
    async def generate_final_verdict(self, session: FactCheckSession, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate final fact-check verdict based on all gathered evidence
        """
        try:
            prompt = f"""
            You are an expert fact-checker providing a final verdict on a claim.
            
            Original claim: {session.user_input}
            
            Evidence and analysis:
            {json.dumps(analysis_data, indent=2)}
            
            Provide a comprehensive final verdict in JSON format:
            {{
                "verdict": "true|likely|uncertain|suspicious|false",
                "confidence_score": 0.0-1.0,
                "reasoning": "Detailed explanation of the verdict",
                "key_evidence": ["List of most important evidence points"],
                "contradictory_evidence": ["Evidence that contradicts the claim"],
                "supporting_evidence": ["Evidence that supports the claim"],
                "source_quality_summary": "Assessment of overall source quality",
                "limitations": ["Limitations of this fact-check"],
                "recommendations": ["Recommendations for further verification if needed"],
                "summary": "Brief summary suitable for display to users"
            }}
            
            Be thorough, balanced, and transparent about limitations and uncertainties.
            """
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=2000
            )
            
            response_text = response.choices[0].message.content
            
            # Log the interaction
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='final_verdict',
                prompt=prompt,
                response=response_text,
                model_used=self.model,
                tokens_used=response.usage.total_tokens if response.usage else None
            )
            
            try:
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return {"error": "Failed to parse response", "raw_response": response_text}
                
        except Exception as e:
            logger.error(f"Error in final verdict generation: {str(e)}")
            return {"error": str(e)}
    
    
