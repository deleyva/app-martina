from ninja import Router, Schema
from typing import List, Optional, Dict, Any
from django.shortcuts import get_object_or_404
from django.http import HttpRequest
from django.db.models import Q
from decimal import Decimal
from datetime import datetime

from .models import Student, EvaluationItem, RubricCategory, Evaluation, RubricScore, PendingEvaluationStatus
from api_keys.auth import DatabaseApiKey

# Crear un router en lugar de una instancia de NinjaAPI
router = Router(tags=["Evaluaciones"], auth=DatabaseApiKey())

# Schemas para la API
class StudentIn(Schema):
    first_name: str
    last_name: str
    group: str
    pending_evaluation_id: Optional[int] = None

class StudentOut(Schema):
    id: int
    first_name: str
    last_name: str
    group: str
    pending_evaluation_id: Optional[int] = None

class EvaluationItemIn(Schema):
    name: str
    term: Optional[str] = None
    description: Optional[str] = None

class EvaluationItemOut(Schema):
    id: int
    name: str
    term: Optional[str] = None
    description: Optional[str] = None

class RubricCategoryIn(Schema):
    name: str
    description: Optional[str] = None
    max_points: float = 2.0
    order: int = 0
    evaluation_item_id: Optional[int] = None

class RubricCategoryOut(Schema):
    id: int
    name: str
    description: Optional[str] = None
    max_points: float
    order: int
    evaluation_item_id: Optional[int] = None

# Endpoints para Estudiantes
@router.post("/students", response=StudentOut)
def create_student(request, payload: StudentIn):
    student_data = payload.dict()
    
    # Manejar la relación con pending_evaluation si existe
    pending_evaluation_id = student_data.pop('pending_evaluation_id', None)
    if pending_evaluation_id:
        pending_evaluation = get_object_or_404(EvaluationItem, id=pending_evaluation_id)
        student = Student.objects.create(**student_data, pending_evaluation=pending_evaluation)
    else:
        student = Student.objects.create(**student_data)
    
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "group": student.group,
        "pending_evaluation_id": student.pending_evaluation.id if student.pending_evaluation else None
    }

@router.get("/students", response=List[StudentOut])
def list_students(request, group: Optional[str] = None):
    queryset = Student.objects.all()
    if group:
        queryset = queryset.filter(group=group)
    
    return [
        {
            "id": student.id,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "group": student.group,
            "pending_evaluation_id": student.pending_evaluation.id if student.pending_evaluation else None
        }
        for student in queryset
    ]

@router.get("/students/{student_id}", response=StudentOut)
def get_student(request, student_id: int):
    student = get_object_or_404(Student, id=student_id)
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "group": student.group,
        "pending_evaluation_id": student.pending_evaluation.id if student.pending_evaluation else None
    }

@router.put("/students/{student_id}", response=StudentOut)
def update_student(request, student_id: int, payload: StudentIn):
    student = get_object_or_404(Student, id=student_id)
    student_data = payload.dict()
    
    # Manejar la relación con pending_evaluation si existe
    pending_evaluation_id = student_data.pop('pending_evaluation_id', None)
    if pending_evaluation_id:
        pending_evaluation = get_object_or_404(EvaluationItem, id=pending_evaluation_id)
        student.pending_evaluation = pending_evaluation
    
    # Actualizar campos
    student.first_name = student_data.get('first_name', student.first_name)
    student.last_name = student_data.get('last_name', student.last_name)
    student.group = student_data.get('group', student.group)
    student.save()
    
    return {
        "id": student.id,
        "first_name": student.first_name,
        "last_name": student.last_name,
        "group": student.group,
        "pending_evaluation_id": student.pending_evaluation.id if student.pending_evaluation else None
    }

@router.delete("/students/{student_id}")
def delete_student(request, student_id: int):
    student = get_object_or_404(Student, id=student_id)
    student.delete()
    return {"success": True}

# Endpoints para Grupos
@router.get("/groups")
def list_groups(request):
    groups = Student.objects.values_list('group', flat=True).distinct()
    return {"groups": list(groups)}

# Endpoints para EvaluationItems
@router.post("/evaluation-items", response=EvaluationItemOut)
def create_evaluation_item(request, payload: EvaluationItemIn):
    evaluation_item = EvaluationItem.objects.create(**payload.dict())
    return {
        "id": evaluation_item.id,
        "name": evaluation_item.name,
        "term": evaluation_item.term,
        "description": evaluation_item.description
    }

