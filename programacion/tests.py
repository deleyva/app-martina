"""
Tests de programación didáctica: cobertura, planes y cierre de sesión.

Ejecutar con: pytest programacion/tests.py --no-migrations
(--no-migrations necesario en sqlite por una migración antigua de cms con SQL de Postgres)
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from wagtail.documents.models import Document
from wagtail.models import Page

from clases.models import ClassSession, ClassSessionItem, Group, Subject
from cms.models import BlogIndexPage, BlogPage
from programacion.models import ContentCoverage, CoursePlan, PlanItem
from programacion.services import (
    create_session_from_plan_item,
    get_page_elements,
    get_pending_elements,
    recompute_coverage,
)

User = get_user_model()


@pytest.fixture
def teacher(db):
    return User.objects.create_user(
        email="profe@example.com", password="x", is_staff=True
    )


@pytest.fixture
def group(db, teacher):
    subject = Subject.objects.create(name="Música")
    group = Group.objects.create(
        name="1º ESO A", subject=subject, academic_year="2025-2026"
    )
    group.teachers.add(teacher)
    return group


@pytest.fixture
def root_page(db):
    from django.conf import settings as dj_settings
    from wagtail.models import Locale

    if not Locale.objects.exists():
        Locale.objects.create(language_code=dj_settings.LANGUAGE_CODE.split("-")[0])
    return Page.objects.filter(depth=1).first() or Page.add_root(
        title="Root", slug="root"
    )


def _make_doc(name="doc.pdf"):
    from wagtail.models import Collection

    if not Collection.objects.exists():
        Collection.add_root(name="Root")
    return Document.objects.create(
        title=name, file=SimpleUploadedFile(name, b"fake-pdf-content")
    )


@pytest.fixture
def article(db, root_page):
    """BlogPage con 2 adjuntos PDF."""
    doc1, doc2 = _make_doc("a.pdf"), _make_doc("b.pdf")
    article = BlogPage(
        title="Cancion de prueba",
        slug="cancion-prueba",
        date="2026-01-01",
        intro="intro",
        attachments=json.dumps(
            [
                {"type": "pdf_score", "value": {"pdf_file": doc1.pk}},
                {"type": "pdf_score", "value": {"pdf_file": doc2.pk}},
            ]
        ),
    )
    root_page.add_child(instance=article)
    return article, doc1, doc2


@pytest.mark.django_db
class TestCoverage:
    def test_get_page_elements(self, article):
        page, doc1, doc2 = article
        elements = get_page_elements(page)
        assert len(elements) == 2
        assert {el["object_id"] for el in elements} == {doc1.pk, doc2.pk}

    def test_coverage_updates_when_session_items_added(self, article, group, teacher):
        page, doc1, doc2 = article
        session = ClassSession.objects.create(
            teacher=teacher, group=group, date="2026-01-10", title="Clase 1"
        )
        doc_ct = ContentType.objects.get_for_model(Document)
        # Señal post_save recalcula cobertura
        ClassSessionItem.objects.create(
            session=session,
            content_type=doc_ct,
            object_id=doc1.pk,
            source_page=page,
            order=0,
        )
        coverage = ContentCoverage.objects.get(
            group=group,
            content_type=ContentType.objects.get_for_model(BlogPage),
            object_id=page.pk,
        )
        assert coverage.elements_total == 2
        assert coverage.elements_seen == 1
        assert coverage.percent == 50

        pending = get_pending_elements(group, page)
        assert len(pending) == 1
        assert pending[0]["object_id"] == doc2.pk

    def test_recompute_is_retroactive(self, article, group, teacher):
        """La cobertura se calcula del historial aunque no existiera antes."""
        page, doc1, doc2 = article
        session = ClassSession.objects.create(
            teacher=teacher, group=group, date="2026-01-10", title="Clase historica"
        )
        doc_ct = ContentType.objects.get_for_model(Document)
        for i, doc in enumerate([doc1, doc2]):
            ClassSessionItem.objects.create(
                session=session,
                content_type=doc_ct,
                object_id=doc.pk,
                source_page=page,
                order=i,
            )
        ContentCoverage.objects.all().delete()
        coverage = recompute_coverage(group, page)
        assert coverage.percent == 100


@pytest.mark.django_db
class TestPlan:
    def test_plan_progress_and_next_step(self, article, group, teacher):
        page, doc1, doc2 = article
        plan = CoursePlan.objects.create(
            teacher=teacher, group=group, name="1er Trimestre"
        )
        item = PlanItem.objects.create(
            plan=plan,
            content_type=ContentType.objects.get_for_model(BlogPage),
            object_id=page.pk,
        )
        assert plan.get_progress() == 0
        assert plan.get_next_step() == item

        # Ver un elemento → 50%
        session = ClassSession.objects.create(
            teacher=teacher, group=group, date="2026-01-10", title="Clase 1"
        )
        ClassSessionItem.objects.create(
            session=session,
            content_type=ContentType.objects.get_for_model(Document),
            object_id=doc1.pk,
            source_page=page,
            order=0,
        )
        assert plan.get_progress() == 50
        assert plan.get_next_step() == item

        # Completado manual → siguiente paso None
        item.status = PlanItem.Status.DONE
        item.save()
        assert plan.get_progress() == 100
        assert plan.get_next_step() is None

    def test_book_sync_chapters(self, root_page, group, teacher):
        book = BlogIndexPage(title="Libro de flauta", slug="libro-flauta")
        root_page.add_child(instance=book)
        chapter = BlogPage(
            title="Capitulo 1", slug="cap-1", date="2026-01-01", intro="x"
        )
        book.add_child(instance=chapter)

        plan = CoursePlan.objects.create(teacher=teacher, group=group, name="Plan")
        item = PlanItem.objects.create(
            plan=plan,
            content_type=ContentType.objects.get_for_model(BlogIndexPage),
            object_id=book.pk,
        )
        created = item.sync_chapters()
        assert len(created) == 1
        assert created[0].content_object.pk == chapter.pk
        # Segunda sincronización no duplica
        assert item.sync_chapters() == []

    def test_create_session_from_plan_item(self, article, group, teacher):
        page, doc1, doc2 = article
        plan = CoursePlan.objects.create(teacher=teacher, group=group, name="Plan")
        item = PlanItem.objects.create(
            plan=plan,
            content_type=ContentType.objects.get_for_model(BlogPage),
            object_id=page.pk,
        )
        session = create_session_from_plan_item(item, teacher, "2026-01-15")
        assert session.group == group
        assert session.items.count() == 2
        assert all(i.source_page_id == page.pk for i in session.items.all())
        assert session.metadata["plan_item_id"] == item.pk


@pytest.mark.django_db
class TestSessionClose:
    def test_close_and_reopen(self, group, teacher):
        session = ClassSession.objects.create(
            teacher=teacher, group=group, date="2026-01-10", title="Clase"
        )
        assert not session.is_closed
        session.close(reflection_text="Ha ido genial")
        session.refresh_from_db()
        assert session.is_closed
        assert session.reflection == "Ha ido genial"

        first_closed_at = session.closed_at
        session.close(reflection_text="Actualizo la reflexión")
        session.refresh_from_db()
        assert session.closed_at == first_closed_at  # idempotente
        assert session.reflection == "Actualizo la reflexión"

        session.reopen()
        session.refresh_from_db()
        assert not session.is_closed
        assert session.reflection == "Actualizo la reflexión"

    def test_close_view(self, client, group, teacher):
        session = ClassSession.objects.create(
            teacher=teacher, group=group, date="2026-01-10", title="Clase"
        )
        client.force_login(teacher)
        response = client.post(
            f"/clases/sessions/{session.pk}/close/",
            {"reflection": "Reflexión vía POST"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert response.status_code == 200
        session.refresh_from_db()
        assert session.is_closed
        assert session.reflection == "Reflexión vía POST"
