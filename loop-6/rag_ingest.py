import os
import uuid

import chromadb
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

KNOWLEDGE_DIR = "./knowledge"

CHROMA_PATH = "./chroma_memory"

COLLECTION_NAME = "devops_knowledge"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# Chunk configuration
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


# ============================================================
# LOAD EMBEDDING MODEL
# ============================================================

print()
print("Loading embedding model...")
print()

embedding_model = SentenceTransformer(EMBEDDING_MODEL)

print("Embedding model loaded.")
print()


# ============================================================
# CONNECT TO CHROMADB
# ============================================================

chroma_client = chromadb.PersistentClient(
    path=CHROMA_PATH
)

collection = chroma_client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# EXTRACT TEXT FROM PDF
# ============================================================

def extract_pdf_text(pdf_path):
    """
    Extract text from every page of a PDF.
    """

    reader = PdfReader(pdf_path)

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):

        text = page.extract_text()

        if text:
            pages.append(
                {
                    "page": page_number,
                    "text": text.strip()
                }
            )

    return pages


# ============================================================
# CHUNK TEXT
# ============================================================

def create_chunks(text):
    """
    Split text into overlapping chunks.

    Example:

    Chunk 1
    0 ---------------- 1000

             overlap

    Chunk 2
             850 ---------------- 1850
    """

    chunks = []

    start = 0

    while start < len(text):

        end = start + CHUNK_SIZE

        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - CHUNK_OVERLAP

    return chunks


# ============================================================
# FIND PDF FILES
# ============================================================

def find_pdf_files():

    pdf_files = []

    for filename in os.listdir(KNOWLEDGE_DIR):

        if filename.lower().endswith(".pdf"):

            pdf_path = os.path.join(
                KNOWLEDGE_DIR,
                filename
            )

            pdf_files.append(pdf_path)

    return sorted(pdf_files)


# ============================================================
# INGEST PDF
# ============================================================

def ingest_pdf(pdf_path):

    filename = os.path.basename(pdf_path)

    print("=" * 60)
    print(f"Processing: {filename}")
    print("=" * 60)

    pages = extract_pdf_text(pdf_path)

    print(f"Pages found: {len(pages)}")

    all_chunks = []

    for page in pages:

        page_chunks = create_chunks(
            page["text"]
        )

        for chunk_index, chunk in enumerate(page_chunks):

            all_chunks.append(
                {
                    "text": chunk,
                    "page": page["page"],
                    "chunk_index": chunk_index
                }
            )

    print(f"Chunks created: {len(all_chunks)}")

    if not all_chunks:
        print("WARNING: No text extracted.")
        return

    # --------------------------------------------------------
    # Create embeddings
    # --------------------------------------------------------

    print("Creating embeddings...")

    texts = [
        item["text"]
        for item in all_chunks
    ]

    embeddings = embedding_model.encode(
        texts,
        show_progress_bar=True
    )

    # --------------------------------------------------------
    # Store in ChromaDB
    # --------------------------------------------------------

    ids = []
    documents = []
    embedding_list = []
    metadatas = []

    for item, embedding in zip(
        all_chunks,
        embeddings
    ):

        document_id = str(uuid.uuid4())

        ids.append(document_id)

        documents.append(
            item["text"]
        )

        embedding_list.append(
            embedding.tolist()
        )

        metadatas.append(
            {
                "source": filename,
                "page": item["page"],
                "chunk_index": item["chunk_index"],
                "type": "devops_knowledge"
            }
        )

    collection.upsert(
        ids=ids,
        documents=documents,
        embeddings=embedding_list,
        metadatas=metadatas
    )

    print(
        f"Stored {len(all_chunks)} chunks in ChromaDB."
    )

    print()


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("=" * 60)
    print("DEVOPS RAG INGESTION")
    print("=" * 60)
    print()

    if not os.path.exists(KNOWLEDGE_DIR):

        print(
            f"Knowledge directory does not exist: "
            f"{KNOWLEDGE_DIR}"
        )

        return

    pdf_files = find_pdf_files()

    if not pdf_files:

        print(
            "No PDF files found in "
            f"{KNOWLEDGE_DIR}"
        )

        return

    print(
        f"Found {len(pdf_files)} PDF file(s)."
    )

    print()

    for pdf_path in pdf_files:

        ingest_pdf(pdf_path)

    print("=" * 60)
    print("INGESTION COMPLETE")
    print("=" * 60)

    print()

    print(
        "Total documents/chunks in ChromaDB:",
        collection.count()
    )

    print()


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    main()