@router.get("/evaluation-items", response=List[EvaluationItemOut])
def list_evaluation_items(request, term: Optional[str] = None):
    queryset = EvaluationItem.objects.all()
    if term:
        queryset = queryset.filter(term=term)
    
    return [
        {
            "id": item.id,
            "name": item.name,
            "term": item.term,
            "description": item.description
        }
        for item in queryset
    ]

@router.get("/evaluation-items/{item_id}", response=EvaluationItemOut)
def get_evaluation_item(request, item_id: int):
    item = get_object_or_404(EvaluationItem, id=item_id)
    return {
        "id": item.id,
        "name": item.name,
        "term": item.term,
        "description": item.description
    }

@router.put("/evaluation-items/{item_id}", response=EvaluationItemOut)
def update_evaluation_item(request, item_id: int, payload: EvaluationItemIn):
    item = get_object_or_404(EvaluationItem, id=item_id)
    
    # Actualizar campos
    item.name = payload.name
    item.term = payload.term
    item.description = payload.description
    item.save()
    
    return {
        "id": item.id,
        "name": item.name,
        "term": item.term,
        "description": item.description
    }

@router.delete("/evaluation-items/{item_id}")
def delete_evaluation_item(request, item_id: int):
    item = get_object_or_404(EvaluationItem, id=item_id)
    item.delete()
    return {"success": True}

# Endpoints para RubricCategories
@router.post("/rubric-categories", response=RubricCategoryOut)
def create_rubric_category(request, payload: RubricCategoryIn):
    category_data = payload.dict()
    
    # Manejar la relación con evaluation_item si existe
    evaluation_item_id = category_data.pop('evaluation_item_id', None)
    if evaluation_item_id:
        evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
        category = RubricCategory.objects.create(**category_data, evaluation_item=evaluation_item)
    else:
        category = RubricCategory.objects.create(**category_data)
    
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "max_points": category.max_points,
        "order": category.order,
        "evaluation_item_id": category.evaluation_item.id if category.evaluation_item else None
    }

@router.get("/rubric-categories", response=List[RubricCategoryOut])
def list_rubric_categories(request, evaluation_item_id: Optional[int] = None):
    queryset = RubricCategory.objects.all()
    if evaluation_item_id:
        queryset = queryset.filter(evaluation_item_id=evaluation_item_id)
    
    return [
        {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "max_points": category.max_points,
            "order": category.order,
            "evaluation_item_id": category.evaluation_item.id if category.evaluation_item else None
        }
        for category in queryset
    ]

@router.get("/rubric-categories/{category_id}", response=RubricCategoryOut)
def get_rubric_category(request, category_id: int):
    category = get_object_or_404(RubricCategory, id=category_id)
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "max_points": category.max_points,
        "order": category.order,
        "evaluation_item_id": category.evaluation_item.id if category.evaluation_item else None
    }

@router.put("/rubric-categories/{category_id}", response=RubricCategoryOut)
def update_rubric_category(request, category_id: int, payload: RubricCategoryIn):
    category = get_object_or_404(RubricCategory, id=category_id)
    category_data = payload.dict()
    
    # Manejar la relación con evaluation_item si existe
    evaluation_item_id = category_data.pop('evaluation_item_id', None)
    if evaluation_item_id:
        evaluation_item = get_object_or_404(EvaluationItem, id=evaluation_item_id)
        category.evaluation_item = evaluation_item
    
    # Actualizar campos
    category.name = category_data.get('name', category.name)
    category.description = category_data.get('description', category.description)
    category.max_points = category_data.get('max_points', category.max_points)
    category.order = category_data.get('order', category.order)
    category.save()
    
    return {
        "id": category.id,
        "name": category.name,
        "description": category.description,
        "max_points": category.max_points,
        "order": category.order,
        "evaluation_item_id": category.evaluation_item.id if category.evaluation_item else None
    }

@router.delete("/rubric-categories/{category_id}")
def delete_rubric_category(request, category_id: int):
    category = get_object_or_404(RubricCategory, id=category_id)
    category.delete()
    return {"success": True}

# Nuevos schemas para evaluaciones y rúbricas
class RubricScoreIn(Schema):
    category_id: int
    points: float

class RubricScoreOut(Schema):
    category_id: int
    category_name: str
    points: float
    max_points: float

class EvaluationIn(Schema):
    student_id: Optional[int] = None
    student_name_search: Optional[str] = None  # Para buscar por nombre/apellido
    evaluation_item_id: Optional[int] = None
    evaluation_item_name: Optional[str] = None  # Para buscar por nombre de elemento
    score: float
    max_score: float = 10.0
    feedback: Optional[str] = None
    classroom_submission: bool = False
    rubric_scores: List[RubricScoreIn] = []

