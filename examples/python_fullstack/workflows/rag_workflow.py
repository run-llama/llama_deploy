import os
from logging import getLogger
from pathlib import Path

from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
from llama_index.core.response_synthesizers import CompactAndRefine
from llama_index.core.schema import NodeWithScore
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.postprocessor.rankgpt_rerank import RankGPTRerank
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import AsyncQdrantClient, QdrantClient

logger = getLogger(__name__)


class RetrieverEvent(Event):
    """Result of running retrieval"""

    nodes: list[NodeWithScore]


class RerankEvent(Event):
    """Result of running reranking on retrieved nodes"""

    nodes: list[NodeWithScore]


class RAGWorkflow(Workflow):
    def __init__(self, index: VectorStoreIndex, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.index = index

    @step
    async def retrieve(self, ctx: Context, ev: StartEvent) -> RetrieverEvent | None:
        "Entry point for RAG, triggered by a StartEvent with `query`."
        logger.info(f"Retrieving nodes for query: {ev.get('query')}")
        query = ev.get("query")
        top_k = ev.get("top_k", 5)
        top_n = ev.get("top_n", 3)

        if not query:
            raise ValueError("Query is required!")

        # store the settings in the global context
        await ctx.set("query", query)
        await ctx.set("top_k", top_k)
        await ctx.set("top_n", top_n)

        retriever = self.index.as_retriever(similarity_top_k=top_k)
        nodes = await retriever.aretrieve(query)
        return RetrieverEvent(nodes=nodes)

    @step
    async def rerank(self, ctx: Context, ev: RetrieverEvent) -> RerankEvent:
        # Rerank the nodes
        top_n = await ctx.get("top_n")
        query = await ctx.get("query")

        ranker = RankGPTRerank(top_n=top_n, llm=OpenAI(model="gpt-4o"))

        try:
            new_nodes = ranker.postprocess_nodes(ev.nodes, query_str=query)
        except Exception:
            # Handle errors in the LLM response
            new_nodes = ev.nodes
        return RerankEvent(nodes=new_nodes)

    @step
    async def synthesize(self, ctx: Context, ev: RerankEvent) -> StopEvent:
        """Return a response using reranked nodes."""
        llm = OpenAI(model="gpt-4o-mini")
        synthesizer = CompactAndRefine(llm=llm)
        query = await ctx.get("query", default=None)

        response = await synthesizer.asynthesize(query, nodes=ev.nodes)

        return StopEvent(result=str(response))


def build_rag_workflow() -> RAGWorkflow:
    # host points to qdrant in docker-compose.yml
    qdrant_host = os.environ.get("QDRANT_HOST", "localhost")
    client = QdrantClient(host=qdrant_host, port=6333)
    aclient = AsyncQdrantClient(host=qdrant_host, port=6333)
    vector_store = QdrantVectorStore(
        collection_name="papers",
        client=client,
        aclient=aclient,
    )

    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=OpenAIEmbedding(model_name="text-embedding-3-small"),
    )

    # ensure the index exists
    here = Path(__file__).parent
    if not client.collection_exists("papers"):
        documents = SimpleDirectoryReader(here / "data").load_data()

        # Double pass chunking
        first_node_parser = SemanticSplitterNodeParser(
            embed_model=OpenAIEmbedding(model_name="text-embedding-3-small"),
        )
        second_node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=128)
        nodes = first_node_parser(documents)

        # Second pass chunking ensures that the nodes are not too large
        nodes = second_node_parser(nodes)

        index.insert_nodes(nodes)

    return RAGWorkflow(index=index, timeout=120.0)
