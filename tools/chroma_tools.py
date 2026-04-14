import chromadb
import os

# Define onde os dados serão salvos (na pasta do seu projeto)
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "../chroma_db_data")

# PersistentClient salva os dados em arquivos locais.
client = chromadb.PersistentClient(path=CHROMA_PATH)

# coleção de templates
collection = client.get_or_create_collection(name="ha_templates")

def add_template(task_type, template_content):
    collection.add(
        documents=[template_content],
        metadatas=[{"type": task_type}],
        ids=[f"template_{task_type}"]
    )
    print(f"--- [CHROMA] Template '{task_type}' salvo localmente! ---")

def get_templates(query):
    try:
        results = collection.query(query_texts=[query], n_results=1)
        if results['documents'] and len(results['documents'][0]) > 0:
            return results['documents'][0][0]
        return ""
    except Exception as e:
        print(f"Erro ao buscar no Chroma: {e}")
        return ""
    
def delete_template(task_type):
    try:
        collection.delete(ids=[f"template_{task_type}"])
        print(f"--- [CHROMA] Template '{task_type}' removido! ---")
        return True
    except Exception as e:
        print(f"Erro ao deletar no Chroma: {e}")
        return False

def get_exact_mission(task_type):
    """Busca um item no ChromaDB pelo ID EXATO, sem usar inteligência/vetor."""
    try:
        result = collection.get(ids=[f"template_{task_type}"])
        
        if result and result['documents'] and len(result['documents']) > 0:
            return result['documents'][0]
        return None
    except Exception as e:
        return None