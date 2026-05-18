"""
Vector Store service for Qdrant Cloud.
Provides retriever interface for the Policy RAG agent.
"""
from qdrant_client import QdrantClient
from langchain_qdrant import QdrantVectorStore
from app.core.config import settings
from app.core.llm import get_embeddings

COLLECTION_NAME = "hr_policies"

def get_qdrant_client():
    """Returns a QdrantClient with a generous timeout."""
    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=60, # Increase timeout to 60 seconds
    )

def get_policy_retriever(k: int = 4):
    """Returns a LangChain retriever backed by the Qdrant hr_policies collection."""
    embeddings = get_embeddings()
    client = get_qdrant_client()
    
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )
    return vectorstore.as_retriever(search_kwargs={"k": k})

def add_chunks(chunks: list[dict]):
    """Insert chunks into Qdrant, creating the collection if it doesn't exist."""
    from langchain_core.documents import Document
    from qdrant_client.http.models import Distance, VectorParams
    
    embeddings = get_embeddings()
    client = get_qdrant_client()
    
    # Ensure collection exists and matches dimension
    try:
        collection_info = client.get_collection(COLLECTION_NAME)
        vector_size = len(embeddings.embed_query("test"))
        if collection_info.config.params.vectors.size != vector_size:
            print(f"Dimension mismatch (expected {vector_size}, got {collection_info.config.params.vectors.size}). Recreating...")
            client.delete_collection(COLLECTION_NAME)
            client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
    except Exception:
        # Collection doesn't exist
        vector_size = len(embeddings.embed_query("test"))
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
    
    vectorstore = QdrantVectorStore(
        client=client,
        collection_name=COLLECTION_NAME,
        embedding=embeddings,
    )
    
    documents = []
    for chunk in chunks:
        doc = Document(
            page_content=chunk["text"],
            metadata=chunk["metadata"].model_dump() if hasattr(chunk["metadata"], "model_dump") else chunk["metadata"]
        )
        documents.append(doc)
        
    vectorstore.add_documents(documents)
    return len(documents)
