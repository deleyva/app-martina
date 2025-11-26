from datetime import date
from typing import List, Optional

from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from wagtail.images import get_image_model

from api_keys.auth import DatabaseApiKey
from .models import (
    MusicCategory,
    MusicLibraryIndexPage,
    MusicTag,
    TestPage,
)


router = Router(tags=["CMS Tests"], auth=DatabaseApiKey())
ImageModel = get_image_model()


class AnswerOptionIn(Schema):
    text: str
    is_correct: bool = False
    image_id: Optional[int] = None


class QuestionIn(Schema):
    prompt: str
    description: Optional[str] = None
    explanation: Optional[str] = None
    illustration_image_id: Optional[int] = None
    options: List[AnswerOptionIn]


class TestPageIn(Schema):
    title: str
    intro: Optional[str] = None
    date: Optional[date] = None
    featured_image_id: Optional[int] = None
    parent_page_id: Optional[int] = None
    category_ids: List[int] = []
    tag_ids: List[int] = []
    questions: List[QuestionIn]


class TestPageOut(Schema):
    id: int
    title: str
    url: str
    question_count: int


def _get_image(image_id: Optional[int]):
    if image_id is None:
        return None
    try:
        return ImageModel.objects.get(id=image_id)
    except ImageModel.DoesNotExist as exc:
        raise HttpError(400, f"La imagen con ID {image_id} no existe.") from exc


def _get_parent_page(parent_page_id: Optional[int]) -> MusicLibraryIndexPage:
    if parent_page_id is not None:
        try:
            return MusicLibraryIndexPage.objects.get(id=parent_page_id)
        except MusicLibraryIndexPage.DoesNotExist as exc:
            raise HttpError(400, "La página padre indicada no existe.") from exc
    parent = MusicLibraryIndexPage.objects.first()
    if not parent:
        raise HttpError(
            400, "No existe ninguna MusicLibraryIndexPage para anexar el test."
        )
    return parent


def _build_questions_payload(questions: List[QuestionIn]):
    stream_value = []
    for question in questions:
        if len(question.options) != 4:
            raise HttpError(400, "Cada pregunta debe tener exactamente 4 opciones.")
        correct_count = sum(1 for option in question.options if option.is_correct)
        if correct_count != 1:
            raise HttpError(
                400,
                "Cada pregunta debe tener exactamente una opción marcada como correcta.",
            )
        illustration = _get_image(question.illustration_image_id)
        option_values = []
        for option in question.options:
            option_values.append(
                {
                    "text": option.text,
                    "is_correct": option.is_correct,
                    "image": _get_image(option.image_id),
                }
            )
        stream_value.append(
            (
                "question",
                {
                    "prompt": question.prompt,
                    "description": question.description,
                    "illustration": illustration,
                    "options": option_values,
                    "explanation": question.explanation,
                },
            )
        )
    return stream_value


@router.post("/tests", response=TestPageOut)
def create_test_page(request, payload: TestPageIn):
    if not payload.questions:
        raise HttpError(400, "Debes enviar al menos una pregunta.")

    parent_page = _get_parent_page(payload.parent_page_id)
    featured_image = _get_image(payload.featured_image_id)
    questions_value = _build_questions_payload(payload.questions)

    with transaction.atomic():
        page = TestPage(
            title=payload.title,
            intro=payload.intro or "",
            date=payload.date or timezone.now().date(),
        )
        if featured_image:
            page.featured_image = featured_image
        page.questions = questions_value
        parent_page.add_child(instance=page)

        if payload.category_ids:
            categories = list(
                MusicCategory.objects.filter(id__in=payload.category_ids).distinct()
            )
            if len(categories) != len(set(payload.category_ids)):
                raise HttpError(400, "Alguna categoría proporcionada no existe.")
            page.categories.set(categories)
        if payload.tag_ids:
            tags = list(MusicTag.objects.filter(id__in=payload.tag_ids).distinct())
            if len(tags) != len(set(payload.tag_ids)):
                raise HttpError(400, "Alguna etiqueta proporcionada no existe.")
            page.tags.set(tags)

        page.save_revision().publish()

    return TestPageOut(
        id=page.id,
        title=page.title,
        url=page.get_url(request),
        question_count=len(payload.questions),
    )
