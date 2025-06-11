#!/usr/bin/env python
import os
import sys
import csv
import json
import requests
import django
from decimal import Decimal

# Configurar el entorno de Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

# Importar los modelos necesarios
from evaluations.models import (
    EvaluationItem,
    RubricCategory,
    Student,
    Evaluation,
    RubricScore,
    PendingEvaluationStatus,
)
from django.db.models import Q

# Configuración
API_KEY = input("Introduce tu API key: ")
API_BASE_URL = "http://localhost:8000/api/evaluations"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}",
}

def get_or_create_evaluation_items():
    """
    Asegura que existen los elementos de evaluación necesarios y sus categorías de rúbrica
    """
    # Obtener o crear el elemento de evaluación "Theory"
    theory_item, theory_created = EvaluationItem.objects.get_or_create(
        name="Theory",
        defaults={
            "description": "Evaluación teórica de música",
            "term": "primera",  # Ajusta según corresponda
        }
    )
    
    if theory_created:
        print("Elemento de evaluación 'Theory' creado")
    else:
        print("Elemento de evaluación 'Theory' ya existe")
    
    # Obtener o crear el elemento de evaluación "Audition tests"
    audition_item, audition_created = EvaluationItem.objects.get_or_create(
        name="Audition tests",
        defaults={
            "description": "Pruebas de audición musical",
            "term": "primera",  # Ajusta según corresponda
        }
    )
    
    if audition_created:
        print("Elemento de evaluación 'Audition tests' creado")
    else:
        print("Elemento de evaluación 'Audition tests' ya existe")
    
    # Crear categorías de rúbrica para Audition tests si es necesario
    categories = [
        {"name": "Test Audiométrico", "max_points": Decimal("10.0"), "order": 1},
        {"name": "Test de Intervalos", "max_points": Decimal("10.0"), "order": 2},
        {"name": "Test de Acordes", "max_points": Decimal("10.0"), "order": 3},
    ]
    
    for cat_data in categories:
        category, created = RubricCategory.objects.get_or_create(
            name=cat_data["name"],
            evaluation_item=audition_item,
            defaults={
                "max_points": cat_data["max_points"],
                "order": cat_data["order"],
                "description": f"Puntuación en {cat_data['name']}",
            }
        )
        
        if created:
            print(f"Categoría de rúbrica '{cat_data['name']}' creada")
        else:
            print(f"Categoría de rúbrica '{cat_data['name']}' ya existe")
    
    return theory_item, audition_item

def find_student_by_name(first_name, last_name):
    """
    Busca un estudiante por nombre y apellidos
    """
    # Construir la consulta para buscar al estudiante
    # Primero intentamos una coincidencia exacta
    students = Student.objects.filter(
        user__name__icontains=f"{first_name}",
    ).filter(
        user__name__icontains=f"{last_name}"
    )
    
    if students.count() == 1:
        return students.first()
    elif students.count() > 1:
        print(f"ADVERTENCIA: Múltiples estudiantes encontrados con nombre similar a {first_name} {last_name}")
        return students.first()  # Tomamos el primero, pero advertimos
    else:
        print(f"ERROR: No se encontró el estudiante {first_name} {last_name}")
        return None

def save_theory_grade(student, theory_item, score):
    """
    Guarda la nota de teoría para un estudiante
    """
    if not student:
        return False
    
    # Crear o actualizar la evaluación
    try:
        evaluation, created = Evaluation.objects.update_or_create(
            student=student,
            evaluation_item=theory_item,
            defaults={
                "score": score,
                "max_score": Decimal("10.0"),
            }
        )
        
        # Eliminar de pendientes si existía
        PendingEvaluationStatus.objects.filter(
            student=student, 
            evaluation_item=theory_item
        ).delete()
        
        return True
    except Exception as e:
        print(f"Error guardando nota de teoría para {student}: {e}")
        return False