class EvaluationOut(Schema):
    id: int
    student_id: int
    student_name: str
    evaluation_item_id: int
    evaluation_item_name: str
    score: float
    max_score: float
    feedback: Optional[str]
    classroom_submission: bool
    date_evaluated: datetime
    rubric_scores: List[RubricScoreOut]

class SearchStudentIn(Schema):
    name_query: str  # Buscar por nombre o apellido
    group: Optional[str] = None

class SearchEvaluationItemIn(Schema):
    name_query: str  # Buscar por nombre
    term: Optional[str] = None

# Endpoint para buscar estudiantes por nombre o apellido
@router.post("/search-students", response=List[StudentOut])
def search_students(request, payload: SearchStudentIn):
    query = payload.name_query.strip()
    queryset = Student.objects.select_related("user")
    
    if query:
        # Buscar por nombre o apellido (asumiendo que User tiene campos first_name y last_name)
        queryset = queryset.filter(
            Q(user__name__icontains=query) |
            Q(user__email__icontains=query)
        )
    
    if payload.group:
        queryset = queryset.filter(group=payload.group)
    
    return [
        {
            "id": student.id,
            "first_name": student.user.name.split()[0] if student.user and student.user.name else "",
            "last_name": " ".join(student.user.name.split()[1:]) if student.user and student.user.name and len(student.user.name.split()) > 1 else "",
            "group": student.group,
            "pending_evaluation_id": None  # El modelo ha cambiado según las memories
        }
        for student in queryset
    ]

# Endpoint para buscar elementos de evaluación por nombre
@router.post("/search-evaluation-items", response=List[EvaluationItemOut])
def search_evaluation_items(request, payload: SearchEvaluationItemIn):
    query = payload.name_query.strip()
    queryset = EvaluationItem.objects.all()
    
    if query:
        queryset = queryset.filter(name__icontains=query)
    
    if payload.term:
        queryset = queryset.filter(term=payload.term)
    
    return [
        {
            "id": item.id,
            "name": item.name,
            "term": item.term,
            "description": item.description
        }
        for item in queryset
    ]

# Endpoint para crear o actualizar una evaluación con rúbricas
@router.post("/evaluations", response=EvaluationOut)
def create_or_update_evaluation(request, payload: EvaluationIn):
    # Primero encontrar el estudiante
    student = None
    if payload.student_id:
        student = get_object_or_404(Student, id=payload.student_id)
    elif payload.student_name_search:
        # Buscar por nombre
        query = payload.student_name_search.strip()
        students = Student.objects.filter(user__name__icontains=query).select_related("user")
        if students.count() == 1:
            student = students.first()
        elif students.count() > 1:
            raise ValueError(f"Se encontraron múltiples estudiantes con el nombre {payload.student_name_search}. Por favor especifica el student_id.")
        else:
            raise ValueError(f"No se encontró ningún estudiante con el nombre {payload.student_name_search}")
    else:
        raise ValueError("Debes proporcionar student_id o student_name_search")
    
    # Luego encontrar el elemento de evaluación
    evaluation_item = None
    if payload.evaluation_item_id:
        evaluation_item = get_object_or_404(EvaluationItem, id=payload.evaluation_item_id)
    elif payload.evaluation_item_name:
        # Buscar por nombre
        query = payload.evaluation_item_name.strip()
        eval_items = EvaluationItem.objects.filter(name__icontains=query)
        if eval_items.count() == 1:
            evaluation_item = eval_items.first()
        elif eval_items.count() > 1:
            raise ValueError(f"Se encontraron múltiples elementos de evaluación con el nombre {payload.evaluation_item_name}. Por favor especifica el evaluation_item_id.")
        else:
            raise ValueError(f"No se encontró ningún elemento de evaluación con el nombre {payload.evaluation_item_name}")
    else:
        raise ValueError("Debes proporcionar evaluation_item_id o evaluation_item_name")
    
    # Comprobar si ya existe una evaluación para este estudiante y elemento
    evaluation, created = Evaluation.objects.get_or_create(
        student=student,
        evaluation_item=evaluation_item,
        defaults={
            "score": payload.score,
            "max_score": payload.max_score,
            "feedback": payload.feedback or "",
            "classroom_submission": payload.classroom_submission,
        }
    )
    
    if not created:
        # Actualizar la evaluación existente
        evaluation.score = payload.score
        evaluation.max_score = payload.max_score
        evaluation.feedback = payload.feedback or evaluation.feedback
        evaluation.classroom_submission = payload.classroom_submission
        evaluation.save()
    
    # Procesar las puntuaciones de rúbrica
    rubric_scores_data = []
    for score_data in payload.rubric_scores:
        category = get_object_or_404(RubricCategory, id=score_data.category_id)
        
        # Verificar que la categoría pertenezca a este elemento de evaluación
        if category.evaluation_item and category.evaluation_item.id != evaluation_item.id:
            raise ValueError(f"La categoría {category.name} no pertenece al elemento de evaluación {evaluation_item.name}")
        
        # Crear o actualizar la puntuación
        rubric_score, _ = RubricScore.objects.update_or_create(
            evaluation=evaluation,
            category=category,
            defaults={"points": Decimal(str(score_data.points))}
        )
        
        rubric_scores_data.append({
            "category_id": category.id,
            "category_name": category.name,
            "points": float(rubric_score.points),
            "max_points": float(category.max_points)
        })
    
    # Si hay puntuaciones de rúbrica, recalcular la puntuación total
    if payload.rubric_scores:
        evaluation.score = float(evaluation.calculate_score())
        evaluation.save()
    
    # Eliminar de pendientes si existía
    PendingEvaluationStatus.objects.filter(student=student, evaluation_item=evaluation_item).delete()
    
    return {
        "id": evaluation.id,
        "student_id": student.id,
        "student_name": student.user.name if student.user else f"Estudiante {student.id}",
        "evaluation_item_id": evaluation_item.id,
        "evaluation_item_name": evaluation_item.name,
        "score": float(evaluation.score),
        "max_score": float(evaluation.max_score),
        "feedback": evaluation.feedback,
        "classroom_submission": evaluation.classroom_submission,
        "date_evaluated": evaluation.date_evaluated,
        "rubric_scores": rubric_scores_data
    }

