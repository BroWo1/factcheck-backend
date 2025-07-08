import logging
import asyncio
from typing import Dict, List, Any
from googlesearch import search
from urllib.parse import urlparse
from django.conf import settings
from asgiref.sync import sync_to_async
from apps.fact_checker.models import SearchQuery, FactCheckSession

logger = logging.getLogger(__name__)


class GoogleSearchService:
    """Service for performing Google searches using googlesearch-python"""

    def __init__(self):
        pass

    @sync_to_async
    def _perform_search(self, query: str, num_results: int, **kwargs) -> List[str]:
        # This version removes the final invalid 'pause' argument.
        return list(search(query, num_results=num_results, **kwargs))

    async def search_general(self, session: FactCheckSession, query: str, num_results: int = 10) -> List[Dict[str, Any]]:
        """
        Perform a general Google search
        """
        try:
            # Log the search query
            search_query = await sync_to_async(SearchQuery.objects.create)(
                session=session,
                query_text=query,
                search_type='google'
            )

            search_results_urls = await self._perform_search(query, num_results)

            search_results = []
            for url in search_results_urls:
                search_results.append({
                    'title': url,  # googlesearch does not return title, use url instead
                    'url': url,
                    'snippet': '',  # googlesearch does not return snippet
                    'display_url': url,
                    'publisher': self._extract_publisher(url),
                    'search_query': query
                })

            # Update search query with results count
            search_query.results_count = len(search_results)
            await sync_to_async(search_query.save)()

            logger.info(f"Google search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Error in Google search for '{query}': {str(e)}")
            # Update search query with error
            if 'search_query' in locals():
                search_query.successful = False
                search_query.error_message = str(e)
                await sync_to_async(search_query.save)()
            return []

    async def search_news_sources(self, session: FactCheckSession, query: str) -> List[Dict[str, Any]]:
        """
        Search specifically in news sources
        """
        try:
            # Add news-specific operators to the query
            news_query = f"{query} (site:reuters.com OR site:ap.org OR site:bbc.com OR site:cnn.com OR site:npr.org)"

            search_query = await sync_to_async(SearchQuery.objects.create)(
                session=session,
                query_text=news_query,
                search_type='publisher_specific'
            )

            search_results_urls = await self._perform_search(news_query, 10)

            search_results = []
            for url in search_results_urls:
                search_results.append({
                    'title': url,
                    'url': url,
                    'snippet': '',
                    'display_url': url,
                    'publisher': self._extract_publisher(url),
                    'search_query': news_query,
                    'is_news_source': True
                })

            search_query.results_count = len(search_results)
            await sync_to_async(search_query.save)()

            logger.info(f"News search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Error in news search for '{query}': {str(e)}")
            if 'search_query' in locals():
                search_query.successful = False
                search_query.error_message = str(e)
                await sync_to_async(search_query.save)()
            return []

    async def search_fact_checkers(self, session: FactCheckSession, query: str) -> List[Dict[str, Any]]:
        """
        Search specifically in fact-checking websites
        """
        try:
            # Add fact-check specific operators to the query
            fact_check_query = f'{query} (site:snopes.com OR site:politifact.com OR site:factcheck.org OR site:reuters.com/fact-check)'

            search_query = await sync_to_async(SearchQuery.objects.create)(
                session=session,
                query_text=fact_check_query,
                search_type='fact_checker_specific'
            )

            search_results_urls = await self._perform_search(fact_check_query, 10)

            search_results = []
            for url in search_results_urls:
                search_results.append({
                    'title': url,
                    'url': url,
                    'snippet': '',
                    'display_url': url,
                    'publisher': self._extract_publisher(url),
                    'search_query': fact_check_query,
                    'is_fact_check_source': True
                })

            search_query.results_count = len(search_results)
            await sync_to_async(search_query.save)()

            logger.info(f"Fact-check search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Error in fact-check search for '{query}': {str(e)}")
            if 'search_query' in locals():
                search_query.successful = False
                search_query.error_message = str(e)
                await sync_to_async(search_query.save)()
            return []

    async def search_academic_sources(self, session: FactCheckSession, query: str) -> List[Dict[str, Any]]:
        """
        Search for academic and scholarly sources
        """
        try:
            # Focus on academic domains and publications
            academic_query = f"{query} (site:edu OR site:gov OR filetype:pdf OR \"peer reviewed\" OR \"research study\")"

            search_query = await sync_to_async(SearchQuery.objects.create)(
                session=session,
                query_text=academic_query,
                search_type='academic'
            )

            search_results_urls = await self._perform_search(academic_query, 10)

            search_results = []
            for url in search_results_urls:
                search_results.append({
                    'title': url,
                    'url': url,
                    'snippet': '',
                    'display_url': url,
                    'publisher': self._extract_publisher(url),
                    'search_query': academic_query,
                    'is_academic_source': True,
                    'credibility_score': 0.85  # High credibility for academic sources
                })

            search_query.results_count = len(search_results)
            await sync_to_async(search_query.save)()

            logger.info(f"Academic search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Error in academic search for '{query}': {str(e)}")
            if 'search_query' in locals():
                search_query.successful = False
                search_query.error_message = str(e)
                await sync_to_async(search_query.save)()
            return []

    async def search_with_date_filter(self, session: FactCheckSession, query: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Search with date filtering for recent information
        """
        try:
            search_query = await sync_to_async(SearchQuery.objects.create)(
                session=session,
                query_text=f"{query} (recent {days_back} days)",
                search_type='google'
            )

            search_results_urls = await self._perform_search(query, 10, tbs=f'qdr:d{days_back}')

            search_results = []
            for url in search_results_urls:
                search_results.append({
                    'title': url,
                    'url': url,
                    'snippet': '',
                    'display_url': url,
                    'publisher': self._extract_publisher(url),
                    'search_query': query,
                    'is__recent': True,
                    'date_filtered': days_back
                })

            search_query.results_count = len(search_results)
            await sync_to_async(search_query.save)()

            logger.info(f"Recent search for '{query}' returned {len(search_results)} results")
            return search_results

        except Exception as e:
            logger.error(f"Error in recent search for '{query}': {str(e)}")
            if 'search_query' in locals():
                search_query.successful = False
                search_query.error_message = str(e)
                await sync_to_async(search_query.save)()
            return []

    def _extract_publisher(self, url: str) -> str:
        """
        Extract publisher name from url
        """
        if not url:
            return ""

        try:
            netloc = urlparse(url).netloc
            domain = netloc.replace('www.', '')
        except Exception:
            domain = url.split('/')[2] if '//' in url else url.split('/')[0]
            domain = domain.replace('www.', '')

        # Map common domains to publisher names
        publisher_mapping = {
            'reuters.com': 'Reuters',
            'ap.org': 'Associated Press',
            'bbc.com': 'BBC',
            'cnn.com': 'CNN',
            'npr.org': 'NPR',
            'nytimes.com': 'New York Times',
            'washingtonpost.com': 'Washington Post',
            'wsj.com': 'Wall Street Journal',
            'snopes.com': 'Snopes',
            'factcheck.org': 'FactCheck.org',
            'politifact.com': 'PolitiFact'
        }

        return publisher_mapping.get(domain, domain.replace('.com', '').replace('.org', '').title())

    async def comprehensive_search(self, session: FactCheckSession, query: str) -> List[Dict[str, Any]]:
        """
        Perform a comprehensive search across general, news, and fact-check sources
        """
        try:
            # Create asyncio tasks for each search type
            tasks = [
                self.search_general(session, query),
                self.search_news_sources(session, query),
                self.search_fact_checkers(session, query)
            ]
            
            # Run tasks concurrently
            results = await asyncio.gather(*tasks)
            
            # Flatten list of lists and remove duplicates
            all_results = [item for sublist in results for item in sublist]
            unique_results = list({v['url']: v for v in all_results}.values())
            
            logger.info(f"Comprehensive search for '{query}' returned {len(unique_results)} unique results")
            return unique_results

        except Exception as e:
            logger.error(f"Error in comprehensive search for '{query}': {str(e)}")
            return []
