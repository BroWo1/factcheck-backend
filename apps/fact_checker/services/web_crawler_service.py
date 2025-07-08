import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime

import requests
from bs4 import BeautifulSoup  # retained for any fallback parsing needs
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from django.conf import settings
from openai import OpenAI
from asgiref.sync import sync_to_async

from apps.fact_checker.models import Source, FactCheckSession

logger = logging.getLogger(__name__)


class WebCrawlerService:
    """Service for crawling and extracting content from web pages using AsyncWebCrawler"""

    def __init__(self):
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # Prefer context-manager pattern but keep a long-lived instance here
        self.crawler = AsyncWebCrawler(verbose=True, openai_client=self.openai_client)

        # Re-usable requests session for any fall-back HTTP calls
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "FactCheck-Bot/1.0 (+http://example.com/bot)",
            }
        )

    async def crawl_url(
        self, session: FactCheckSession, url: str
    ) -> Optional[Dict[str, Any]]:
        """Crawl a single URL and persist the extracted content."""
        try:
            # Skip if already crawled for this session
            existing = await sync_to_async(Source.objects.filter(session=session, url=url).first)()
            if existing:
                logger.info("URL already crawled: %s", url)
                return self._source_to_dict(existing)

            logger.info("Crawling URL: %s", url)

            # Use Crawl4AI 0.6 config object
            config = CrawlerRunConfig(summarization=True)
            result = await self.crawler.arun(url=url, config=config)

            if not result.success:
                logger.error("Failed to crawl %s: %s", url, result.error_message)
                return None

            # Transform crawler result → model fields
            content_data = self._extract_content_data(result)

            source = await sync_to_async(Source.objects.create)(
                session=session,
                url=url,
                title=content_data["title"],
                content_summary=content_data["summary"],
                publish_date=content_data["publish_date"],
                accessed_at=datetime.utcnow(),
                is_primary_source=content_data["is_primary_source"],
                supports_claim=content_data["supports_claim"],
                relevance_score=content_data["relevance_score"],
            )

            logger.info("Stored crawled source: %s", url)
            return self._source_to_dict(source)

        except Exception as exc:
            logger.exception("Error while crawling %s: %s", url, exc)
            return None

    async def crawl_multiple_urls(
        self, session: FactCheckSession, urls: List[str]
    ) -> List[Dict[str, Any]]:
        """Crawl multiple URLs concurrently with limited parallelism."""
        logger.info("Starting to crawl %d URLs", len(urls))
        semaphore = asyncio.Semaphore(3)

        async def crawl_one(u: str):
            async with semaphore:
                return await self.crawl_url(session, u)

        tasks = [crawl_one(u) for u in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        successful = []
        for res in results:
            if isinstance(res, dict):
                successful.append(res)
            elif isinstance(res, Exception):
                logger.error("Unhandled crawl exception: %s", res)

        logger.info(
            "Crawled %d/%d URLs successfully", len(successful), len(urls)
        )
        return successful

    # ──────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────

    def _extract_content_data(self, crawler_result) -> Dict[str, Any]:
        """Map Crawl4AI result object to our DB schema."""
        return {
            "title": crawler_result.metadata.get("title"),
            "summary": crawler_result.summary,
            "publish_date": crawler_result.metadata.get("publish_date"),
            "is_primary_source": crawler_result.metadata.get("is_primary", False),
            "supports_claim": crawler_result.metadata.get("supports_claim", False),
            "relevance_score": crawler_result.metadata.get("relevance_score", 0.0),
        }

    def _source_to_dict(self, source: Source) -> Dict[str, Any]:
        """Convert a Source ORM instance to a serialisable dict."""
        return {
            "id": source.id,
            "url": source.url,
            "title": source.title,
            "content_summary": source.content_summary,
            "publish_date": source.publish_date.isoformat()
            if source.publish_date
            else None,
            "accessed_at": source.accessed_at.isoformat(),
            "is_primary_source": source.is_primary_source,
            "supports_claim": source.supports_claim,
            "relevance_score": source.relevance_score,
        }

    async def cleanup(self):
        """Gracefully close the AsyncWebCrawler session."""
        try:
            await self.crawler.close()
        except Exception as exc:
            logger.error("Error during crawler cleanup: %s", exc)