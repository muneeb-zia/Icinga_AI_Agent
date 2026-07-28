import os
from langchain_community.document_loaders import TextLoader
from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import MarkdownHeaderTextSplitter

# Initialize local HuggingFace embeddings instead of Ollama to avoid 501 errors
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

VECTOR_STORE_DIR = "./chroma_db"
DOCS_FILE = "docs/sample_troubleshooting.md"

def init_knowledge_base():
    """Initializes the vector store with troubleshooting docs if it doesn't exist."""
    if os.path.exists(VECTOR_STORE_DIR):
        print("Vector store already exists. Loading...")
        return Chroma(persist_directory=VECTOR_STORE_DIR, embedding_function=embeddings)
        
    print("Initializing vector store from docs...")
    if not os.path.exists(DOCS_FILE):
        print(f"Warning: {DOCS_FILE} not found. RAG will not work.")
        return None

    # Load and split the markdown document
    with open(DOCS_FILE, 'r') as f:
        content = f.read()

    headers_to_split_on = [
        ("##", "Header 2")
    ]
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on=headers_to_split_on)
    md_header_splits = markdown_splitter.split_text(content)

    # Create Chroma vector store
    vectorstore = Chroma.from_documents(
        documents=md_header_splits,
        embedding=embeddings,
        persist_directory=VECTOR_STORE_DIR
    )
    return vectorstore

def search_troubleshooting_guides(query: str, top_k: int = 2) -> str:
    """Searches the troubleshooting guide for relevant solutions."""
    db = init_knowledge_base()
    if not db:
        return "No knowledge base available."

    docs = db.similarity_search(query, k=top_k)
    
    if not docs:
        return "No relevant troubleshooting steps found in the knowledge base."
        
    results = []
    for doc in docs:
        header = doc.metadata.get('Header 2', 'General')
        results.append(f"--- Section: {header} ---\n{doc.page_content}")
        
    return "\n\n".join(results)

if __name__ == "__main__":
    print("Testing RAG Pipeline...")
    res = search_troubleshooting_guides("host is down")
    print("Query: 'host is down'")
    print("Result:")
    print(res)