# Endpoint para obtener todos los detalles de una evaluación existente
@router.get("/evaluations/{evaluation_id}", response=EvaluationOut)
def get_evaluation(request, evaluation_id: int):
    evaluation = get_object_or_404(Evaluation, id=evaluation_id)
    
    # Obtener las puntuaciones de rúbrica asociadas
    rubric_scores = RubricScore.objects.filter(evaluation=evaluation).select_related("category")
    rubric_scores_data = [
        {
            "category_id": score.category.id,
            "category_name": score.category.name,
            "points": float(score.points),
            "max_points": float(score.category.max_points)
        }
        for score in rubric_scores
    ]
    
    return {
        "id": evaluation.id,
        "student_id": evaluation.student.id,
        "student_name": evaluation.student.user.name if evaluation.student.user else f"Estudiante {evaluation.student.id}",
        "evaluation_item_id": evaluation.evaluation_item.id,
        "evaluation_item_name": evaluation.evaluation_item.name,
        "score": float(evaluation.score),
        "max_score": float(evaluation.max_score),
        "feedback": evaluation.feedback,
        "classroom_submission": evaluation.classroom_submission,
        "date_evaluated": evaluation.date_evaluated,
        "rubric_scores": rubric_scores_data
    }

# Endpoint para obtener todas las evaluaciones de un estudiante
@router.get("/students/{student_id}/evaluations", response=List[EvaluationOut])
def get_student_evaluations(request, student_id: int):
    student = get_object_or_404(Student, id=student_id)
    evaluations = Evaluation.objects.filter(student=student).select_related("evaluation_item")
    
    result = []
    for evaluation in evaluations:
        # Obtener las puntuaciones de rúbrica asociadas
        rubric_scores = RubricScore.objects.filter(evaluation=evaluation).select_related("category")
        rubric_scores_data = [
            {
                "category_id": score.category.id,
                "category_name": score.category.name,
                "points": float(score.points),
                "max_points": float(score.category.max_points)
            }
            for score in rubric_scores
        ]
        
        result.append({
            "id": evaluation.id,
            "student_id": student.id,
            "student_name": student.user.name if student.user else f"Estudiante {student.id}",
            "evaluation_item_id": evaluation.evaluation_item.id,
            "evaluation_item_name": evaluation.evaluation_item.name,
            "score": float(evaluation.score),
            "max_score": float(evaluation.max_score),
            "feedback": evaluation.feedback,
            "classroom_submission": evaluation.classroom_submission,
            "date_evaluated": evaluation.date_evaluated,
            "rubric_scores": rubric_scores_data
        })
    
    return result
