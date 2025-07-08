import logging
import asyncio
from typing import Dict, List, Optional, Any
from django.utils import timezone
from asgiref.sync import sync_to_async
from apps.fact_checker.models import FactCheckSession, AnalysisStep, Source
from apps.fact_checker.services.chatgpt_service import ChatGPTService
from apps.fact_checker.services.google_search_service import GoogleSearchService
from apps.fact_checker.services.web_crawler_service import WebCrawlerService

logger = logging.getLogger(__name__)


class AnalysisService:
    """Main orchestration service for the fact-checking workflow"""
    
    def __init__(self):
        self.chatgpt_service = ChatGPTService()
        self.search_service = GoogleSearchService()
        self.crawler_service = WebCrawlerService()
    
    async def perform_complete_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Perform the complete fact-checking analysis workflow
        """
        try:
            logger.info(f"Starting complete analysis for session {session.session_id}")
            
            # Update session status
            session.status = 'analyzing'
            await sync_to_async(session.save)()
            
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
            
            logger.info(f"Analysis completed for session {session.session_id}")
            
            return {
                'success': True,
                'session_id': str(session.session_id),
                'status': 'completed',
                'verdict': final_verdict.get('verdict'),
                'confidence_score': final_verdict.get('confidence_score'),
                'summary': final_verdict.get('summary'),
                'detailed_results': final_verdict
            }
            
        except Exception as e:
            logger.error(f"Error in complete analysis: {str(e)}")
            return await self._handle_analysis_error(session, f"Analysis error: {str(e)}", {})
        finally:
            # Cleanup resources
            await self.crawler_service.cleanup()
    
    async def get_analysis_progress(self, session: FactCheckSession) -> Dict[str, Any]:
        """
        Get the current progress of the analysis
        """
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
        
        progress_percentage = (completed_steps / total_steps) * 100 if total_steps > 0 else 0
        
        return {
            'session_id': str(session.session_id),
            'status': session.status,
            'progress_percentage': progress_percentage,
            'completed_steps': completed_steps,
            'total_steps': total_steps,
            'failed_steps': failed_steps,
            'current_step': {
                'step_number': current_step['step_number'] if current_step else None,
                'description': current_step['description'] if current_step else None,
                'step_type': current_step['step_type'] if current_step else None
            } if current_step else None,
            'steps': progress_steps
        }

    async def _step_initial_analysis(self, session: FactCheckSession) -> Dict[str, Any]:
        """Step 1: Initial analysis with ChatGPT"""
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
            
            # Update step
            step.status = 'completed' if not result.get('error') else 'failed'
            step.result_data = result
            step.completed_at = timezone.now()
            if result.get('error'):
                step.error_message = str(result.get('error'))
            await sync_to_async(step.save)()
            
            return result
            
        except Exception as e:
            logger.error(f"Error in initial analysis step: {str(e)}")
            if 'step' in locals():
                step.status = 'failed'
                step.error_message = str(e)
                await sync_to_async(step.save)()
            return {'error': str(e)}
    
    
    
    async def _step_search_sources(self, session: FactCheckSession, queries: List[str]) -> List[Dict[str, Any]]:
        """Step 2: Search for relevant sources"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=2,
                step_type='search',
                description=f'Searching for sources using {len(queries)} queries',
                status='in_progress'
            )
            
            # Perform comprehensive search for each query
            all_results = []
            for query in queries:
                results = await self.search_service.comprehensive_search(session, query)
                all_results.extend(results)
            
            # Remove duplicates
            search_results = list({v['url']: v for v in all_results}.values())
            
            # Update step
            step.status = 'completed'
            step.result_data = {
                'queries_used': queries,
                'results_count': len(search_results),
                'results': search_results[:20]  # Limit stored results
            }
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error in search sources step: {str(e)}")
            # Update step on error
            if 'step' in locals():
                step.status = 'failed'
                step.error_message = str(e)
                step.completed_at = timezone.now()
                await sync_to_async(step.save)()
            raise
    
    async def _step_crawl_sources(self, session: FactCheckSession, search_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Step 3: Crawl and extract content from sources"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=3,
                step_type='crawl',
                description=f'Extracting content from {len(search_results)} sources',
                status='in_progress'
            )
            
            # Extract URLs and prioritize them
            urls = self._prioritize_urls(search_results)
            
            # Crawl URLs (limit to top 5 to avoid excessive processing)
            crawled_results = await self.crawler_service.crawl_multiple_urls(
                session, urls[:5]
            )
            
            # Update step
            step.status = 'completed'
            step.result_data = {
                'urls_attempted': len(urls[:5]),
                'successful_crawls': len(crawled_results),
                'sources': crawled_results
            }
            step.completed_at = timezone.now()
            await sync_to_async(step.save)()
            
            return crawled_results
            
        except Exception as e:
            logger.error(f"Error in crawl sources step: {str(e)}")
            if 'step' in locals():
                step.status = 'failed'
                step.error_message = str(e)
                await sync_to_async(step.save)()
            return []
    
    async def _step_evaluate_sources(self, session: FactCheckSession, sources: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Step 3: Evaluate source credibility and relevance"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=3,
                step_type='source_evaluation',
                description=f'Evaluating {len(sources)} sources',
                status='in_progress'
            )
            
            if not sources:
                logger.warning("No sources to evaluate.")
                step.status = 'completed'
                step.result_data = {'message': 'No sources found to evaluate'}
                step.completed_at = timezone.now()
                await sync_to_async(step.save)()
                return {'source_evaluations': [], 'overall_assessment': 'No sources found'}

            evaluation = await self.chatgpt_service.evaluate_sources(session, sources)
            
            # Update step
            step.status = 'completed' if not evaluation.get('error') else 'failed'
            step.result_data = evaluation
            step.completed_at = timezone.now()
            if evaluation.get('error'):
                step.error_message = str(evaluation.get('error'))
            await sync_to_async(step.save)()
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Error in evaluate sources step: {str(e)}")
            if 'step' in locals():
                step.status = 'failed'
                step.error_message = str(e)
                await sync_to_async(step.save)()
            return {'error': str(e)}
    
    async def _step_generate_verdict(self, session: FactCheckSession, analysis_data: Dict[str, Any]) -> Dict[str, Any]:
        """Step 5: Generate final verdict"""
        try:
            step = await sync_to_async(AnalysisStep.objects.create)(
                session=session,
                step_number=5,
                step_type='final_analysis',
                description='Generating final fact-check verdict',
                status='in_progress'
            )
            
            # Generate final verdict with ChatGPT
            verdict = await self.chatgpt_service.generate_final_verdict(session, analysis_data)
            
            # Update step
            step.status = 'completed' if not verdict.get('error') else 'failed'
            step.result_data = verdict
            step.completed_at = timezone.now()
            if verdict.get('error'):
                step.error_message = str(verdict.get('error'))
            await sync_to_async(step.save)()
            
            return verdict
            
        except Exception as e:
            logger.error(f"Error in generate verdict step: {str(e)}")
            if 'step' in locals():
                step.status = 'failed'
                step.error_message = str(e)
                await sync_to_async(step.save)()
            return {'error': str(e)}
    
    def _prioritize_urls(self, search_results: List[Dict[str, Any]]) -> List[str]:
        """Prioritize URLs based on source credibility and relevance"""
        # Sort by priority: fact-check sites > news sources > others
        def get_priority(result):
            if result.get('is_fact_check_site'):
                return 1
            elif result.get('is_news_source'):
                return 2
            elif result.get('is_academic_source'):
                return 3
            else:
                return 4
        
        sorted_results = sorted(search_results, key=get_priority)
        return [result['url'] for result in sorted_results]
    
    async def _update_source_evaluations(self, session: FactCheckSession, evaluations: List[Dict[str, Any]]):
        """Update source records with ChatGPT evaluations"""
        try:
            for eval_data in evaluations:
                url = eval_data.get('url')
                if not url:
                    continue
                
                source = await sync_to_async(Source.objects.filter(session=session, url=url).first)()
                if source:
                    source.credibility_score = eval_data.get('credibility_score', source.credibility_score)
                    source.relevance_score = eval_data.get('relevance_score')
                    source.supports_claim = eval_data.get('supports_claim')
                    await sync_to_async(source.save)()
                    
        except Exception as e:
            logger.error(f"Error updating source evaluations: {str(e)}")
    
    async def _handle_analysis_error(self, session: FactCheckSession, error_message: str, error_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle analysis errors and update session status"""
        logger.error(f"Analysis error for session {session.session_id}: {error_message}")
        
        session.status = 'failed'
        session.completed_at = timezone.now()
        await sync_to_async(session.save)()
        
        return {
            'success': False,
            'session_id': str(session.session_id),
            'status': 'failed',
            'error': error_message,
            'error_data': error_data
        }
