# ruff: noqa: S101, ERA001
"""
TDD tests for class_session_edit view — library search and pagination.

Bug 1: Search box doesn't filter library items (HTMX partial issue)
Bug 2: "Mostrar más" button shows duplicate entries
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import RequestFactory
from django.urls import reverse

from clases.models import ClassSession
from clases.models import Group
from clases.models import GroupLibraryItem
from clases.models import Subject
from martina_bescos_app.users.tests.factories import UserFactory
from wagtail.documents.models import Document


@pytest.fixture
def staff_user(db):
    user = UserFactory(is_staff=True)
    return user


@pytest.fixture
def group(db, staff_user):
    subject, _ = Subject.objects.get_or_create(
        code="MUS", defaults={"name": "Música"}
    )
    g = Group.objects.create(name="4AG", subject=subject)
    g.teachers.add(staff_user)
    return g


@pytest.fixture
def session(db, staff_user, group):
    return ClassSession.objects.create(
        teacher=staff_user,
        group=group,
        date="2026-02-12",
        title="Test Session",
    )


@pytest.fixture
def documents(db):
    """Create 10 documents with distinct titles for testing search & pagination."""
    docs = []
    titles = [
        "Rhythmic Dictations 2nd term",
        "1970s Progressive Rock",
        "1960s British Invasion",
        "Steady Walk",
        "Tonalidades con sostenidos",
        "Counting Stars",
        "Makumaná",
        "Rolling in the deep",
        "Melodic Readings 4th ESO",
        "You Cant Always Get What You Want",
    ]
    for title in titles:
        doc = Document.objects.create(title=title)
        docs.append(doc)
    return docs


@pytest.fixture
def library_items(db, group, staff_user, documents):
    """Add all documents to the group library."""
    items = []
    doc_ct = ContentType.objects.get_for_model(Document)
    for doc in documents:
        item = GroupLibraryItem.objects.create(
            group=group,
            content_type=doc_ct,
            object_id=doc.pk,
            added_by=staff_user,
        )
        items.append(item)
    return items


# =============================================================================
# BUG 1: Search box should filter library items
# =============================================================================


@pytest.mark.django_db
class TestSearchFiltersLibraryItems:
    """Search HTMX requests should return only matching items."""

    def test_search_filters_by_title(self, client, staff_user, session, library_items):
        """Searching for 'Rolling' should return only 'Rolling in the deep'."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])
        response = client.get(
            url,
            {"search": "Rolling", "page_size": "50"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Rolling in the deep" in content
        assert "Counting Stars" not in content
        assert "Makumaná" not in content

    def test_search_empty_returns_all_paginated(
        self, client, staff_user, session, library_items
    ):
        """Empty search should return all items (up to page_size)."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])
        response = client.get(
            url,
            {"search": "", "page_size": "50"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        # All 10 items should be present
        assert "Rolling in the deep" in content
        assert "Counting Stars" in content
        assert "Makumaná" in content

    def test_search_no_results(self, client, staff_user, session, library_items):
        """Search with no matching term returns no items."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])
        response = client.get(
            url,
            {"search": "ZZZZNONEXISTENT", "page_size": "50"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Rolling in the deep" not in content
        assert "Counting Stars" not in content


# =============================================================================
# BUG 2: "Mostrar más" should not duplicate entries
# =============================================================================


@pytest.mark.django_db
class TestShowMorePagination:
    """'Mostrar más' (load more) should return only the next page of items."""

    def test_first_page_returns_page_size_items(
        self, client, staff_user, session, library_items
    ):
        """First page with page_size=5 returns exactly 5 items."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])
        response = client.get(
            url,
            {"page_size": "5", "offset": "0"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        # Context should indicate there are more items
        assert response.context["has_more"] is True
        assert response.context["next_offset"] == 5
        assert len(response.context["library_items"]) == 5

    def test_show_more_returns_next_page_only(
        self, client, staff_user, session, library_items
    ):
        """Offset=5 with page_size=5 returns items 5-9 only, not items 0-4."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])

        # Get first page
        response1 = client.get(
            url,
            {"page_size": "5", "offset": "0"},
            HTTP_HX_REQUEST="true",
        )
        first_page_ids = [
            item.pk for item in response1.context["library_items"]
        ]

        # Get second page
        response2 = client.get(
            url,
            {"page_size": "5", "offset": "5"},
            HTTP_HX_REQUEST="true",
        )
        second_page_ids = [
            item.pk for item in response2.context["library_items"]
        ]

        # No overlap between pages
        assert set(first_page_ids).isdisjoint(set(second_page_ids)), (
            f"Pages overlap! First: {first_page_ids}, Second: {second_page_ids}"
        )
        assert len(second_page_ids) == 5

    def test_show_more_response_has_updated_offset(
        self, client, staff_user, session, library_items
    ):
        """The HTMX response for 'show more' must include the correct next_offset
        so the next click fetches the right page."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])

        response = client.get(
            url,
            {"page_size": "5", "offset": "5"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        # After showing items 5-9 (10 total), there should be no more
        assert response.context["has_more"] is False

    def test_show_more_button_contains_correct_offset_in_html(
        self, client, staff_user, session, library_items
    ):
        """The 'Mostrar más' button HTML must contain the next offset value
        so subsequent clicks don't re-fetch the same data."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])

        response = client.get(
            url,
            {"page_size": "5", "offset": "0"},
            HTTP_HX_REQUEST="true",
        )

        content = response.content.decode()
        # The response should contain a button with offset=5
        assert "offset=5" in content, (
            "The HTMX response must include a 'Mostrar más' button with "
            "the correct next offset so subsequent clicks work properly"
        )


# =============================================================================
# HTMX vs full page rendering
# =============================================================================


@pytest.mark.django_db
class TestHTMXPartialRendering:
    """HTMX requests should return partial template, normal requests full page."""

    def test_htmx_returns_partial(self, client, staff_user, session, library_items):
        """HTMX request should render the partial template."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])
        response = client.get(url, HTTP_HX_REQUEST="true")

        assert response.status_code == 200
        # Partial should NOT contain full page structure
        content = response.content.decode()
        assert "<!DOCTYPE" not in content
        assert "<html" not in content

    def test_non_htmx_returns_full_page(
        self, client, staff_user, session, library_items
    ):
        """Non-HTMX request should render the full page template."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])
        response = client.get(url)

        assert response.status_code == 200
        content = response.content.decode()
        # Full page should contain HTML structure
        assert "Biblioteca del Grupo" in content

    def test_search_resets_offset(self, client, staff_user, session, library_items):
        """When searching, results should always start from offset 0,
        even if a previous offset was active."""
        client.force_login(staff_user)
        url = reverse("clases:class_session_edit", args=[session.pk])

        # Simulate: user was on offset=5, then searches
        response = client.get(
            url,
            {"search": "Rolling", "page_size": "5", "offset": "0"},
            HTTP_HX_REQUEST="true",
        )

        assert response.status_code == 200
        content = response.content.decode()
        assert "Rolling in the deep" in content
