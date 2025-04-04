from flask import Flask, request, render_template
import json
import os
import requests
import re

app = Flask(__name__)

# Configuración de Elasticsearch
#ELASTICSEARCH_URL = "https://127.0.0.1:9200"
#ELASTICSEARCH_USER = "elastic"
#ELASTICSEARCH_PASSWORD = "EyGOcJqQDd--_0vQf3Sk"

ELASTICSEARCH_URL = "https://h3zbk3xmad:ek3s8c5l2a@personal-search-3598143640.eu-central-1.bonsaisearch.net:443"
ELASTICSEARCH_USER = "h3zbk3xmad"
ELASTICSEARCH_PASSWORD = "ek3s8c5l2a"

# Verificar conexión con Elasticsearch
def is_elasticsearch_available():
    try:
        response = requests.get(
            ELASTICSEARCH_URL,
            auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD),
            verify=False
        )
        return response.status_code == 200
    except Exception as e:
        print(f"Error conectando a Elasticsearch: {e}")
        return False

# Guardar el archivo JSON en disco
def save_json_to_file(data, filename):
    try:
        base, ext = os.path.splitext(filename)  # Dividir nombre y extensión
        counter = 1

        # Si el archivo existe, generar un nuevo nombre con un número secuencial
        while os.path.exists(filename):
            filename = f"{base}_{counter}{ext}"
            counter += 1

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=4)
        print(f"Archivo guardado como {filename}")
    except Exception as e:
        print(f"Error guardando archivo JSON: {e}")

# Indexar en Elasticsearch
def index_to_elasticsearch(data, index):
    url = f"{ELASTICSEARCH_URL}/{index}/_doc"
    try:
        response = requests.post(
            url, json=data, auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD), verify=False
        )
        if response.status_code == 201:
            print(f"Indexado exitoso en {index}: {response.json()}")
            return True
        else:
            print(f"Error al indexar en Elasticsearch: {response.json()}")
            return False
    except Exception as e:
        print(f"Error al indexar en Elasticsearch: {e}")
        return False

def create_index_if_not_exists(index):
    print(f"Creando índice '{index}' en Elasticsearch...")
    url = f"{ELASTICSEARCH_URL}/{index}"
    
    # Verificar si el índice existe
    response = requests.get(url, auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD), verify=False)
    
    if response.status_code == 404:  # Si el índice no existe, créalo
        payload = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 1
            }
        }
        response = requests.put(url, json=payload, auth=(ELASTICSEARCH_USER, ELASTICSEARCH_PASSWORD), verify=False)
        if response.status_code in [200, 201]:
            print(f"Índice '{index}' creado exitosamente.")
        else:
            print(f"Error al crear el índice: {response.json()}")
    else:
        print(f"Índice '{index}' ya existe.")   
@app.route("/", methods=["GET", "POST"])
def home():
    success = False
    elastic_error = False

    if request.method == "POST":
        normativa = request.form.get("normativa")
        tipo = request.form.get("tipo")
        fecha = request.form.get("fecha")
        tema = request.form.get("tema")
        apartado = request.form.get("apartado")
        contenido = request.form.get("contenido")
        indice = request.form.get("indice")

        # Crear el objeto JSON
        data = {
            "normativa": normativa,
            "tipo": tipo,
            "fecha": fecha,
            "tema": tema,
            "apartado": apartado,
            "contenido": contenido,
        }

        # Limpiar el nombre del archivo
        clean_tema = re.sub(r"[^\w\s-]", "", tema).strip().replace(" ", "_")
        clean_apartado = re.sub(r"[^\w\s-]", "", apartado).strip().replace(" ", "_")
        filename = f"output_json/{clean_tema}-{clean_apartado}.json"

        # Crear la carpeta si no existe
        os.makedirs(os.path.dirname(filename), exist_ok=True)

        # Guardar el archivo JSON
        save_json_to_file(data, filename)

        # Verificar conexión con Elasticsearch
        if not is_elasticsearch_available():
            elastic_error = True
        else:
            create_index_if_not_exists(indice)
            # Indexar en Elasticsearch
            success = index_to_elasticsearch(data, indice)

    return render_template("index.html", success=success, elastic_error=elastic_error)

if __name__ == "__main__":
    app.run(debug=True)
