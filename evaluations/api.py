from ninja import Router, Schema
from typing import List, Optional
from django.shortcuts import get_object_or_404
from django.http import HttpRequest

from .models import Student, EvaluationItem, RubricCategory
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
