from flask import Flask, request, jsonify
from flask_cors import CORS
from nltk.corpus import wordnet as wn
import requests
import google.generativeai as genai
import json
import spacy
import nltk
import os

# Configuración para la API de Gemini
genai.configure(api_key="AIzaSyASmi59Kcfpr5c8mrqD9iJ1osmRxAbI00I")
SPACY_MODEL_PATH = os.path.join(os.getcwd(), "es_core_news_sm/es_core_news_sm-3.8.0")
NLTK_DATA_PATH = os.path.join(os.getcwd(), "nltk_data")

# Inicializar el modelo spaCy
nlp = spacy.load(SPACY_MODEL_PATH)  # Cargar spaCy desde la carpeta local
nltk.data.path.append(NLTK_DATA_PATH)  # Agregar nltk_data al path

app = Flask(__name__)
CORS(app)

# Función para conectar a Elasticsearch usando peticiones directas
def connect_to_elasticsearch(host, user, password):
    try:
        # Realizar una petición GET para comprobar la conexión
        response = requests.get(
            f"{host}/_cluster/health", 
            auth=(user, password), 
            verify=False  # Desactivar SSL si es necesario
        )
        if response.status_code == 200:
            print("Conexión exitosa a Elasticsearch")
            return host
        else:
            print("No se pudo conectar a Elasticsearch")
            return None
    except Exception as e:
        print(f"Error al conectar a Elasticsearch: {e}")
        return None

# Obtener la lista de índices de Elasticsearch
def get_indices(host, user, password):
    try:
        response = requests.get(
            f"{host}/_cat/indices?v=true", 
            auth=(user, password), 
            verify=False  # Desactivar SSL si es necesario
        )
        if response.status_code == 200:
            # El resultado de la consulta se devuelve como un texto, lo convertimos a lista
            indices = response.text.strip().split('\n')[1:]  # Excluir cabecera
            indices_list = [line.split()[2] for line in indices]  # Extraer solo los nombres de los índices
            print("Índices obtenidos:", indices_list)
            return indices_list
        else:
            print(f"Error al obtener los índices: {response.text}")
            return []
    except Exception as e:
        print(f"Error al obtener los índices: {e}")
        return []

# Procesar consulta con spaCy
def preprocess_query_with_spacy(query):
    doc = nlp(query)
    keywords = [token.text for token in doc if token.pos_ in ["NOUN", "VERB", "ADJ", "ADV", "PROPN"]]
    
    original_tokens = query.split()
    for token in original_tokens:
        if token not in keywords:
            keywords.append(token)

    processed_query = " ".join(keywords)
    return processed_query if processed_query else query

# Realizar búsqueda en Elasticsearch
def search_elasticsearch(host, user, password, indices, query, fields=None):
    search_query = {
        "query": {
            "bool": {
                "should": [
                    {
                        "multi_match": {
                            "query": query,
                            "fields": fields if fields else ["contenido", "normativa", "tipo", "tema", "apartado"],
                            "fuzziness": "AUTO",
                            "operator": "or",
                            "type": "best_fields"
                        }
                    },
                    {
                        "match_phrase": {
                            "contenido": {
                                "query": query,
                                "slop": 5
                            }
                        }
                    }
                ]
            }
        },
        "size": 100
    }

    try:
        responses = []
        for index in indices:
            response = requests.get(
                f"{host}/{index}/_search", 
                auth=(user, password), 
                headers={"Content-Type": "application/json"}, 
                json=search_query, 
                verify=False  # Desactivar SSL si es necesario
            )
            if response.status_code == 200:
                responses.extend(response.json()['hits']['hits'])
            else:
                print(f"Error al realizar la búsqueda en el índice {index}: {response.text}")
        return {"hits": {"hits": responses}}
    except Exception as e:
        print(f"Error al realizar la búsqueda: {e}")
        return None

