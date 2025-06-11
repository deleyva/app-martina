#!/usr/bin/env python
import csv
import sys
import os
import requests
import json
from decimal import Decimal

# Configuración
API_BASE_URL = "http://localhost:8000/api"  # Ajusta si es necesario
CSV_FILE = "notas-3.csv"  # Archivo por defecto

def get_api_key():
    """Solicita al usuario su API key"""
    return input("Introduce tu API key: ")

def test_connection(headers):
    """Prueba la conexión a la API"""
    try:
        response = requests.get(f"{API_BASE_URL}/evaluations/groups", headers=headers)
        if response.status_code == 200:
            print("✓ Conexión a la API establecida correctamente")
            return True
        else:
            print(f"✗ Error de conexión: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        return False

def ensure_evaluation_items(headers):
    """Asegura que existan los elementos de evaluación necesarios"""
    # Buscar si existe Theory
    response = requests.post(
        f"{API_BASE_URL}/evaluations/search-evaluation-items",
        headers=headers,
        json={"name_query": "Theory"}
    )
    
    if response.status_code != 200:
        print(f"Error al buscar elemento de evaluación: {response.status_code} - {response.text}")
        return None, None
    
    theory_items = response.json()
    theory_item = None
    
    if not theory_items:
        # Crear el elemento si no existe
        create_response = requests.post(
            f"{API_BASE_URL}/evaluations/evaluation-items",
            headers=headers,
            json={
                "name": "Theory",
                "description": "Evaluación teórica de música",
                "term": "primera"  # Ajusta según corresponda
            }
        )
        if create_response.status_code == 200:
            theory_item = create_response.json()
            print("✓ Elemento de evaluación 'Theory' creado")
        else:
            print(f"✗ Error al crear el elemento Theory: {create_response.status_code}")
            return None, None
    else:
        theory_item = theory_items[0]
        print("✓ Elemento de evaluación 'Theory' encontrado")
    
    # Buscar si existe Audition tests
    response = requests.post(
        f"{API_BASE_URL}/evaluations/search-evaluation-items",
        headers=headers,
        json={"name_query": "Audition tests"}
    )
    
    if response.status_code != 200:
        print(f"Error al buscar elemento de evaluación: {response.status_code} - {response.text}")
        return theory_item, None
    
    audition_items = response.json()
    audition_item = None
    
    if not audition_items:
        # Crear el elemento si no existe
        create_response = requests.post(
            f"{API_BASE_URL}/evaluations/evaluation-items",
            headers=headers,
            json={
                "name": "Audition tests",
                "description": "Pruebas de audición musical",
                "term": "primera"  # Ajusta según corresponda
            }
        )
        if create_response.status_code == 200:
            audition_item = create_response.json()
            print("✓ Elemento de evaluación 'Audition tests' creado")
        else:
            print(f"✗ Error al crear el elemento Audition tests: {create_response.status_code}")
            return theory_item, None
    else:
        audition_item = audition_items[0]
        print("✓ Elemento de evaluación 'Audition tests' encontrado")
    
    # Verificar/Crear las categorías de rúbrica para audition tests
    rubric_categories = []
    category_names = ["Test Audiométrico", "Test de Intervalos", "Test de Acordes"]
    
    # Obtener todas las categorías para el elemento
    response = requests.get(
        f"{API_BASE_URL}/evaluations/rubric-categories?evaluation_item_id={audition_item['id']}",
        headers=headers
    )
    
    if response.status_code == 200:
        existing_categories = {cat['name']: cat for cat in response.json()}
    else:
        print(f"✗ Error al obtener categorías: {response.status_code}")
        existing_categories = {}
    
    # Crear las categorías que faltan
    for i, name in enumerate(category_names, 1):
        if name not in existing_categories:
            create_response = requests.post(
                f"{API_BASE_URL}/evaluations/rubric-categories",
                headers=headers,
                json={
                    "name": name,
                    "description": f"Puntuación en {name}",
                    "max_points": 10.0,
                    "order": i,
                    "evaluation_item_id": audition_item["id"]
                }
            )
            
            if create_response.status_code == 200:
                rubric_categories.append(create_response.json())
                print(f"✓ Categoría '{name}' creada")
            else:
                print(f"✗ Error al crear categoría '{name}': {create_response.status_code}")
        else:
            rubric_categories.append(existing_categories[name])
            print(f"✓ Categoría '{name}' encontrada")
    
    # Crear un mapeo de categorías por nombre para facilitar su búsqueda
    category_map = {cat['name']: cat for cat in rubric_categories}
    
    # Guardar IDs de las categorías en el objeto de elemento de evaluación
    audition_item['rubric_categories'] = category_map
    
    return theory_item, audition_item

def find_student(headers, first_name, last_name):
    """Busca un estudiante por nombre"""
    search_name = f"{first_name} {last_name}"
    
    response = requests.post(
        f"{API_BASE_URL}/evaluations/search-students",
        headers=headers,
        json={"name_query": search_name}
    )
    
    if response.status_code != 200:
        print(f"✗ Error al buscar estudiante {search_name}: {response.status_code}")
        return None
    
    students = response.json()
    
    if not students:
        print(f"✗ No se encontró al estudiante '{search_name}'")
        return None
    elif len(students) > 1:
        print(f"⚠ Se encontraron múltiples estudiantes con nombre similar a '{search_name}', usando el primero")
    
    return students[0]

def save_theory_grade(headers, student, theory_item, score):
    """Guarda la calificación de teoría"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/evaluations/evaluations",
            headers=headers,
            json={
                "student_id": student["id"],
                "evaluation_item_id": theory_item["id"],
                "score": float(score),
                "max_score": 10.0,
                "rubric_scores": []  # No tiene rúbricas
            }
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"✗ Error al guardar nota de teoría para {student['first_name']} {student['last_name']}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error al guardar nota de teoría: {e}")
        return False

def save_audition_grade(headers, student, audition_item, audiometrico, intervalos, acordes):
    """Guarda las calificaciones de audición con sus rúbricas"""
    try:
        # Obtener el ID de las categorías
        audiometrico_cat = audition_item['rubric_categories']['Test Audiométrico']
        intervalos_cat = audition_item['rubric_categories']['Test de Intervalos']
        acordes_cat = audition_item['rubric_categories']['Test de Acordes']
        
        # Calcular la puntuación total según la fórmula
        # Total = Test Audiométrico*0.4 + Test de Intervalos*0.4 + Test de Acordes*0.2
        total_score = (
            float(audiometrico) * 0.4 +
            float(intervalos) * 0.4 +
            float(acordes) * 0.2
        )
        
        response = requests.post(
            f"{API_BASE_URL}/evaluations/evaluations",
            headers=headers,
            json={
                "student_id": student["id"],
                "evaluation_item_id": audition_item["id"],
                "score": total_score,
                "max_score": 10.0,
                "rubric_scores": [
                    {
                        "category_id": audiometrico_cat["id"],
                        "points": float(audiometrico)
                    },
                    {
                        "category_id": intervalos_cat["id"],
                        "points": float(intervalos)
                    },
                    {
                        "category_id": acordes_cat["id"],
                        "points": float(acordes)
                    }
                ]
            }
        )
        
        if response.status_code == 200:
            return True
        else:
            print(f"✗ Error al guardar notas de audición para {student['first_name']} {student['last_name']}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error al guardar notas de audición: {e}")
        return False

def process_csv(headers, csv_file, theory_item, audition_item):
    """Procesa el archivo CSV de notas"""
    success_count = 0
    error_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as file:
        csv_reader = csv.DictReader(file)
        
        for i, row in enumerate(csv_reader, 1):
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            
            print(f"\nProcesando estudiante {i}: {first_name} {last_name}")
            
            # Verificar datos necesarios
            theory_score = row.get('Nota Teoría (sobre 10)', '').strip()
            audiometrico = row.get('Test Audiométrico', '').strip()
            intervalos = row.get('Test de Intervalos', '').strip()
            acordes = row.get('Test Acordes', '').strip()
            
            if not all([first_name, last_name, theory_score, audiometrico, intervalos, acordes]):
                print(f"✗ Datos incompletos para {first_name} {last_name}")
                error_count += 1
                continue
            
            # Buscar estudiante
            student = find_student(headers, first_name, last_name)
            if not student:
                error_count += 1
                continue
            
            # Guardar notas
            theory_success = save_theory_grade(headers, student, theory_item, theory_score)
            audition_success = save_audition_grade(
                headers, student, audition_item, 
                audiometrico, intervalos, acordes
            )
            
            if theory_success and audition_success:
                success_count += 1
                print(f"✓ Notas guardadas correctamente para {first_name} {last_name}")
            else:
                error_count += 1
    
    return success_count, error_count

def main():
    """Función principal"""
    # Verificar si se proporciona la ruta del CSV como argumento
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
    else:
        csv_file = CSV_FILE
    
    # Verificar que el archivo existe
    if not os.path.exists(csv_file):
        print(f"✗ El archivo {csv_file} no existe")
        return
    
    # Obtener API key y configurar headers
    api_key = get_api_key()
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    # Probar conexión
    if not test_connection(headers):
        print("✗ No se pudo establecer conexión. Verifica la API key y que el servidor esté en funcionamiento.")
        return
    
    # Preparar elementos de evaluación
    print("\nVerificando elementos de evaluación y categorías...")
    theory_item, audition_item = ensure_evaluation_items(headers)
    
    if not theory_item or not audition_item:
        print("✗ No se pudieron configurar los elementos de evaluación necesarios.")
        return
    
    # Procesar el archivo CSV
    print(f"\nProcesando archivo {csv_file}...")
    success, errors = process_csv(headers, csv_file, theory_item, audition_item)
    
    print(f"\n✅ Proceso completado: {success} estudiantes procesados correctamente, {errors} errores")

if __name__ == "__main__":
    main()
