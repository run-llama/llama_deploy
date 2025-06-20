"""Web scraper workflows with local vector storage."""

import functools

from pathlib import Path
from typing import Any, Dict, List, Optional

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
    error: Optional[str] = None


class SearchResult(StopEvent):
    results: List[Dict[str, Any]]
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


class WebScraperWorkflow(Workflow):
    """Scrapes a given URL and adds it to the knowledge base."""

    @step
    async def scrape_and_index(self, ctx: Context, ev: ScrapeEvent) -> ScrapeResult:
        """Scrape webpage and add to vector store."""
        try:
            url = ev.url

            reader = SimpleWebPageReader(html_to_text=True)
            documents = reader.load_data([url])
            text_splitter = SentenceSplitter(
                chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP
            )
            nodes = text_splitter.get_nodes_from_documents(documents)
            index = get_vector_store_index()

            # Add nodes to index
            index.insert_nodes(nodes)

            return ScrapeResult(
                success=True,
                url=url,
                chunks_created=len(nodes),
            )

        except Exception as e:
            return ScrapeResult(
                success=False,
                url=url,
                chunks_created=0,
                error=str(e),
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
            include_sources = ev.include_sources
            client = get_qdrant_client()

            vector_store = QdrantVectorStore(
                client=client, collection_name=COLLECTION_NAME
            )
            index = VectorStoreIndex.from_vector_store(
                vector_store=vector_store, embed_model=get_embeddings_model()
            )
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)
            results = []
            for node in nodes:
                result = {
                    "text": node.text,
                    "score": node.score,
                }

                if include_sources and node.metadata:
                    result["metadata"] = node.metadata
                    if "url" in node.metadata:
                        result["source_url"] = node.metadata["url"]

                results.append(result)

            return SearchResult(results=results, query=query)

        except Exception:
            return SearchResult(results=[], query=query)


# Workflow instances
scraper_workflow = WebScraperWorkflow()
search_workflow = VectorSearchWorkflow()