# Formatear resultados
def display_results(response):
    if not response or "hits" not in response:
        return []

    hits = response["hits"]["hits"]
    results = []
    for hit in hits:
        source = hit["_source"]
        results.append({
            "id": hit["_id"],
            "score": hit["_score"],
            "normativa": source.get("normativa", "Sin normativa"),
            "tipo": source.get("tipo", "Sin tipo"),
            "tema": source.get("tema", "Sin tema"),
            "apartado": source.get("apartado", "Sin apartado"),
            "content": source.get("contenido", "Sin contenido")
        })
    return results

# Consulta a Gemini
def query_gemini(query, documents):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
                Compórtate como experto en normativa educativa y orientación psicopedagógica. Responde únicamente basándote en los documentos proporcionados. 

                Pregunta: {query}

                A continuación tienes los documentos relevantes, revisa cuidadosamente su contenido para responder con precisión. Usa el texto proporcionado y sé específico:

                Reglas Importantes sobre la gestión de la información en los documentos:
                - No inventes información.
                - La normativa posterior en fecha modifica a la anterior.
                - La normativa autonómica no puede contradecir la estatal.
                - En caso de información derogada o modificada, no mostrarla.
                - detecta y corrige errores.
                - detecta apartados, por ejemplo fechas, nombre, lugares, sobre todo que terminen por :  y organizalo jerárquicamente o cronológicamente. 
                """
        for doc in documents:
            prompt += f"""
            Normativa: {doc['normativa']}
            Tipo: {doc['tipo']}
            Tema: {doc['tema']}
            Apartado: {doc['apartado']}
            Contenido: {doc['content'][:1500]}...\n\n
            """

        prompt += """
        Reglas importantes para responder:
            - Si en la propia consulta hay información empleala para responser.
            - Incluye siempre enlaces al documento de Blog. Para ello el documento BLOG lo separas por apartados, espacios o nuevas líneas e 
            - intenta que cuadre la pregunta que realiza el usuario con los enlaces de los documentos de tema Blog. 
            - Añade todas las explicaciones contextuales a los enlaces empleando los documentos que provienen de etpoep.
            - Formatea la salida adecuadamente en html para que sea comprendida, no incluyas los caracteres de apertura ```html y cierre.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error al realizar la consulta a Gemini: {e}")
        return "No se pudo generar el resumen."

# Conexión inicial a Elasticsearch
host = "https://h3zbk3xmad:ek3s8c5l2a@personal-search-3598143640.eu-central-1.bonsaisearch.net:443"
user = "h3zbk3xmad"
password = "ek3s8c5l2a"

es = connect_to_elasticsearch(host, user, password)

@app.route("/")
def home():
    return jsonify({"message": "Bienvenido a la API de búsqueda. Usa el endpoint /search para realizar consultas."})

@app.route("/indices", methods=["GET"])
def indices():
    if not es:
        return jsonify({"error": "No se pudo conectar a Elasticsearch"}), 500
    indices = get_indices(es, user, password)
    return jsonify({"indices": indices})

@app.route("/search", methods=["POST"])
def search():
    if not es:
        return jsonify({"error": "No se pudo conectar a Elasticsearch"}), 500

    data = request.json
    query = data.get("query", "")
    indices = data.get("indices", [])

    if not query:
        return jsonify({"error": "Debe proporcionar una consulta"}), 400

    if not indices:
        return jsonify({"error": "Debe seleccionar al menos un índice"}), 400

    processed_query = preprocess_query_with_spacy(query)
    response = search_elasticsearch(es, user, password, indices, processed_query)
    documents = display_results(response)

    if not documents:
        return jsonify({"message": "No se encontraron documentos relevantes."})

    gemini_response = query_gemini(query, documents)
    return jsonify({
        "query": query,
        "processed_query": processed_query,
        "results": documents,
        "gemini_response": gemini_response
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Usa el puerto que le asigna Render, por defecto 5000 si no se encuentra
    app.run(host="0.0.0.0", port=port)

handler = app
