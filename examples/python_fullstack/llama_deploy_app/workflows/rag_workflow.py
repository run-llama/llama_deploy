import json
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex
from llama_index.core.node_parser import SemanticSplitterNodeParser, SentenceSplitter
from llama_index.core.response_synthesizers import CompactAndRefine
from llama_index.core.workflow import (
    Context,
    Event,
    Workflow,
    StartEvent,
    StopEvent,
    step,
)
from llama_index.core.schema import NodeWithScore
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.postprocessor.rankgpt_rerank import RankGPTRerank
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient, AsyncQdrantClient


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

        new_nodes = ranker.postprocess_nodes(ev.nodes, query_str=query)
        return RerankEvent(nodes=new_nodes)

    @step
    async def synthesize(self, ctx: Context, ev: RerankEvent) -> StopEvent:
        """Return a response using reranked nodes."""
        llm = OpenAI(model="gpt-4o-mini")
        synthesizer = CompactAndRefine(llm=llm)
        query = await ctx.get("query", default=None)

        response = await synthesizer.asynthesize(query, nodes=ev.nodes)

        # create a serialized version of the response and the source nodes
        result = {
            "response": str(response),
            "source_nodes": json.dumps([node.model_dump() for node in ev.nodes]),
        }
        return StopEvent(result=result)


def build_rag_workflow() -> RAGWorkflow:
    client = QdrantClient(host="qdrant", port=6333)
    aclient = AsyncQdrantClient(host="qdrant", port=6333)
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
    if not client.collection_exists("papers"):
        documents = SimpleDirectoryReader("data").load_data()

        # Double pass chunking
        first_node_parser = SemanticSplitterNodeParser(
            embed_model=OpenAIEmbedding(model_name="text-embedding-3-small"),
        )
        second_node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=128)
        nodes = first_node_parser(documents)

        # Second pass chunking ensures that the nodes are not too large
        nodes = second_node_parser(nodes)

        index.insert_nodes(nodes)

    return RAGWorkflow(index=index)
