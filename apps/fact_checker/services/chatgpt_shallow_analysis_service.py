import logging
import json
import base64
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


class ChatGPTResearchService:
    """Service for conducting general research using OpenAI's ChatGPT API with web search capabilities"""
    
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
        Calls the AI to generate a user-friendly summary of a step's result for research.
        """
        try:
            # Create a simplified version of the result for the prompt
            summary_prompt_data = {k: v for k, v in result_data.items() if k not in ['citations', 'step', 'parsing_error']}

            prompt = f"""
            Based on the following JSON data from step {step_number} of a research process, please provide a concise, one-sentence summary for a non-technical user.

            Data:
            {json.dumps(summary_prompt_data, indent=2)}

            Example Summaries:
            - Step 1: "Analyzed and clarified the research question, identifying key areas to investigate."
            - Step 2: "Conducted comprehensive background research and gathered general information about the topic."
            - Step 3: "Performed detailed investigation into specific aspects and gathered expert insights."

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
            logger.info(f"Generated summary for research step {step_number}: {summary}")
            return summary
        except Exception as e:
            logger.error(f"Error generating summary for research step {step_number}: {str(e)}")
            return f"Research step {step_number} has been completed."

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
                "recommendations": ["Areas where additional research would be valuable"],
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
    
    # Research Service Methods for ChatGPTResearchService
    def _create_research_fallback_response(self, step_number: int, raw_response: str, citations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a fallback response structure for research steps when JSON parsing fails
        """
        summary_text = f"Research step {step_number} has been completed with a parsing error."
        
        if step_number == 1:
            return {
                "research_question": "Unable to parse structured response",
                "summary": summary_text,
                "question_type": "general",
                "research_scope": "broad",
                "key_concepts": [],
                "search_strategy": "Web search conducted",
                "initial_understanding": raw_response[:500] + "..." if len(raw_response) > 500 else raw_response,
                "research_areas": [],
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        elif step_number == 2:
            return {
                "general_findings": [],
                "summary": summary_text,
                "key_information": [],
                "topic_overview": raw_response[:1000] + "..." if len(raw_response) > 1000 else raw_response,
                "related_topics": [],
                "preliminary_insights": [],
                "areas_for_deeper_research": [],
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        elif step_number == 3:
            return {
                "detailed_findings": [],
                "summary": summary_text,
                "specific_insights": [],
                "expert_opinions": [],
                "case_studies": [],
                "data_points": [],
                "conflicting_viewpoints": [],
                "research_gaps": [],
                "raw_findings": raw_response[:1000] + "..." if len(raw_response) > 1000 else raw_response,
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }
        else:
            return {
                "error": "Unknown research step number",
                "raw_response": raw_response,
                "citations": citations,
                "step": step_number,
                "parsing_error": True
            }

    async def _research_step1_understand_request(self, session: FactCheckSession, user_input: str, image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Step 1: Understand and clarify the research request
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=1,
                step_type='research_understanding',
                description='Understanding and clarifying the research request',
                status='in_progress'
            )
            
            prompt = f"""
            You are an expert researcher analyzing a research request. Your goal is to understand what the user wants to learn and clarify the research question to guide comprehensive investigation.

            User Request: {user_input}

            Analyze this request and identify:
            1. The core research question or topic
            2. Key concepts and areas to explore
            3. The scope and approach needed
            4. What the user is ultimately trying to understand

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "research_question": "Clear, focused research question derived from the user's request",
                "question_type": "academic|business|technical|general|exploratory|comparative|analytical",
                "research_scope": "narrow|focused|broad|comprehensive",
                "key_concepts": ["List of key concepts, terms, or topics central to this research"],
                "search_strategy": "Recommended approach for conducting this research",
                "initial_understanding": "Your understanding of what the user is looking for",
                "research_areas": [
                    {{
                        "area": "Specific research area or subtopic",
                        "importance": "high|medium|low",
                        "description": "Why this area is important for the research"
                    }}
                ],
                "methodology_suggestions": ["Suggested research methods or approaches"],
                "expected_outcomes": ["What types of insights or information this research should provide"]
            }}

            Focus on understanding the research intent to enable comprehensive investigation. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt, image_data)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 1,
                "interaction_type": "research_understanding"
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='research_step1_understanding',
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
                result["step"] = 1

                # Generate and save summary
                summary = await self._summarize_step_result(1, result)
                result["summary"] = summary
                step.summary = summary
                
                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = result
                await sync_to_async(step.save)()
                
                logger.info(f"Research Step 1 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Research Step 1 JSON response: {str(e)}")
                
                fallback_result = self._create_research_fallback_response(1, response_text, citations)
                step.summary = fallback_result.get("summary", "Research Step 1 completed with a parsing error.")

                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Research Step 1 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Research Step 1: {str(e)}")
            
            # Mark step as failed
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 1}

    async def _research_step2_general_search(self, session: FactCheckSession, user_input: str, step1_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 2: Conduct general research on the summarized question
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=2,
                step_type='general_research',
                description='Conducting general research on the topic',
                status='in_progress'
            )
            
            prompt = f"""
            You are an expert researcher conducting comprehensive background research. Based on the research understanding, gather broad information to build a foundation of knowledge about the topic.

            Original User Request: {user_input}

            Research Understanding from Step 1:
            {json.dumps(step1_result, indent=2)}

            Conduct thorough web searches to gather:
            1. Foundational information and background context
            2. Current state of knowledge and recent developments
            3. Key facts, data, and statistics
            4. Major perspectives and different viewpoints
            5. Important trends and patterns
            6. Authoritative sources and expert insights

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "general_findings": [
                    {{
                        "topic": "Specific aspect or subtopic",
                        "key_information": "Important information found about this topic",
                        "source_type": "academic|news|government|industry|expert|other",
                        "reliability": "high|medium|low"
                    }}
                ],
                "key_information": ["Most important facts or pieces of information discovered"],
                "topic_overview": "Comprehensive overview of the topic based on research findings",
                "related_topics": ["Related topics or areas that emerged during research"],
                "preliminary_insights": ["Initial insights or patterns observed"],
                "areas_for_deeper_research": ["Specific areas that warrant more detailed investigation"],
                "information_gaps": ["Areas where information is lacking or unclear"],
                "research_quality_assessment": "Assessment of the quality and availability of information on this topic"
            }}

            Focus on building comprehensive understanding through diverse, reliable sources. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 2,
                "interaction_type": "general_research"
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='research_step2_general_search',
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
                
                logger.info(f"Research Step 2 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Research Step 2 JSON response: {str(e)}")
                
                fallback_result = self._create_research_fallback_response(2, response_text, citations)
                step.summary = fallback_result.get("summary", "Research Step 2 completed with a parsing error.")

                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Research Step 2 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Research Step 2: {str(e)}")
            
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 2}

    async def _research_step3_specific_exploration(self, session: FactCheckSession, step1_result: Dict[str, Any], step2_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Step 3: Conduct specific, detailed research on identified areas
        """
        try:
            # Create analysis step
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=3,
                step_type='specific_research',
                description='Conducting specific detailed research',
                status='in_progress'
            )
            
            prompt = f"""
            You are an expert researcher conducting targeted investigation. Based on the foundational research, now explore specific aspects in greater depth to provide comprehensive understanding.

            Research Understanding:
            {json.dumps(step1_result, indent=2)}

            General Research Findings:
            {json.dumps(step2_result, indent=2)}

            Conduct focused searches to explore:
            1. Detailed analysis of the most important areas identified
            2. Expert perspectives and authoritative opinions
            3. Specific evidence, case studies, and real-world examples
            4. Current debates, challenges, and emerging issues
            5. Practical implications and applications
            6. Recent developments and future outlook

            CRITICAL: You MUST respond with ONLY valid JSON. Do not include any text before or after the JSON. Do not use markdown formatting or code blocks.

            Provide your response in this EXACT JSON structure:
            {{
                "detailed_findings": [
                    {{
                        "area": "Specific research area explored",
                        "key_insights": "Detailed insights discovered",
                        "evidence_type": "statistical|qualitative|expert_opinion|case_study|other",
                        "confidence_level": "high|medium|low",
                        "implications": "What this finding means for the research question"
                    }}
                ],
                "specific_insights": ["Specific, detailed insights that directly address the research question"],
                "expert_opinions": [
                    {{
                        "expert": "Expert name or description",
                        "expertise": "Area of expertise",
                        "opinion": "Summary of their perspective",
                        "context": "Context or basis for their opinion"
                    }}
                ],
                "case_studies": ["Relevant case studies or examples found"],
                "data_points": [
                    {{
                        "metric": "Specific data point or statistic",
                        "value": "The actual value or finding",
                        "source": "Source of the data",
                        "context": "What this data means"
                    }}
                ],
                "conflicting_viewpoints": ["Different perspectives or contradictory information found"],
                "research_gaps": ["Areas where more research is needed"],
                "practical_applications": ["How this research can be applied or used"]
            }}

            Focus on depth and specificity to provide comprehensive answers. RESPOND ONLY WITH THE JSON STRUCTURE ABOVE.
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "step": 3,
                "interaction_type": "specific_research"
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='research_step3_specific_exploration',
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
                
                logger.info(f"Research Step 3 completed with {len(citations)} citations")
                return result
                
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse Research Step 3 JSON response: {str(e)}")
                
                fallback_result = self._create_research_fallback_response(3, response_text, citations)
                step.summary = fallback_result.get("summary", "Research Step 3 completed with a parsing error.")

                step.status = 'completed'
                step.completed_at = timezone.now()
                step.result_data = fallback_result
                await sync_to_async(step.save)()
                
                logger.info(f"Research Step 3 completed with fallback response and {len(citations)} citations")
                return fallback_result
                
        except Exception as e:
            logger.error(f"Error in Research Step 3: {str(e)}")
            
            step.status = 'failed'
            step.error_message = str(e)
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return {"error": str(e), "step": 3}

    async def _research_generate_final_report(self, session: FactCheckSession, user_input: str, step1_result: Dict[str, Any], step2_result: Dict[str, Any], step3_result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate final research report as a comprehensive markdown response
        """
        try:
            prompt = f"""
            You are an expert researcher writing a comprehensive research report. Your goal is to help the audience fully understand the answer to their research question through clear, engaging writing.

            Original Research Request: {user_input}

            Research Process Summary:
            Step 1 - Understanding: {json.dumps(step1_result, indent=2)}
            Step 2 - General Research: {json.dumps(step2_result, indent=2)}
            Step 3 - Specific Investigation: {json.dumps(step3_result, indent=2)}

            Write a comprehensive research report in markdown format that addresses the user's question. Focus on helping the audience understand the topic thoroughly rather than providing recommendations or action items.

            Your report should:
            - Start with a clear, engaging introduction that frames the research question and provides a short and concise overview of the conclusions drawn
            - Present findings in a logical, easy-to-follow structure
            - Include key insights, data, and expert perspectives discovered
            - Explain complex concepts in accessible language
            - Highlight different viewpoints when they exist
            - Discuss current trends and recent developments
            - Address any limitations or gaps in the available information
            - Conclude with a synthesis that answers the original question

            Write in a style similar to a high-quality research article or investigative report. Use markdown formatting including:
            - Headers (## and ###) to organize sections
            - **Bold text** for emphasis on key points
            - *Italics* for important terms or concepts
            - Bullet points or numbered lists where appropriate
            - > Blockquotes for significant expert opinions or key insights

            Do NOT include:
            - Specific action recommendations
            - Detailed methodology sections
            - Formal citations (but you can reference "recent studies" or "experts indicate")

            Focus on being informative, engaging, and helping the reader gain deep understanding of the topic.

            Write your complete research report in markdown format below:
            """
            
            response_text, citations = await self._make_web_search_request(prompt)
            
            # Log the interaction
            interaction_data = {
                "response": response_text,
                "citations": citations,
                "web_search_used": True,
                "interaction_type": "research_report_generation"
            }
            
            await sync_to_async(ChatGPTInteraction.objects.create)(
                session=session,
                interaction_type='research_final_report',
                prompt=prompt,
                response=json.dumps(interaction_data),
                model_used=self.advModel,
                tokens_used=None
            )
            
            # Return the markdown report directly (no JSON parsing needed)
            return {
                "research_report": {
                    "markdown_content": response_text,
                    "format": "markdown",
                    "title": "Research Report",
                    "executive_summary": response_text[:300] + "..." if len(response_text) > 300 else response_text
                },
                "citations": citations,
                "web_search_used": True
            }
                
        except Exception as e:
            logger.error(f"Error in final research report generation: {str(e)}")
            return {"error": str(e)}

    async def conduct_research_with_web_search(self, session: FactCheckSession, user_input: str, image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """
        Conduct comprehensive research using web search in multiple steps
        This orchestrates the 3-step research process
        """
        try:
            logger.info(f"Starting multi-step research analysis for session {session.session_id}")
            
            # Step 1: Understand the research request
            step1_result = await self._research_step1_understand_request(session, user_input, image_data)
            if step1_result.get('error') and not step1_result.get('parsing_error'):
                logger.error(f"Research Step 1 failed: {step1_result.get('error')}")
                return step1_result
            
            # Step 2: General research (continue even if Step 1 had parsing issues)
            step2_result = await self._research_step2_general_search(session, user_input, step1_result)
            if step2_result.get('error') and not step2_result.get('parsing_error'):
                logger.error(f"Research Step 2 failed: {step2_result.get('error')}")
                # Continue with partial results
                
            # Step 3: Specific exploration (continue even if previous steps had parsing issues)
            step3_result = await self._research_step3_specific_exploration(session, step1_result, step2_result)
            if step3_result.get('error') and not step3_result.get('parsing_error'):
                logger.error(f"Research Step 3 failed: {step3_result.get('error')}")
                # Continue with partial results
                
            # Generate final research report
            final_report = await self._research_generate_final_report(session, user_input, step1_result, step2_result, step3_result)
            if final_report.get('error'):
                logger.error(f"Research final report generation failed: {final_report.get('error')}")
                return final_report
            
            # Combine all citations
            all_citations = []
            for step_result in [step1_result, step2_result, step3_result]:
                if isinstance(step_result, dict) and "citations" in step_result:
                    all_citations.extend(step_result["citations"])
            
            # Add citations from final report
            if "citations" in final_report:
                all_citations.extend(final_report["citations"])
            
            # Check if we had any parsing errors
            parsing_errors = [
                step_result.get('parsing_error', False) 
                for step_result in [step1_result, step2_result, step3_result]
            ]
            had_parsing_errors = any(parsing_errors)
            
            # Return combined results in a research format
            final_result = {
                "research_type": "multi_step_web_search",
                "web_search_used": True,
                "had_parsing_errors": had_parsing_errors,
                "step1_understanding": step1_result,
                "step2_general_research": step2_result,
                "step3_specific_exploration": step3_result,
                "final_report": final_report.get("research_report", {}),
                "citations": all_citations,
                "research_summary": final_report.get("research_report", {}).get("executive_summary", "Research completed successfully"),
                "methodology": "Three-step web search research process",
                "format": "markdown",
                "markdown_content": final_report.get("research_report", {}).get("markdown_content", "Research report could not be generated")
            }
            
            logger.info(f"Multi-step research analysis completed for session {session.session_id} with {len(all_citations)} total citations")
            if had_parsing_errors:
                logger.warning(f"Research completed but had parsing errors in {sum(parsing_errors)} step(s)")
            
            return final_result
            
        except Exception as e:
            logger.error(f"Error in multi-step research analysis: {str(e)}")
            return {"error": str(e)}