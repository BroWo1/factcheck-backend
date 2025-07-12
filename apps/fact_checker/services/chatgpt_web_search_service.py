import logging
import json
from typing import Dict, List, Optional, Any
from openai import OpenAI
from django.conf import settings
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.fact_checker.models import ChatGPTInteraction, FactCheckSession, AnalysisStep

logger = logging.getLogger(__name__)


class ChatGPTWebSearchService:
    """Service for interacting with OpenAI's ChatGPT API using web search tool with multi-step analysis"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4.1-mini"
        self.advModel = "o4-mini"
    
    def _extract_web_search_citations(self, response_content: List[Any]) -> List[Dict[str, Any]]:
        """
        Extract citations from web search response content
        """
        citations = []
        logger.debug(f"Extracting citations from response_content: {type(response_content)}")
        
        try:
            # The response_content is a list of content blocks.
            # We need to find the one of type 'text'.
            for i, content_block in enumerate(response_content):
                logger.debug(f"Processing content block {i}: {type(content_block)}")
                
                # Handle both dictionary and object access
                block_type = getattr(content_block, 'type', None) or \
                            (content_block.get('type') if hasattr(content_block, 'get') else None)
                
                logger.debug(f"Content block {i} type: {block_type}")

                if block_type in ['text', 'output_text']:
                    # Based on OpenAI documentation: annotations are in message.content[0].annotations
                    # For output_text type, annotations are directly on the content block
                    annotations = getattr(content_block, 'annotations', None) or \
                                (content_block.get('annotations') if hasattr(content_block, 'get') else [])
                    
                    logger.debug(f"Found {len(annotations) if annotations else 0} annotations for {block_type}")
                    
                    for j, annotation in enumerate(annotations):
                        logger.debug(f"Processing annotation {j}: {type(annotation)}")
                        
                        # Handle both dictionary and object access for annotations
                        ann_type = getattr(annotation, 'type', None) or \
                                (annotation.get('type') if hasattr(annotation, 'get') else None)
                        
                        logger.debug(f"Annotation {j} type: {ann_type}")

                        if ann_type == 'url_citation':
                            # For url_citation type, try different ways to access the citation data
                            url = None
                            title = None
                            
                            # Method 1: Try direct access to url attribute
                            url = getattr(annotation, 'url', None)
                            title = getattr(annotation, 'title', None)
                            
                            # Method 2: Try url_citation sub-object
                            if not url:
                                citation_details = getattr(annotation, 'url_citation', None) or \
                                                (annotation.get('url_citation') if hasattr(annotation, 'get') else {})
                                
                                if citation_details:
                                    url = getattr(citation_details, 'url', None) or \
                                        (citation_details.get('url') if hasattr(citation_details, 'get') else None)
                                    
                                    title = getattr(citation_details, 'title', None) or \
                                            (citation_details.get('title') if hasattr(citation_details, 'get') else None)
                            
                            # Method 3: Try dictionary-style access
                            if not url and hasattr(annotation, 'get'):
                                url = annotation.get('url')
                                title = annotation.get('title')
                            
                            # Method 4: Try to convert to dict and access
                            if not url:
                                try:
                                    if hasattr(annotation, 'dict'):
                                        ann_dict = annotation.dict()
                                        url = ann_dict.get('url')
                                        title = ann_dict.get('title')
                                        logger.debug(f"Annotation dict: {ann_dict}")
                                except:
                                    pass

                            citation = {
                                "url": url,
                                "title": title,
                                "start_index": getattr(annotation, 'start_index', None),
                                "end_index": getattr(annotation, 'end_index', None)
                            }
                            
                            logger.debug(f"Extracted citation: {citation}")
                            
                            # Only add citation if it has a URL
                            if citation["url"]:
                                citations.append(citation)
                                logger.info(f"Added citation: {url}")
                            else:
                                logger.warning(f"Citation missing URL: {citation}")
                                # Log annotation details for debugging
                                logger.debug(f"Annotation attributes: {dir(annotation)}")
                                if hasattr(annotation, 'dict'):
                                    try:
                                        logger.debug(f"Annotation as dict: {annotation.dict()}")
                                    except:
                                        pass
        except Exception as e:
            logger.error(f"Error extracting citations: {str(e)}")
            logger.debug(f"Response content structure: {response_content}")
            
        logger.info(f"Extracted {len(citations)} total citations")
        return citations
    
    def _clean_json_response(self, response_text: str) -> str:
        """
        Clean JSON response by removing markdown code blocks and other formatting
        """
        if not response_text or not response_text.strip():
            return ""
            
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
        
        # Try to extract JSON from text that might have additional content
        response_text = response_text.strip()
        
        # Look for JSON object boundaries
        start_idx = response_text.find('{')
        if start_idx != -1:
            # Find the last closing brace
            brace_count = 0
            end_idx = -1
            for i in range(start_idx, len(response_text)):
                if response_text[i] == '{':
                    brace_count += 1
                elif response_text[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i
                        break
            
            if end_idx != -1:
                response_text = response_text[start_idx:end_idx + 1]
        
        return response_text.strip()
    
    async def _summarize_step_result(self, step_number: int, result_data: Dict[str, Any]) -> str:
        """
        Calls the AI to generate a user-friendly summary of a step's result.
        """
        try:
            # Create a simplified version of the result for the prompt
            summary_prompt_data = {k: v for k, v in result_data.items() if k not in ['citations', 'step', 'parsing_error']}

            prompt = f"""
            Based on the following JSON data from step {step_number} of a fact-checking process, please provide a concise, one-sentence summary for a non-technical user.

            Data:
            {json.dumps(summary_prompt_data, indent=2)}

            Example Summaries:
            - Step 1: "Identified the main topic and found initial credible sources to investigate the claim."
            - Step 2: "Gathered specific evidence and noted some conflicting reports that require further analysis."
            - Step 3: "Evaluated the reliability of the sources, finding most to be credible but with some potential for bias."
            - Step 4: "Finalized the analysis, reaching a verdict with a moderate level of confidence."

            Your summary:
            """

            # Using the simpler chat completions API for this non-critical task
            response = self.client.chat.completions.create(
                model="gpt-4.1-mini", # Cheaper and faster model is fine for this
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=100,
            )
            
            summary = response.choices[0].message.content.strip()
            logger.info(f"Generated summary for step {step_number}: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error generating summary for step {step_number}: {str(e)}")
            return f"Step {step_number} has been completed."
    
    def _create_fallback_response(self, step_number: int, raw_response: str, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a fallback response structure when JSON parsing fails
        """
        if step_number == 1:
            return {
                "main_topic": "Analysis completed but unable to parse structured response",
                "summary": summary_text,
                "claim_type": "other",
                "initial_credible_sources": [],
                "general_summary": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "search_strategy": "Web search conducted",
                "preliminary_assessment": "Unable to provide structured assessment",
                "areas_needing_deeper_research": [],
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        elif step_number == 2:
            return {
                "specific_evidence": [],
                "summary": summary_text,
                "counter_arguments": [],
                "expert_perspectives": [],
                "recent_developments": [],
                "contextual_factors": [],
                "contradictory_information": [],
                "areas_of_uncertainty": [],
                "raw_findings": raw_response[:1000] + "..." if len(raw_response) > 1000 else raw_response,
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        elif step_number == 3:
            return {
                "source_credibility_analysis": [],
                "summary": summary_text,
                "overall_source_quality": {
                    "primary_sources_count": 0,
                    "secondary_sources_count": 0,
                    "high_credibility_sources": 0,
                    "questionable_sources": 0,
                    "source_diversity": "Unable to assess"
                },
                "cross_reference_analysis": {
                    "consistent_information": [],
                    "conflicting_information": [],
                    "unique_claims": [],
                    "verification_status": "unable_to_verify"
                },
                "red_flags": [],
                "source_recommendations": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        elif step_number == 4:
            return {
                "verdict": {
                    "classification": "uncertain",
                    "confidence_score": 0.0,
                    "summary": "Analysis completed but unable to provide structured verdict due to response format issues"
                },
                "summary": summary_text,
                "detailed_analysis": {
                    "reasoning": raw_response[:1000] + "..." if len(raw_response) > 1000 else raw_response,
                    "key_evidence": [],
                    "supporting_evidence": [],
                    "contradictory_evidence": [],
                    "source_quality_assessment": "Unable to assess due to parsing error",
                    "limitations": ["Response format parsing failed"],
                    "areas_of_uncertainty": ["Complete analysis due to technical issues"]
                },
                "methodology_summary": {
                    "search_approach": "Multi-step web search analysis",
                    "sources_consulted": "Web search results",
                    "verification_methods": "Cross-reference analysis",
                    "analysis_date": "Current date"
                },
                "recommendations": ["Manual review recommended due to parsing issues"],
                "follow_up_suggestions": ["Re-run analysis or review raw findings"],
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        else:
            return {
                "error": "Unknown step number",
                "raw_response": raw_response,
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }

    async def _make_web_search_request(self, prompt: str, image_data: Optional[bytes] = None) -> tuple[str, List[Dict[str, Any]]]:
        """
        Helper method to make web search requests and extract response + citations
        """
        tools = [{"type": "web_search_preview", "search_context_size": "medium"}]
        
        # Prepare input according to OpenAI responses API documentation
        if image_data:
            import base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # For responses API with images, use the correct format from the documentation
            input_data = [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt},
                        {
                            "type": "input_image",
                            "image_url": f"data:image/jpeg;base64,{base64_image}",
                        },
                    ],
                }
            ]
            
            response = self.client.responses.create(
                model=self.advModel,
                tools=tools,
                input=input_data
            )
        else:
            # For text-only requests, use the simpler format
            input_data = [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": prompt}
                    ],
                }
            ]
            
            response = self.client.responses.create(
                model=self.advModel,
                tools=tools,
                input=input_data
            )
        
        # Extract response text and citations
        response_text = ""
        citations = []

        try:
            if hasattr(response, 'output') and response.output:
                for output_item in response.output:
                    if getattr(output_item, 'type', None) == "message" or hasattr(output_item, 'content'):
                        if hasattr(output_item, 'content'):
                            citations.extend(self._extract_web_search_citations(output_item.content))
                        
                        for content_block in output_item.content:
                            block_type = getattr(content_block, 'type', None)
                            if block_type in ['text', 'output_text']:
                                if block_type == 'text':
                                    # For text type, content is nested in a text object
                                    text_obj = getattr(content_block, 'text', {})
                                    response_text = getattr(text_obj, 'value', '') or text_obj.get('value', '')
                                elif block_type == 'output_text':
                                    # For output_text type, the text is directly on the object as per OpenAI docs
                                    response_text = getattr(content_block, 'text', '') or content_block.get('text', '')
                                break
                        if response_text:
                            break
        except Exception as e:
            logger.warning(f"Failed to parse structured response output: {str(e)}")

        # Fallback to output_text if no response_text was extracted
        if not response_text and hasattr(response, 'output_text'):
            response_text = response.output_text
            logger.debug("Using fallback output_text for response")

        return response_text, citations

    async def _step1_initial_search(self, session: FactCheckSession, user_input: str, image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Step 1: Initial search for credible sources and general summary
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=1,
                step_type='initial_web_search',
                description='Initial search for credible sources and general summary',
                status='in_progress'
            )
            
            prompt = f"""
            You are an expert fact-checker performing an initial search for credible sources. Analyze the following claim and search for the most authoritative and credible sources available. Use the user's input language (English or Chinese) for your response.

            Claim: {user_input}

            Focus on finding:
            1. Primary sources (official statements, press releases, government documents)
            2. Credible news organizations with strong fact-checking reputations
            3. Academic or scientific sources if relevant
            4. Expert commentary from recognized authorities

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "main_topic": "The primary topic or subject matter",
                "claim_type": "news_event|historical_fact|scientific_claim|statistical_claim|political_statement|other",
                "initial_credible_sources": [
                    {{
                        "source_name": "Name of the source",
                        "source_type": "news|academic|government|expert|other",
                        "credibility_level": "high|medium|low",
                        "key_information": "Main information from this source"
                    }}
                ],
                "general_summary": "Brief general summary of what current credible sources say about this topic",
                "search_strategy": "What search approach was most effective for finding information",
                "preliminary_assessment": "Initial assessment based on credible sources found",
                "areas_needing_deeper_research": ["List of specific aspects that need more detailed investigation"]
            }}

            Always use web search to find the most credible and authoritative sources available, DO NOT overly rely on your internal knowledge. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt, image_data)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 1
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='step1_initial_search',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.advModel,
                tokens_used=None  # Would need to extract from response if available
            )
            
            # Parse response
            try:
                cleaned_response = self._clean_json_response(response_text)
                if not cleaned_response:
                    raise json.JSONDecodeError("Cleaned response is empty.", "", 0)
                
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["step"] = 1

                # --- NEW: Generate and save summary ---
                summary = await self._summarize_step_result(1, result)
                result["summary"] = summary
                step.summary = summary
                # --- END NEW ---
                
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 1 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Step 1 JSON response: {str(e)}")
                
                fallback_result = self._create_fallback_response(1, response_text, citations)
                
                # --- NEW: Add summary to fallback ---
                step.summary = fallback_result.get("summary", "Step 1 completed with a parsing error.")
                # --- END NEW ---

                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 1 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Step 1 initial search: {str(e)}")
            
            # Mark step as failed
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 1}

    async def _step2_deeper_exploration(self, session: FactCheckSession, user_input: str, step1_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 2: Deeper exploration and refined searches for specific content
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=2,
                step_type='deeper_exploration',
                description='Deeper exploration and refined searches for specific content',
                status='in_progress'
            )
            
            prompt = f"""
            You are an expert fact-checker conducting deeper research. Based on the initial findings, conduct more specific and targeted searches to gather detailed information.

            Original Claim: {user_input}

            Initial Research Findings:
            {json.dumps(step1_result, indent=2)}

            Now conduct deeper, more specific searches focusing on:
            1. Detailed evidence for specific claims
            2. Counter-arguments or alternative perspectives
            3. Expert analysis and commentary
            4. Recent updates or developments
            5. Contextual information that affects the claim's validity

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "specific_evidence": [
                    {{
                        "evidence_type": "statistical|testimonial|documentary|expert_opinion|other",
                        "evidence_description": "Description of the evidence found",
                        "source_quality": "high|medium|low",
                        "supports_claim": "strongly_supports|somewhat_supports|neutral|somewhat_contradicts|strongly_contradicts"
                    }}
                ],
                "counter_arguments": [
                    {{
                        "argument": "Description of counter-argument or alternative perspective",
                        "source": "Source of this counter-argument",
                        "credibility": "high|medium|low"
                    }}
                ],
                "expert_perspectives": [
                    {{
                        "expert_name": "Name or description of expert",
                        "expertise_area": "Their area of expertise",
                        "opinion_summary": "Summary of their perspective",
                        "stance": "supports|opposes|neutral|nuanced"
                    }}
                ],
                "recent_developments": ["Any recent news, updates, or developments related to this claim"],
                "contextual_factors": ["Important contextual information that affects interpretation"],
                "contradictory_information": ["Information that contradicts the original claim"],
                "areas_of_uncertainty": ["Aspects where evidence is unclear or conflicting"]
            }}

            Use targeted web searches to gather comprehensive evidence from multiple perspectives. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 2
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='step2_deeper_exploration',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.advModel,
                tokens_used=None
            )
            
            # Parse response
            try:
                cleaned_response = self._clean_json_response(response_text)
                if not cleaned_response:
                    raise json.JSONDecodeError("Cleaned response is empty.", "", 0)
                
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["step"] = 2
                summary = await self._summarize_step_result(2, result)
                result["summary"] = summary
                step.summary = summary
                
                # Mark step as completed
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 2 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Step 2 JSON response: {str(e)}")
                logger.debug(f"Raw response: {response_text[:500]}...")
                
                # Create fallback response
                fallback_result = self._create_fallback_response(2, response_text, citations)
                step.summary = fallback_result.get("summary", "Step 2 completed with a parsing error.")

                # Mark step as completed with fallback result
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 2 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Step 2 deeper exploration: {str(e)}")
            
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 2}

    async def _step3_source_evaluation(self, session: FactCheckSession, step1_result: Dict[str, Any], step2_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 3: Evaluate cited sources and their credibility
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=3,
                step_type='source_credibility_evaluation',
                description='Evaluate cited sources and their credibility',
                status='in_progress'
            )
            
            # Combine citations from previous steps
            all_citations = []
            all_citations.extend(step1_result.get("citations", []))
            all_citations.extend(step2_result.get("citations", []))
            
            prompt = f"""
            You are an expert fact-checker evaluating source credibility and reliability. Analyze all the sources found in the previous research steps and provide a comprehensive credibility assessment.

            Sources to evaluate from previous research:
            {json.dumps(all_citations, indent=2)}

            Previous research findings:
            Step 1 - Initial Search: {json.dumps(step1_result, indent=2)}
            Step 2 - Deeper Exploration: {json.dumps(step2_result, indent=2)}

            Conduct additional web searches to verify publisher credibility, check for bias, and cross-reference information.

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "source_credibility_analysis": [
                    {{
                        "url": "Source URL",
                        "publisher": "Publisher name",
                        "credibility_score": 0.8,
                        "credibility_factors": [
                            "List of factors affecting credibility (e.g., editorial standards, fact-checking history, transparency)"
                        ],
                        "bias_assessment": {{
                            "political_lean": "left|center|right|unknown",
                            "bias_level": "minimal|low|moderate|high",
                            "factual_reporting": "very_high|high|mostly_factual|mixed|low"
                        }},
                        "publisher_reputation": "excellent|good|fair|poor|unknown",
                        "fact_check_history": "Description of publisher's fact-checking track record",
                        "funding_transparency": "transparent|somewhat_transparent|opaque|unknown"
                    }}
                ],
                "overall_source_quality": {{
                    "primary_sources_count": 2,
                    "secondary_sources_count": 3,
                    "high_credibility_sources": 4,
                    "questionable_sources": 1,
                    "source_diversity": "Assessment of source diversity and independence"
                }},
                "cross_reference_analysis": {{
                    "consistent_information": ["Information that is consistently reported across sources"],
                    "conflicting_information": ["Information that conflicts between sources"],
                    "unique_claims": ["Claims found in only one or few sources"],
                    "verification_status": "well_verified|partially_verified|poorly_verified|conflicting"
                }},
                "red_flags": ["Any credibility red flags or concerns identified"],
                "source_recommendations": "Recommendations about which sources are most trustworthy"
            }}

            Use web search to verify publisher reputations and credibility ratings from media bias and fact-checking organizations. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 3
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='step3_source_evaluation',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.advModel,
                tokens_used=None
            )
            
            # Parse response
            try:
                cleaned_response = self._clean_json_response(response_text)
                if not cleaned_response:
                    raise json.JSONDecodeError("Cleaned response is empty.", "", 0)
                
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["step"] = 3
                summary = await self._summarize_step_result(3, result)
                result["summary"] = summary
                step.summary = summary
                
                # Mark step as completed
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 3 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Step 3 JSON response: {str(e)}")
                logger.debug(f"Raw response: {response_text[:500]}...")
                
                # Create fallback response
                fallback_result = self._create_fallback_response(3, response_text, citations)
                
                step.summary = fallback_result.get("summary", "Step 3 completed with a parsing error.")

                # Mark step as completed with fallback result
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 3 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Step 3 source evaluation: {str(e)}")
            
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 3}

    async def _step4_final_conclusion(self, session: FactCheckSession, user_input: str, step1_result: Dict[str, Any], step2_result: Dict[str, Any], step3_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 4: Summarize all findings and provide final conclusion
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=4,
                step_type='final_conclusion',
                description='Summarize findings and provide final conclusion',
                status='in_progress'
            )
            
            prompt = f"""
            You are an expert fact-checker providing a final conclusion. Synthesize all previous research to provide a comprehensive final verdict.

            Original Claim: {user_input}

            Research Summary:
            Step 1 - Initial Search Results: {json.dumps(step1_result, indent=2)}
            Step 2 - Deeper Exploration: {json.dumps(step2_result, indent=2)}
            Step 3 - Source Evaluation: {json.dumps(step3_result, indent=2)}

            Based on all research conducted, provide a final comprehensive assessment. Use web search for any final verification or to check for very recent developments.

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "verdict": {{
                    "classification": "true|likely_true|uncertain|likely_false|false",
                    "confidence_score": 0.85,
                    "summary": "Brief summary suitable for display to users"
                }},
                "detailed_analysis": {{
                    "reasoning": "Detailed explanation of the verdict based on all research findings",
                    "key_evidence": ["Most important evidence points supporting the verdict"],
                    "supporting_evidence": ["Evidence that supports the claim"],
                    "contradictory_evidence": ["Evidence that contradicts the claim"],
                    "source_quality_assessment": "Overall assessment of source quality and reliability",
                    "limitations": ["Limitations of this fact-check analysis"],
                    "areas_of_uncertainty": ["Aspects where definitive conclusions cannot be made"]
                }},
                "methodology_summary": {{
                    "search_approach": "Summary of search methodology used",
                    "sources_consulted": "Types and quality of sources consulted",
                    "verification_methods": "Methods used to verify information",
                    "analysis_date": "When this analysis was conducted"
                }},
                "recommendations": [
                    "Recommendations for readers about interpreting this information"
                ],
                "follow_up_suggestions": [
                    "Suggestions for further research or monitoring of developments"
                ]
            }}

            Provide a balanced, evidence-based conclusion that acknowledges uncertainties while being as definitive as the evidence allows. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 4
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='step4_final_conclusion',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.advModel,
                tokens_used=None
            )
            
            # Parse response
            try:
                cleaned_response = self._clean_json_response(response_text)
                if not cleaned_response:
                    raise json.JSONDecodeError("Cleaned response is empty.", "", 0)
                
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["step"] = 4
                summary = await self._summarize_step_result(4, result)
                result["summary"] = summary
                step.summary = summary
                
                # Mark step as completed
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 4 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Step 4 JSON response: {str(e)}")
                logger.debug(f"Raw response: {response_text[:500]}...")
                
                # Create fallback response  
                fallback_result = self._create_fallback_response(4, response_text, citations)
                step.summary = fallback_result.get("summary", "Step 4 completed with a parsing error.")

                
                # Mark step as completed with fallback result
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Step 4 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Step 4 final conclusion: {str(e)}")
            
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 4}

    async def analyze_claim_with_web_search(self, session: FactCheckSession, user_input: str, image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Perform comprehensive fact-checking using web search in multiple steps
        This orchestrates the 4-step analysis process
        """
        try:
            logger.info(f"Starting multi-step web search analysis for session {session.session_id}")
            
            # Step 1: Initial search for credible sources
            step1_result = await self._step1_initial_search(session, user_input, image_data)
            if step1_result.get('error') and not step1_result.get('parsing_error'):
                logger.error(f"Step 1 failed: {step1_result.get('error')}")
                return step1_result
            
            # Step 2: Deeper exploration (continue even if Step 1 had parsing issues)
            step2_result = await self._step2_deeper_exploration(session, user_input, step1_result)
            if step2_result.get('error') and not step2_result.get('parsing_error'):
                logger.error(f"Step 2 failed: {step2_result.get('error')}")
                # Continue with partial results
                
            # Step 3: Source evaluation (continue even if previous steps had parsing issues)
            step3_result = await self._step3_source_evaluation(session, step1_result, step2_result)
            if step3_result.get('error') and not step3_result.get('parsing_error'):
                logger.error(f"Step 3 failed: {step3_result.get('error')}")
                # Continue with partial results
                
            # Step 4: Final conclusion (continue even if previous steps had parsing issues)
            step4_result = await self._step4_final_conclusion(session, user_input, step1_result, step2_result, step3_result)
            if step4_result.get('error') and not step4_result.get('parsing_error'):
                logger.error(f"Step 4 failed: {step4_result.get('error')}")
                return step4_result
            
            # Combine all citations
            all_citations = []
            for step_result in [step1_result, step2_result, step3_result, step4_result]:
                if isinstance(step_result, dict) and "citations" in step_result:
                    all_citations.extend(step_result["citations"])
            
            # Check if we had any parsing errors
            parsing_errors = [
                step_result.get('parsing_error', False) 
                for step_result in [step1_result, step2_result, step3_result, step4_result]
            ]
            had_parsing_errors = any(parsing_errors)
            
            # Extract verdict from Step 4 (even if it had parsing errors)
            verdict_info = step4_result.get("verdict", {
                "classification": "uncertain",
                "confidence_score": 0.0,
                "summary": "Multi-step analysis completed with some formatting issues."
            })
            
            # Return combined results in the format expected by enhanced_analysis_service
            final_result = {
                "web_search_used": True,
                "multi_step_analysis": True,
                "had_parsing_errors": had_parsing_errors,
                "step1_initial_search": step1_result,
                "step2_deeper_exploration": step2_result,
                "step3_source_evaluation": step3_result,
                "step4_final_conclusion": step4_result,
                "citations": all_citations,
                "verdict": verdict_info
            }
            
            logger.info(f"Multi-step web search analysis completed for session {session.session_id} with {len(all_citations)} total citations")
            if had_parsing_errors:
                logger.warning(f"Analysis completed but had parsing errors in {sum(parsing_errors)} step(s)")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in multi-step web search analysis: {str(e)}")
            return {"error": str(e)}

    # Keep existing methods for backwards compatibility
    async def analyze_initial_claim_with_search(self, session: FactCheckSession, user_input: str, image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Perform initial analysis with web search support
        Compatible with existing workflow but enhanced with web search
        """
        try:
            prompt = f"""
            You are an expert fact-checker with access to current web information. Analyze the following claim and provide a structured analysis using web search to enhance your assessment.
            
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
                "initial_assessment": "Brief initial assessment of the claim's plausibility based on web search",
                "web_search_insights": {{
                    "recent_coverage": ["Recent news coverage found"],
                    "authoritative_sources": ["Authoritative sources that have addressed this topic"],
                    "initial_credibility": "Assessment based on immediate web search results"
                }}
            }}
            
            Use web search to enhance your initial analysis with current information.
            """
            
            response_text, citations = await self._make_web_search_request(prompt, image_data)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='initial_analysis_web_search',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.model,
                tokens_used=None
            )
            
            # Parse JSON response
            try:
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["web_search_used"] = True
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return {
                    "error": "Failed to parse response", 
                    "raw_response": response_text,
                    "citations": citations,
                    "web_search_used": True
                }
                
        except Exception as e:
            logger.error(f"Error in initial claim analysis with web search: {str(e)}")
            return {"error": str(e)}
    
    async def evaluate_sources_with_search(self, session: FactCheckSession, sources_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluate sources with additional web search for context
        """
        try:
            sources_summary = []
            for source in sources_data:
                sources_summary.append({
                    "url": source.get("url", ""),
                    "title": source.get("title", ""),
                    "publisher": source.get("publisher", ""),
                    "summary": source.get("content_summary", "")[:500]
                })
            
            prompt = f"""
            You are an expert fact-checker evaluating sources for credibility and relevance. Use web search to gather additional context about publishers and cross-reference information.
            
            Original claim: {session.user_input}
            
            Sources to evaluate:
            {json.dumps(sources_summary, indent=2)}
            
            Use web search to verify publisher credibility, look for additional coverage, and cross-reference information. Provide a JSON response with:
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
                        "fact_check_notes": "Notes about this source's reliability",
                        "cross_references": ["Additional sources found that corroborate or contradict"]
                    }}
                ],
                "overall_assessment": "Summary of source quality and consensus",
                "additional_findings": "What web search revealed about this topic",
                "consensus_level": "How much agreement exists among reliable sources"
            }}
            
            Use web search extensively to verify publisher reputations and find additional corroborating sources.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='source_evaluation_web_search',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.model,
                tokens_used=None
            )
            
            try:
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["web_search_used"] = True
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return {
                    "error": "Failed to parse response", 
                    "raw_response": response_text,
                    "citations": citations,
                    "web_search_used": True
                }
                
        except Exception as e:
            logger.error(f"Error in source evaluation with web search: {str(e)}")
            return {"error": str(e)}
    
    async def generate_final_verdict_with_search(self, session: FactCheckSession, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate final verdict with additional web search for latest information
        """
        try:
            prompt = f"""
            You are an expert fact-checker providing a final verdict on a claim. Use web search to gather the most current information and ensure your verdict is based on the latest available evidence.
            
            Original claim: {session.user_input}
            
            Previous evidence and analysis:
            {json.dumps(analysis_data, indent=2)}
            
            Use web search to find any recent developments, updates, or additional authoritative sources. Provide a comprehensive final verdict in JSON format:
            {{
                "verdict": "true|likely_true|uncertain|likely_false|false",
                "confidence_score": 0.0-1.0,
                "reasoning": "Detailed explanation of the verdict incorporating latest web search findings",
                "key_evidence": ["List of most important evidence points including web search findings"],
                "contradictory_evidence": ["Evidence that contradicts the claim"],
                "supporting_evidence": ["Evidence that supports the claim"],
                "source_quality_summary": "Assessment of overall source quality including web search sources",
                "recent_developments": ["Any recent developments found through web search"],
                "expert_consensus": "What expert sources and authoritative publications say",
                "limitations": ["Limitations of this fact-check"],
                "recommendations": ["Recommendations for further verification if needed"],
                "summary": "Brief summary suitable for display to users",
                "last_updated": "Information about when this assessment was made and what current sources say"
            }}
            
            Use web search extensively to ensure your verdict reflects the most current and comprehensive information available.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='final_verdict_web_search',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.model,
                tokens_used=None
            )
            
            try:
                cleaned_response = self._clean_json_response(response_text)
                result = json.loads(cleaned_response)
                result["citations"] = citations
                result["web_search_used"] = True
                return result
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON response: {response_text}")
                return {
                    "error": "Failed to parse response", 
                    "raw_response": response_text,
                    "citations": citations,
                    "web_search_used": True
                }
                
        except Exception as e:
            logger.error(f"Error in final verdict generation with web search: {str(e)}")
            return {"error": str(e)}
    
    def extract_search_queries(self, initial_analysis: Dict[str, Any]) -> List[str]:
        """
        Extract optimized search queries from initial analysis
        Note: This method is less relevant when using web search tool, 
        but kept for compatibility with existing workflow
        """
        queries = []
        
        # Add suggested keywords from initial analysis
        if "search_keywords" in initial_analysis:
            queries.extend(initial_analysis["search_keywords"])
        
        # Add topic-based queries
        if "main_topic" in initial_analysis:
            queries.append(initial_analysis["main_topic"])
        
        # Add factual claims as queries
        if "factual_claims" in initial_analysis:
            queries.extend(initial_analysis["factual_claims"])
        
        # Add web search insights if available
        if "web_search_insights" in initial_analysis:
            insights = initial_analysis["web_search_insights"]
            if "recent_coverage" in insights:
                queries.extend(insights["recent_coverage"])
        
        return queries[:5]  # Limit to 5 queries