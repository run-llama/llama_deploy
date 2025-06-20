"""Web scraper workflows with local vector storage."""

import functools
from urllib.parse import urljoin, urlparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from llama_index.core import VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.workflow import (
    Context,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.readers.web import SimpleWebPageReader
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams

QDRANT_DATA_DIR = Path("./data")
EMBEDDINGS_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDINGS_MODEL_DIMENSION = 384
COLLECTION_NAME = "knowledge_base"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200


# Events
class ScrapeEvent(StartEvent):
    url: str


class SearchEvent(StartEvent):
    query: str
    top_k: int = 5
    include_sources: bool = True


class ScrapeResult(StopEvent):
    success: bool
    url: str
    chunks_created: int
    pages_scraped: int = 1
    urls_processed: List[str] = []
    errors: List[str] = []
    error: Optional[str] = None


class SearchResultDetails(BaseModel):
    text: str
    score: float
    metadata: Dict[str, Any]
    source_url: Optional[str] = None


class SearchResult(StopEvent):
    results: List[SearchResultDetails]
    query: str


@functools.lru_cache(maxsize=1)
def get_embeddings_model() -> HuggingFaceEmbedding:
    """Get the embeddings model."""
    return HuggingFaceEmbedding(model_name=EMBEDDINGS_MODEL)


@functools.lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    """Get or create Qdrant client and collection."""
    client = QdrantClient(path=str(QDRANT_DATA_DIR / "qdrant"))

    # Create collection if it doesn't exist
    collections = client.get_collections().collections
    collection_names = [c.name for c in collections]

    if COLLECTION_NAME not in collection_names:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDINGS_MODEL_DIMENSION,
                distance=Distance.COSINE,
            ),
        )

    return client


@functools.lru_cache(maxsize=1)
def get_vector_store_index() -> VectorStoreIndex:
    """Get or create vector store."""
    client = get_qdrant_client()
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION_NAME)
    return VectorStoreIndex.from_vector_store(
        vector_store=vector_store, embed_model=get_embeddings_model()
    )


def get_domain(url: str) -> str:
    """Extract domain from URL."""
    return urlparse(url).netloc


def get_links_from_page(url: str) -> List[str]:
    """Extract all links from a webpage."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            # Convert relative URLs to absolute
            absolute_url = urljoin(url, href)
            links.append(absolute_url)

        return links
    except Exception:
        return []


def is_valid_crawl_url(url: str, base_domain: str) -> bool:
    """Check if URL is valid for crawling (same domain, not a file, etc)."""
    try:
        parsed = urlparse(url)

        # Must be same domain
        if parsed.netloc != base_domain:
            return False

        # Skip common file extensions and fragments
        path = parsed.path.lower()
        skip_extensions = {
            ".pdf",
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".zip",
            ".doc",
            ".docx",
        }
        if any(path.endswith(ext) for ext in skip_extensions):
            return False

        # Skip fragments and query params for deduplication
        if parsed.fragment:
            return False

        return True
    except Exception:
        return False


def is_url_already_processed(url: str) -> bool:
    """Check if a URL has already been processed and stored in the vector store."""
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        client = get_qdrant_client()

        # Search for points with this URL in metadata using proper Qdrant filter syntax
        result = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=Filter(
                must=[FieldCondition(key="url", match=MatchValue(value=url))]
            ),
            limit=1,  # We only need to know if any exist
            with_payload=True,
        )

        # If we found any points with this URL, it's already processed
        return len(result[0]) > 0
    except Exception as e:
        # If there's an error (e.g., collection doesn't exist yet), assume not processed
        print(f"Error checking URL {url}: {e}")
        return False


class WebScraperWorkflow(Workflow):
    """Scrapes a given URL and adds it to the knowledge base. Always scrapes max 20 pages at depth 2 using breadth-first traversal."""

    @step
    async def scrape_and_index(self, ctx: Context, ev: ScrapeEvent) -> ScrapeResult:
        """Scrape webpage(s) and add to vector store."""
        root_url = ev.url
        max_depth = 2  # Fixed depth
        max_pages = 20  # Fixed page limit

        # Recursive crawling with breadth-first traversal
        base_domain = get_domain(root_url)
        visited_urls: Set[str] = set()
        urls_to_process = [(root_url, 0)]  # (url, depth)
        pages_scraped = 0
        total_chunks = 0
        errors = []
        processed_urls = []

        reader = SimpleWebPageReader(html_to_text=True)
        text_splitter = SentenceSplitter(
            chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
        )
        index = get_vector_store_index()

        while urls_to_process and pages_scraped < max_pages:
            current_url, depth = urls_to_process.pop(0)

            # Skip if already visited in this session
            if current_url in visited_urls:
                continue

            # Skip if too deep
            if depth > max_depth:
                continue

            # Skip if already processed globally
            if is_url_already_processed(current_url):
                visited_urls.add(current_url)
                continue

            visited_urls.add(current_url)

            try:
                # Scrape current page
                documents = reader.load_data([current_url])
                nodes = text_splitter.get_nodes_from_documents(documents)

                # Add URL metadata to nodes
                for node in nodes:
                    node.metadata["url"] = current_url

                # Add to index
                index.insert_nodes(nodes)

                pages_scraped += 1
                total_chunks += len(nodes)
                processed_urls.append(current_url)

                # Get links for next level if we haven't reached max depth
                if depth < max_depth:
                    links = get_links_from_page(current_url)
                    for link in links:
                        if (
                            is_valid_crawl_url(link, base_domain)
                            and link not in visited_urls
                        ):
                            urls_to_process.append((link, depth + 1))

            except Exception as e:
                errors.append(f"Error processing {current_url}: {str(e)}")
                continue

        return ScrapeResult(
            success=True,
            url=root_url,
            chunks_created=total_chunks,
            pages_scraped=pages_scraped,
            urls_processed=processed_urls,
            errors=errors,
        )


class VectorSearchWorkflow(Workflow):
    """Workflow to search the vector store."""

    @step
    async def search_knowledge_base(
        self, ctx: Context, ev: SearchEvent
    ) -> SearchResult:
        """Search the vector knowledge base."""
        try:
            query = ev.query
            top_k = ev.top_k
            client = get_qdrant_client()

            vector_store = QdrantVectorStore(
                client=client, collection_name=COLLECTION_NAME
            )
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store, embed_model=get_embeddings_model()
            )
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            results: List[SearchResultDetails] = []
            for node in nodes:
                result = SearchResultDetails(
                    text=node.text,
                    score=node.score,
                    metadata=node.metadata,
                    source_url=node.metadata.get("url"),
                )

                results.append(result)

            return SearchResult(results=results, query=query)

        except Exception:
            return SearchResult(results=[], query=query)


# Workflow instances
scraper_workflow = WebScraperWorkflow()
search_workflow = VectorSearchWorkflow()