def save_audition_tests(student, audition_item, audiometrico, intervalos, acordes):
    """
    Guarda las notas de las pruebas de audición para un estudiante
    """
    if not student:
        return False
    
    try:
        # Primero obtenemos las categorías de rúbrica
        audiometrico_cat = RubricCategory.objects.get(
            name="Test Audiométrico", 
            evaluation_item=audition_item
        )
        intervalos_cat = RubricCategory.objects.get(
            name="Test de Intervalos", 
            evaluation_item=audition_item
        )
        acordes_cat = RubricCategory.objects.get(
            name="Test de Acordes", 
            evaluation_item=audition_item
        )
        
        # Crear la evaluación principal
        # Primero necesitamos calcular el score total según la fórmula
        # Total = Test Audiométrico*0.4 + Test de Intervalos*0.4 + Test de Acordes*0.2
        total_score = (
            Decimal(str(audiometrico)) * Decimal("0.4") +
            Decimal(str(intervalos)) * Decimal("0.4") +
            Decimal(str(acordes)) * Decimal("0.2")
        )
        
        # Crear o actualizar la evaluación
        evaluation, created = Evaluation.objects.update_or_create(
            student=student,
            evaluation_item=audition_item,
            defaults={
                "score": total_score,
                "max_score": Decimal("10.0"),
            }
        )
        
        # Guardar las puntuaciones de rúbrica
        RubricScore.objects.update_or_create(
            evaluation=evaluation,
            category=audiometrico_cat,
            defaults={"points": Decimal(str(audiometrico))}
        )
        
        RubricScore.objects.update_or_create(
            evaluation=evaluation,
            category=intervalos_cat,
            defaults={"points": Decimal(str(intervalos))}
        )
        
        RubricScore.objects.update_or_create(
            evaluation=evaluation,
            category=acordes_cat,
            defaults={"points": Decimal(str(acordes))}
        )
        
        # Eliminar de pendientes si existía
        PendingEvaluationStatus.objects.filter(
            student=student, 
            evaluation_item=audition_item
        ).delete()
        
        return True
    except Exception as e:
        print(f"Error guardando notas de audición para {student}: {e}")
        return False

def process_csv_file(file_path):
    """
    Procesa el archivo CSV de notas
    """
    # Obtener o crear los elementos de evaluación necesarios
    theory_item, audition_item = get_or_create_evaluation_items()
    
    success_count = 0
    error_count = 0
    
    with open(file_path, 'r', encoding='utf-8') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        
        for row in csv_reader:
            first_name = row.get('First Name', '').strip()
            last_name = row.get('Last Name', '').strip()
            theory_score = row.get('Nota Teoría (sobre 10)', '').strip()
            audiometrico = row.get('Test Audiométrico', '').strip()
            intervalos = row.get('Test de Intervalos', '').strip()
            acordes = row.get('Test Acordes', '').strip()
            
            # Validar los datos
            if not all([first_name, last_name, theory_score, audiometrico, intervalos, acordes]):
                print(f"ERROR: Datos incompletos para {first_name} {last_name}")
                error_count += 1
                continue
            
            try:
                # Convertir a decimal
                theory_score = Decimal(theory_score)
                audiometrico = Decimal(audiometrico)
                intervalos = Decimal(intervalos)
                acordes = Decimal(acordes)
            except Exception as e:
                print(f"ERROR: Formato de nota incorrecto para {first_name} {last_name}: {e}")
                error_count += 1
                continue
            
            # Buscar al estudiante
            student = find_student_by_name(first_name, last_name)
            if not student:
                error_count += 1
                continue
            
            # Guardar las notas
            theory_ok = save_theory_grade(student, theory_item, theory_score)
            audition_ok = save_audition_tests(student, audition_item, audiometrico, intervalos, acordes)
            
            if theory_ok and audition_ok:
                success_count += 1
                print(f"✓ Notas guardadas correctamente para {first_name} {last_name}")
            else:
                error_count += 1
    
    print(f"\nProceso completado: {success_count} estudiantes procesados correctamente, {error_count} errores")

if __name__ == "__main__":
    # Comprobar si se proporciona la ruta del archivo CSV como argumento
    if len(sys.argv) > 1:
        csv_file_path = sys.argv[1]
    else:
        # Usar la ruta por defecto
        csv_file_path = "notas-3.csv"
    
    # Verificar que el archivo existe
    if not os.path.exists(csv_file_path):
        print(f"El archivo {csv_file_path} no existe")
        sys.exit(1)
    
    # Procesar el archivo
    print(f"Procesando archivo {csv_file_path}...")
    process_csv_file(csv_file_path)
