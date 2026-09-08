import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime
import uuid


# ============================================================
# Configuration
# ============================================================

CHROMA_PATH = "./chroma_memory"

COLLECTION_NAME = "conversation_memory"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"


# ============================================================
# Initialize embedding model
# ============================================================

print("Loading embedding model...")

embedding_model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")


# ============================================================
# Initialize ChromaDB
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# Add long-term memory
# ============================================================

def save_memory(
    conversation_id: str,
    memory: str,
    memory_type: str = "conversation"
):
    """
    Store a long-term conversational memory.
    """

    memory_id = str(uuid.uuid4())

    embedding = embedding_model.encode(
        memory
    ).tolist()

    collection.add(
        ids=[memory_id],
        documents=[memory],
        embeddings=[embedding],
        metadatas=[
            {
                "conversation_id": conversation_id,
                "memory_type": memory_type,
                "created_at": datetime.utcnow().isoformat()
            }
        ]
    )

    return memory_id


# ============================================================
# Search long-term memory
# ============================================================

def search_memory(
    query: str,
    conversation_id: str | None = None,
    limit: int = 5
):
    """
    Search long-term memories using semantic similarity.
    """

    query_embedding = embedding_model.encode(
        query
    ).tolist()

    where = None

    if conversation_id:
        where = {
            "conversation_id": conversation_id
        }

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=limit,
        where=where
    )

    memories = []

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):
        memories.append(
            {
                "memory": document,
                "metadata": metadata,
                "distance": distance
            }
        )

    return memories


# ============================================================
# Get number of stored memories
# ============================================================

def memory_count():
    return collection.count()


# ============================================================
# Simple test
# ============================================================

if __name__ == "__main__":

    conversation_id = "test-conversation"

    save_memory(
        conversation_id,
        "The user's DevOps application runs using Docker Compose."
    )

    save_memory(
        conversation_id,
        "The user wants remediation actions to require human approval."
    )

    save_memory(
        conversation_id,
        "The DevOps agent uses GPT-OSS 120B through the Groq API."
    )

    print()
    print("Stored memories:", memory_count())

    print()
    print("Searching memory...")
    print()

    results = search_memory(
        "How does the user's DevOps application run?",
        limit=3
    )

    for result in results:
        print(
            "Memory:",
            result["memory"]
        )

        print(
            "Distance:",
            result["distance"]
        )

        print()
