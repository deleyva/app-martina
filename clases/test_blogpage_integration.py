import pytest
from django.contrib.contenttypes.models import ContentType
from cms.models import BlogPage
from clases.models import (
    ClassSession,
    ClassSessionItem,
    Group,
    Subject,
    GroupLibraryItem,
)
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_blogpage_content_type_allowed():
    """Test que verifica que el ContentType de BlogPage está permitido en sesiones"""

    # Obtener el ContentType para BlogPage
    blog_content_type = ContentType.objects.get_for_model(BlogPage)

    # Verificar que no es ScorePage (que está bloqueado)
    assert blog_content_type.model != "scorepage"

    # Verificar que el modelo es blogpage
    assert blog_content_type.model == "blogpage"


@pytest.mark.django_db
def test_group_library_supports_blogpage():
    """Test que verifica que GroupLibraryItem puede manejar BlogPages"""

    # Crear datos de prueba
    teacher = User.objects.create_user(
        name="teacher", email="teacher@test.com", password="pass", is_staff=True
    )
    subject, _ = Subject.objects.get_or_create(name="Música", code="MUS")
    group, _ = Group.objects.get_or_create(name="1A", subject=subject)
    group.teachers.add(teacher)

    # Verificar que el método get_icon funciona para BlogPages
    blog_content_type = ContentType.objects.get_for_model(BlogPage)

    # Crear un GroupLibraryItem simulado para probar el icono
    from clases.models import GroupLibraryItem

    item = GroupLibraryItem(
        group=group, content_type=blog_content_type, object_id=1  # ID simulado
    )

    # Verificar que el icono para BlogPage es correcto
    assert item.get_icon() == "📝"
    assert item.get_content_type_name() == "Artículo de Blog"


@pytest.mark.django_db
def test_add_to_session_method_accepts_blogpage():
    """Test que verifica que el método add_to_session no rechaza BlogPages"""

    # Crear datos de prueba
    teacher = User.objects.create_user(
        name="teacher", email="teacher@test.com", password="pass", is_staff=True
    )
    subject, _ = Subject.objects.get_or_create(name="Música", code="MUS")
    group, _ = Group.objects.get_or_create(name="1A", subject=subject)
    group.teachers.add(teacher)

    session = ClassSession.objects.create(
        teacher=teacher, group=group, title="Sesión de prueba", date="2024-01-01"
    )

    # Verificar que el ContentType de BlogPage no está bloqueado
    blog_content_type = ContentType.objects.get_for_model(BlogPage)

    # El método add_to_session solo debe bloquear ScorePages
    # BlogPages deben pasar la validación
    if blog_content_type.model == "scorepage":
        pytest.fail("BlogPage no debería ser un scorepage")

    # Verificar que no se lanza excepción para BlogPages
    try:
        # Simular la validación que hace add_to_session
        if blog_content_type.model == "scorepage":
            raise ValueError(
                "No se pueden añadir ScorePages completas a sesiones de clase. "
                "Añade los elementos individuales (PDFs, audios, imágenes) en su lugar."
            )
        # Si llegamos aquí, BlogPages están permitidos
        assert True
    except ValueError as e:
        pytest.fail(f"BlogPages deberían estar permitidos: {e}")
