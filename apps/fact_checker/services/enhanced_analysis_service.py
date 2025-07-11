import logging
import asyncio
from typing import Dict, List, Optional, Any
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.fact_checker.models import FactCheckSession, AnalysisStep, Source
from apps.fact_checker.services.chatgpt_service import ChatGPTService
from apps.fact_checker.services.chatgpt_web_search_service import ChatGPTWebSearchService
from apps.fact_checker.services.chatgpt_shallow_analysis_service import ChatGPTResearchService
from apps.fact_checker.services.google_search_service import GoogleSearchService
from apps.fact_checker.services.web_crawler_service import WebCrawlerService

logger = logging.getLogger(__name__)


class EnhancedAnalysisService:
    """
    Enhanced analysis service that can use traditional workflow, web search workflow, or research workflow
    """
    
    def __init__(self, use_web_search: bool = False, use_research: bool = False):
        self.use_web_search = use_web_search
        self.use_research = use_research
        
        if use_research:
            self.research_service = ChatGPTResearchService()
        elif use_web_search:
            self.chatgpt_service = ChatGPTWebSearchService()
        else:
            self.chatgpt_service = ChatGPTService()
            self.search_service = GoogleSearchService()
            self.crawler_service = WebCrawlerService()
    
    async def perform_complete_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Perform complete analysis using traditional, web search, or research workflow
        """
        try:
            logger.info(f"Starting complete analysis for session {session.session_id} (web_search={self.use_web_search}, research={self.use_research})")
            
            # Update session status
            session.status = 'analyzing'
            await sync_to_async(session.save)()
            
            if self.use_research:
                return await self._perform_research_analysis(session)
            elif self.use_web_search:
                return await self._perform_web_search_analysis(session)
            else:
                return await self._perform_traditional_analysis(session)
                
        except Exception as e:
            logger.error(f"Error in complete analysis: {str(e)}")
            return await self._handle_analysis_error(session, f"Analysis error: {str(e)}", {})
        finally:
            # Cleanup resources if using traditional workflow
            if not self.use_web_search and not self.use_research and hasattr(self, 'crawler_service'):
                await self.crawler_service.cleanup()
    
    async def _perform_web_search_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Perform analysis using ChatGPT's web search tool - now with multiple steps
        """
        try:
            # Get image data if present
            image_data = None
            if session.uploaded_image:
                image_path = session.uploaded_image.path
                image_data = await sync_to_async(self._read_image_data)(image_path)
            
            # Perform multi-step comprehensive analysis with web search
            # The ChatGPTWebSearchService now handles creating its own AnalysisStep records
            result = await self.chatgpt_service.analyze_claim_with_web_search(
                session, session.user_input, image_data
            )
            
            if result.get('error'):
                return await self._handle_analysis_error(session, "Web search analysis failed", result)
            
            # Extract verdict information from the final step
            verdict_info = {}
            if result.get('multi_step_analysis'):
                # Multi-step analysis - get verdict from step 4
                step4_result = result.get('step4_final_conclusion', {})
                verdict_info = step4_result.get('verdict', {})
            else:
                # Backwards compatibility - single step analysis
                verdict_info = result.get('verdict', {})
            
            # Update session with final results
            session.status = 'completed'
            session.final_verdict = verdict_info.get('classification', 'uncertain')
            session.confidence_score = verdict_info.get('confidence_score', 0.5)
            session.analysis_summary = verdict_info.get('summary', '')
            session.completed_at = timezone.now()
            await sync_to_async(session.save)()
            
            # Store citations as sources if available
            citations = result.get('citations', [])
            if citations:
                logger.info(f"Storing {len(citations)} citations as sources")
                await self._store_web_search_citations(session, citations)
            else:
                logger.warning("No citations found in web search result")
            
            logger.info(f"Web search analysis completed for session {session.session_id}")
            
            return {
                'success': True,
                'session_id': str(session.session_id),
                'status': 'completed',
                'verdict': verdict_info.get('classification'),
                'confidence_score': verdict_info.get('confidence_score'),
                'summary': verdict_info.get('summary'),
                'detailed_results': result,
                'web_search_used': True,
                'multi_step_analysis': result.get('multi_step_analysis', False),
                'citations': citations
            }
            
        except Exception as e:
            logger.error(f"Error in web search analysis: {str(e)}")
            raise
    
    async def _perform_research_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Perform general research analysis using ChatGPT's research service
        """
        try:
            # Get image data if present
            image_data = None
            if session.uploaded_image:
                image_path = session.uploaded_image.path
                image_data = await sync_to_async(self._read_image_data)(image_path)
            
            # Perform multi-step comprehensive research with web search
            # The ChatGPTResearchService handles creating its own AnalysisStep records
            result = await self.research_service.conduct_research_with_web_search(
                session, session.user_input, image_data
            )
            
            if result.get('error'):
                return await self._handle_analysis_error(session, "Research analysis failed", result)
            
            # Extract research report information
            final_report = result.get('final_report', {})
            research_summary = result.get('research_summary', 'Research completed successfully')
            markdown_content = result.get('markdown_content', '') or final_report.get('markdown_content', '')
            
            # For research mode, we want the full markdown content in analysis_summary
            # so it can be properly displayed in the frontend
            full_markdown = markdown_content if markdown_content else research_summary
            
            # Update session with final results
            session.status = 'completed'
            session.final_verdict = 'completed'  # Research doesn't have traditional verdicts
            session.confidence_score = 0.9  # High confidence for completed research
            session.analysis_summary = full_markdown  # Store full markdown content
            session.completed_at = timezone.now()
            await sync_to_async(session.save)()
            
            # Store citations as sources if available
            citations = result.get('citations', [])
            if citations:
                logger.info(f"Storing {len(citations)} citations as sources")
                await self._store_web_search_citations(session, citations)
            else:
                logger.warning("No citations found in research result")
            
            logger.info(f"Research analysis completed for session {session.session_id}")
            
            return {
                'success': True,
                'session_id': str(session.session_id),
                'status': 'completed',
                'research_type': 'general_research',
                'summary': full_markdown,  # Return full markdown content
                'detailed_results': result,
                'research_report': final_report,
                'markdown_content': markdown_content,
                'format': 'markdown',
                'web_search_used': True,
                'multi_step_analysis': True,
                'citations': citations,
                'methodology': result.get('methodology', 'Three-step web search research process')
            }
            
        except Exception as e:
            logger.error(f"Error in research analysis: {str(e)}")
            raise
    
    async def _perform_traditional_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Perform analysis using traditional workflow with manual search and crawling
        """
        # Step 1: Initial Analysis with ChatGPT
        initial_analysis = await self._step_initial_analysis(session)
        if not initial_analysis or initial_analysis.get('error'):
            return await self._handle_analysis_error(session, "Initial analysis failed", initial_analysis)
        
        # Step 2: Generate search queries
        search_queries = self._generate_search_queries(initial_analysis)
        
        # Step 3: Search for sources
        search_results = await self._step_search_sources(session, search_queries)
        if not search_results:
            return await self._handle_analysis_error(session, "No sources found", {})
        
        # Step 4: Crawl and extract content
        crawled_sources = await self._step_crawl_sources(session, search_results)
        if not crawled_sources:
            return await self._handle_analysis_error(session, "Content extraction failed", {})
        
        # Step 5: Evaluate sources with ChatGPT
        source_evaluation = await self._step_evaluate_sources(session, crawled_sources)
        if not source_evaluation or source_evaluation.get('error'):
            return await self._handle_analysis_error(session, "Source evaluation failed", source_evaluation)
        
        # Step 6: Generate final verdict
        final_verdict = await self._step_generate_verdict(session, {
            'initial_analysis': initial_analysis,
            'sources': crawled_sources,
            'source_evaluation': source_evaluation
        })
        
        if not final_verdict or final_verdict.get('error'):
            return await self._handle_analysis_error(session, "Final verdict generation failed", final_verdict)
        
        # Update session with final results
        session.status = 'completed'
        session.final_verdict = final_verdict.get('verdict', 'uncertain')
        session.confidence_score = final_verdict.get('confidence_score', 0.5)
        session.analysis_summary = final_verdict.get('summary', '')
        session.completed_at = timezone.now()
        await sync_to_async(session.save)()
        
        logger.info(f"Traditional analysis completed for session {session.session_id}")
        
        return {
            'success': True,
            'session_id': str(session.session_id),
            'status': 'completed',
            'verdict': final_verdict.get('verdict'),
            'confidence_score': final_verdict.get('confidence_score'),
            'summary': final_verdict.get('summary'),
            'detailed_results': final_verdict,
            'web_search_used': False
        }
    
    async def perform_hybrid_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Perform hybrid analysis that combines web search with traditional workflow
        """
        try:
            logger.info(f"Starting hybrid analysis for session {session.session_id}")
            
            # Update session status
            session.status = 'analyzing'
            await sync_to_async(session.save)()
            
            # Use web search service for analysis
            web_search_service = ChatGPTWebSearchService()
            
            # Perform comprehensive analysis with web search
            result = await web_search_service.analyze_claim_with_web_search(
                session, session.user_input, None
            )
            
            if result.get('error'):
                return await self._handle_analysis_error(session, "Web search analysis failed", result)
            
            # Update session with final results
            verdict_info = result.get('step4_final_conclusion', {}).get('verdict', {})
            session.status = 'completed'
            session.final_verdict = verdict_info.get('classification', 'uncertain')
            session.confidence_score = verdict_info.get('confidence_score', 0.5)
            session.analysis_summary = verdict_info.get('summary', '')
            session.completed_at = timezone.now()
            await sync_to_async(session.save)()
            
            logger.info(f"Hybrid analysis completed for session {session.session_id}")
            
            return {
                'success': True,
                'session_id': str(session.session_id),
                'status': 'completed',
                'verdict': verdict_info.get('classification'),
                'confidence_score': verdict_info.get('confidence_score'),
                'summary': verdict_info.get('summary'),
                'detailed_results': result,
                'web_search_used': True,
                'hybrid_mode': True,
                'citations': result.get('citations', [])
            }
            
        except Exception as e:
            logger.error(f"Error in hybrid analysis: {str(e)}")
            return await self._handle_analysis_error(session, f"Hybrid analysis error: {str(e)}", {})
        finally:
            # Cleanup resources
            if hasattr(self, 'crawler_service'):
                await self.crawler_service.cleanup()
    
    async def _store_web_search_citations(self, session: FactCheckSession, citations: List[Dict[str, Any]]) -> None:
        """
        Store web search citations as sources for consistency with traditional workflow
        """
        logger.debug(f"Storing {len(citations)} citations for session {session.session_id}")
        
        for i, citation in enumerate(citations):
            if citation.get('url'):
                logger.debug(f"Creating source {i+1}: {citation['url']}")
                await sync_to_async(Source.objects.create)(
                    session=session,
                    url=citation['url'],
                    title=citation.get('title', 'Web Search Citation'),
                    publisher='Web Search',
                    content_summary=f"Citation from web search (positions {citation.get('start_index', 0)}-{citation.get('end_index', 0)})",
                    credibility_score=0.8,  # High credibility since from web search tool
                    relevance_score=0.8,  # High relevance since it was cited
                    supports_claim=True  # Assume citations support the analysis
                )
                logger.info(f"Created source for citation: {citation['url']}")
            else:
                logger.warning(f"Skipping citation {i+1} - no URL: {citation}")
                
        logger.info(f"Successfully stored {len([c for c in citations if c.get('url')])} sources from citations")
    
    
    
    
    
    
    
    # Include methods from original AnalysisService for traditional workflow
    async def _step_initial_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """Step 1: Initial analysis with ChatGPT (traditional)"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=1,
                step_type='topic_analysis',
                description='Analyzing claim and identifying key topics',
                status='in_progress'
            )
            
            # Get image data if present
            image_data = None
            if session.uploaded_image:
                image_path = session.uploaded_image.path
                image_data = await sync_to_async(self._read_image_data)(image_path)
            
            # Perform initial analysis
            result = await self.chatgpt_service.analyze_initial_claim(
                session, session.user_input, image_data
            )
            
            if result.get('error'):
                step.status = 'failed'
                step.error_message = result.get('error')
                await sync_to_async(step.save)()
                return result
            
            # Mark step as completed
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.result_data = result
            await sync_to_async(step.save)()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in initial analysis: {str(e)}")
            return {"error": str(e)}
    
    def _generate_search_queries(self, initial_analysis: Dict[str, Any]) -> List[str]:
        """Generate search queries from initial analysis"""
        queries = []
        
        # Add main topic
        if 'main_topic' in initial_analysis:
            queries.append(initial_analysis['main_topic'])
        
        # Add factual claims
        if 'factual_claims' in initial_analysis:
            queries.extend(initial_analysis['factual_claims'][:3])  # Limit to 3
        
        # Add search keywords if available
        if 'search_keywords' in initial_analysis:
            queries.extend(initial_analysis['search_keywords'][:2])  # Limit to 2
        
        return queries[:5]  # Overall limit of 5 queries
    
    async def _step_search_sources(self, session: FactCheckSession, search_queries: List[str]) -> List[Dict[str, Any]]:
        """Step 2: Search for sources using Google Search"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=2,
                step_type='source_search',
                description='Searching for relevant sources',
                status='in_progress'
            )
            
            all_results = []
            
            for query in search_queries[:3]:  # Limit to top 3 queries
                try:
                    results = await self.search_service.search(query, num_results=5)
                    all_results.extend(results)
                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {str(e)}")
            
            # Remove duplicates based on URL
            unique_results = []
            seen_urls = set()
            for result in all_results:
                url = result.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    unique_results.append(result)
            
            if not unique_results:
                step.status = 'failed'
                step.error_message = 'No search results found'
                await sync_to_async(step.save)()
                return []
            
            # Mark step as completed
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.result_data = {'search_results': unique_results[:10]}  # Limit to top 10
            await sync_to_async(step.save)()
            
            return unique_results[:10]
            
        except Exception as e:
            logger.error(f"Error in source search: {str(e)}")
            return []
    
    async def _step_crawl_sources(self, session: FactCheckSession, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Step 3: Crawl and extract content from sources"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=3,
                step_type='content_extraction',
                description='Extracting content from sources',
                status='in_progress'
            )
            
            crawled_sources = []
            
            # Process sources concurrently but with a limit
            semaphore = asyncio.Semaphore(3)  # Limit concurrent crawling
            
            async def crawl_single_source(source):
                async with semaphore:
                    try:
                        content = await self.crawler_service.extract_content(source['url'])
                        if content:
                            # Store source in database
                            source_obj = await sync_to_async(Source.objects.create)(
                                session=session,
                                url=source['url'],
                                title=source.get('title', ''),
                                publisher=content.get('publisher', ''),
                                content_summary=content.get('summary', '')[:1000],  # Limit summary
                                credibility_score=None,  # Will be determined in evaluation
                                relevance_score=None  # Will be determined in evaluation
                            )
                            
                            return {
                                'url': source['url'],
                                'title': source.get('title', ''),
                                'publisher': content.get('publisher', ''),
                                'content_summary': content.get('summary', ''),
                                'source_id': source_obj.id
                            }
                    except Exception as e:
                        logger.warning(f"Failed to crawl {source['url']}: {str(e)}")
                    return None
            
            # Crawl sources concurrently
            tasks = [crawl_single_source(source) for source in search_results]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Filter successful results
            crawled_sources = [result for result in results if result and not isinstance(result, Exception)]
            
            if not crawled_sources:
                step.status = 'failed'
                step.error_message = 'No content could be extracted'
                await sync_to_async(step.save)()
                return []
            
            # Mark step as completed
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.result_data = {'crawled_count': len(crawled_sources)}
            await sync_to_async(step.save)()
            
            return crawled_sources
            
        except Exception as e:
            logger.error(f"Error in content extraction: {str(e)}")
            return []
    
    async def _step_evaluate_sources(self, session: FactCheckSession, crawled_sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Step 4: Evaluate sources with ChatGPT"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=4,
                step_type='source_evaluation',
                description='Evaluating source credibility and relevance',
                status='in_progress'
            )
            
            result = await self.chatgpt_service.evaluate_sources(session, crawled_sources)
            
            if result.get('error'):
                step.status = 'failed'
                step.error_message = result.get('error')
                await sync_to_async(step.save)()
                return result
            
            # Update source credibility scores in database
            if 'source_evaluations' in result:
                for evaluation in result['source_evaluations']:
                    url = evaluation.get('url')
                    if url:
                        try:
                            source = await sync_to_async(Source.objects.get)(session=session, url=url)
                            source.supports_claim = evaluation.get('supports_claim')
                            source.relevance_score = evaluation.get('relevance_score', 0.5)
                            source.credibility_score = evaluation.get('credibility_score', 0.5)
                            await sync_to_async(source.save)()
                        except Source.DoesNotExist:
                            logger.warning(f"Source not found for URL: {url}")
            
            # Mark step as completed
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.result_data = result
            await sync_to_async(step.save)()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in source evaluation: {str(e)}")
            return {"error": str(e)}
    
    async def _step_generate_verdict(self, session: FactCheckSession, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 5: Generate final verdict"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=5,
                step_type='final_verdict',
                description='Generating final verdict',
                status='in_progress'
            )
            
            result = await self.chatgpt_service.generate_final_verdict(session, analysis_data)
            
            if result.get('error'):
                step.status = 'failed'
                step.error_message = result.get('error')
                await sync_to_async(step.save)()
                return result
            
            # Mark step as completed
            step.status = 'completed'
            step.completed_at = timezone.now()
            step.result_data = result
            await sync_to_async(step.save)()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in verdict generation: {str(e)}")
            return {"error": str(e)}
    
    async def _handle_analysis_error(self, session: FactCheckSession, error_message: str, error_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis errors and update session status"""
        logger.error(f"Analysis error for session {session.session_id}: {error_message}")
        
        session.status = 'failed'
        session.error_message = error_message
        await sync_to_async(session.save)()
        
        return {
            'success': False,
            'session_id': str(session.session_id),
            'status': 'failed',
            'error': error_message,
            'error_data': error_data
        }
    
    def _read_image_data(self, image_path: str) -> bytes:
        """Read image data from file path"""
        try:
            with open(image_path, 'rb') as image_file:
                return image_file.read()
        except Exception as e:
            logger.error(f"Error reading image file {image_path}: {str(e)}")
            return None
    
    async def get_analysis_progress(self, session: FactCheckSession) -> Dict[str, Any]:
        """Get the current progress of the analysis"""
        steps = await sync_to_async(list)(AnalysisStep.objects.filter(session=session).order_by('step_number'))
        
        progress_steps = [{
            'step_number': step.step_number,
            'step_type': step.step_type,
            'description': step.description,
            'status': step.status,
            'completed_at': step.completed_at.isoformat() if step.completed_at else None
        } for step in steps]
        
        total_steps = len(progress_steps)
        completed_steps = len([step for step in progress_steps if step['status'] == 'completed'])
        failed_steps = len([step for step in progress_steps if step['status'] == 'failed'])
        current_step = next((step for step in progress_steps if step['status'] == 'in_progress'), None)
        
        # Determine expected steps based on analysis type
        multi_step_web_search = any(
            step['step_type'] in ['initial_web_search', 'deeper_exploration', 'source_credibility_evaluation', 'final_conclusion']
            for step in progress_steps
        )
        
        if multi_step_web_search:
            expected_steps = 4
        elif self.use_web_search:
            expected_steps = 4  # Legacy single-step web search
        else:
            expected_steps = 5  # Traditional analysis
            
        progress_percentage = (completed_steps / expected_steps) * 100 if expected_steps > 0 else 0
        
        return {
            'session_id': str(session.session_id),
            'status': session.status,
            'progress_percentage': min(progress_percentage, 100),  # Cap at 100%
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'expected_steps': expected_steps,
            'failed_steps': failed_steps,
            'multi_step_web_search': multi_step_web_search,
            'current_step': {
                'step_number': current_step['step_number'] if current_step else None,
                'description': current_step['description'] if current_step else None,
                'step_type': current_step['step_type'] if current_step else None
            } if current_step else None,
            'steps': progress_steps,
            'web_search_mode': self.use_web_search
        }