import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

CHROMA_PATH = "./chroma_memory"

COLLECTION_NAME = "devops_knowledge"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

DEFAULT_RESULTS = 3


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

print()
print("Loading embedding model...")
print()

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL
)

print("Embedding model loaded.")
print()


# ============================================================
# CONNECT TO CHROMADB
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH
)


# ============================================================
# GET KNOWLEDGE COLLECTION
# ============================================================

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# SEARCH KNOWLEDGE
# ============================================================

def search_knowledge(
    query: str,
    limit: int = DEFAULT_RESULTS
):
    """
    Search the DevOps knowledge base.

    Flow:

        User question
              |
              v
        Embedding model
              |
              v
        Query vector
              |
              v
        ChromaDB
              |
              v
        Similar document chunks
    """

    if not query or not query.strip():
        return []

    query = query.strip()

    # --------------------------------------------------------
    # Convert question into embedding
    # --------------------------------------------------------

    query_embedding = embedding_model.encode(
        query
    ).tolist()

    # --------------------------------------------------------
    # Search ChromaDB
    # --------------------------------------------------------

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=limit,
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    # --------------------------------------------------------
    # Extract results
    # --------------------------------------------------------

    documents = results.get(
        "documents",
        [[]]
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]]
    )[0]

    distances = results.get(
        "distances",
        [[]]
    )[0]

    retrieved_chunks = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances
    ):

        retrieved_chunks.append(
            {
                "content": document,
                "source": metadata.get(
                    "source",
                    "unknown"
                ),
                "page": metadata.get(
                    "page",
                    "unknown"
                ),
                "chunk_index": metadata.get(
                    "chunk_index",
                    "unknown"
                ),
                "distance": distance
            }
        )

    return retrieved_chunks


# ============================================================
# DISPLAY RESULTS
# ============================================================

def display_results(
    query: str,
    results: list
):

    print()
    print("=" * 70)
    print("RAG SEARCH")
    print("=" * 70)

    print()
    print("Question:")
    print(query)

    print()
    print("Results found:", len(results))

    print()

    if not results:

        print("No relevant knowledge found.")

        print()

        return

    for index, result in enumerate(
        results,
        start=1
    ):

        print("-" * 70)

        print(
            f"RESULT {index}"
        )

        print()

        print(
            f"Source : {result['source']}"
        )

        print(
            f"Page   : {result['page']}"
        )

        print(
            f"Chunk  : {result['chunk_index']}"
        )

        print(
            f"Distance: {result['distance']:.4f}"
        )

        print()

        print("Retrieved knowledge:")

        print()

        print(
            result["content"]
        )

        print()

    print("=" * 70)
    print()


# ============================================================
# INTERACTIVE MODE
# ============================================================

def interactive_mode():

    print()
    print("=" * 70)
    print("DEVOPS RAG KNOWLEDGE SEARCH")
    print("=" * 70)

    print()

    print(
        "Knowledge collection:",
        COLLECTION_NAME
    )

    print(
        "Documents/chunks:",
        collection.count()
    )

    print()

    print(
        "Ask a question about Docker or Linux."
    )

    print(
        "Type 'exit' to quit."
    )

    print()

    while True:

        try:

            question = input(
                "Question: "
            ).strip()

        except (
            KeyboardInterrupt,
            EOFError
        ):

            print()
            print("Exiting...")
            break

        if not question:
            continue

        if question.lower() in (
            "exit",
            "quit"
        ):

            print()
            print("Exiting...")
            break

        results = search_knowledge(
            question,
            limit=DEFAULT_RESULTS
        )

        display_results(
            question,
            results
        )


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    interactive_mode()
