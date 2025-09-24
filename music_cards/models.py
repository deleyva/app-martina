from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from martina_bescos_app.users.models import User

# Create your models here.


class Author(models.Model):
    name = models.CharField(max_length=200)
    surname = models.CharField(max_length=200, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} {self.surname}"


class Tag(models.Model):
    key = models.CharField(max_length=200)
    value = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return f"{self.key} - {self.value}"


class MusicItemManager(models.Manager):
    def filter_by_tags(self, tags=None, file_type=None, embed_type=None, text=None):
        queryset = self.get_queryset()

        # Filtrado por tags clave-valor
        if tags:
            for key, value in tags.items():
                queryset = queryset.filter(tags__key=key, tags__value=value).distinct()

        # Filtrado por tipo de archivo
        if file_type:
            queryset = queryset.filter(files__file__endswith=file_type).distinct()

        # Filtrado por tipo de embed
        if embed_type:
            queryset = queryset.filter(embeds__url__icontains=embed_type).distinct()

        # Filtrado por tipo de embed
        if text:
            queryset = queryset.filter(embeds__url__icontains=text).distinct()

        return queryset


class Category(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, null=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="subcategories",
    )
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["parent__id", "order"]

    def get_full_category_name(self):
        """
        Retorna el nombre completo de la categoría incluyendo la jerarquía de padres.
        """
        names = [self.name]
        parent = self.parent
        while parent:
            names.append(parent.name)
            parent = parent.parent
        return " > ".join(reversed(names))

    def __str__(self):
        return self.get_full_category_name()

    def get_items(self):
        # Aquí puedes ordenar todos los elementos asociados a la categoría
        items = (
            list(self.texts.all())
            + list(self.files.all())
            + list(self.embeds.all())
            + list(self.music_items.all())
        )
        items.sort(key=lambda x: x.categoryitem_set.get(category=self).order)
        return items


class MusicItem(models.Model):
    VISIBILITY_CHOICES = [
        ('private', 'Privado'),
        ('shared', 'Compartido con profesores'),
        ('public', 'Público'),
        ('course_only', 'Solo para mi curso'),
    ]
    
    title = models.CharField(max_length=200)
    texts = models.ManyToManyField("Text", blank=True, related_name="music_items")
    files = models.ManyToManyField("File", blank=True, related_name="music_items")
    embeds = models.ManyToManyField("Embed", blank=True, related_name="music_items")
    tags = models.ManyToManyField(Tag, blank=True, related_name="music_items")
    
    # Nuevos campos para compartir y colaboración
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_music_items', null=True, blank=True)
    shared_with = models.ManyToManyField(User, blank=True, related_name='shared_music_items')
    
    # Metadatos para plantillas y reutilización
    is_template = models.BooleanField(default=False, help_text="Marca como plantilla reutilizable")
    original_item = models.ForeignKey('self', null=True, blank=True, on_delete=models.SET_NULL, 
                                    help_text="Referencia al item original si es una copia")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MusicItemManager()

    class Meta:
        permissions = [
            ('can_share_content', 'Can share content with other teachers'),
            ('can_use_shared_content', 'Can use shared content'),
            ('can_create_templates', 'Can create content templates'),
        ]

    def __str__(self):
        return f"Song: {self.title}"
    
    def can_be_viewed_by(self, user):
        """Verifica si un usuario puede ver este item"""
        if self.visibility == 'public':
            return True
        if self.created_by == user:
            return True
        if self.visibility == 'shared' and user in self.shared_with.all():
            return True
        # TODO: Implementar lógica para 'course_only' cuando tengamos el modelo Course
        return False
    
    def duplicate_for_user(self, user):
        """Crea una copia del item para otro usuario"""
        new_item = MusicItem.objects.create(
            title=f"{self.title} (copia)",
            visibility='private',
            created_by=user,
            is_template=False,
            original_item=self
        )
        
        # Copiar relaciones ManyToMany
        new_item.texts.set(self.texts.all())
        new_item.files.set(self.files.all())
        new_item.embeds.set(self.embeds.all())
        new_item.tags.set(self.tags.all())
        
        return new_item


class Embed(models.Model):
    name = models.CharField(max_length=300)
    url = models.CharField(max_length=300)
    tags = models.ManyToManyField(Tag, blank=True, related_name="embeds")
    copyrighted = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        music_item_title = (
            self.music_item.title if self.music_item else "No music score"
        )
        return f"Embed: {self.name} - Music Item: {music_item_title}"


class File(models.Model):
    name = models.CharField(max_length=300)
    file = models.FileField(upload_to="files/")
    tags = models.ManyToManyField(Tag, blank=True, related_name="files")
    copyrighted = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"File: {self.name}"


class Text(models.Model):
    name = models.CharField(max_length=300)
    content = models.TextField()
    tags = models.ManyToManyField(Tag, blank=True, related_name="texts")
    copyrighted = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Text: {self.name}{self.id}"


class CategoryItem(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="category_items"
    )
    text = models.ForeignKey(Text, on_delete=models.CASCADE, null=True, blank=True)
    file = models.ForeignKey(File, on_delete=models.CASCADE, null=True, blank=True)
    embed = models.ForeignKey(Embed, on_delete=models.CASCADE, null=True, blank=True)
    music_item = models.ForeignKey(
        MusicItem, on_delete=models.CASCADE, null=True, blank=True
    )
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.content_object.name if self.content_object else "N/A"

    @property
    def content_object(self):
        if self.text:
            return self.text
        if self.file:
            return self.file
        if self.embed:
            return self.embed
        if self.music_item:
            return self.music_item
        return None


######### Comienzan los modelos relativos al estudio #########


class UserReview(models.Model):
    # I want a table that relates a user to a song or lick
    # and has a field for each box
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    music_item = models.ForeignKey(
        MusicItem, on_delete=models.CASCADE, related_name="user_review"
    )
    # boxes
    box = models.IntegerField(
        choices=[
            (1, "Iniciando"),
            (2, "Analizando"),
            (3, "Practicando"),
            (4, "Revisando"),
            (5, "Dominado"),
        ]
    )
    n_times_reiewed = models.IntegerField(default=0)
    last_reviewed = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"User: {self.user} - Music Item: {self.music_item} - Box: {self.box} - Times Reviewed: {self.n_times_reiewed}"

    def update_box(self, action):
        """
        Actualiza el box de la review basándose en la acción dada.

        Parámetros:
        action (str): Puede ser 'up', 'down' o 'same' para subir, bajar o mantener el mismo box, respectivamente.
        """

        if action == "up" and self.box < 5:
            self.box += 1
        elif action == "down" and self.box > 1:
            self.box -= 1
        elif action == "same":
            pass  # No se realiza ninguna acción si se elige mantener el mismo box
        else:
            raise ValueError("La acción debe ser 'up', 'down' o 'same'.")

        self.save()


class UserStudySession(models.Model):
    """Un modelo que agrupa las UserReviews para mostrarlas en una sesión de estudio, que permita filtrar por
    etiquetas, ordenar por etiquetas, box y última vez que se revisaron.

    También debe tener un par de métodos que permitan guardar la sesión como "en progreso" o "terminada"
    y que permita acceder a la siguiente UserReview de la sesión."""

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reviews = models.ManyToManyField(
        UserReview, blank=True, related_name="study_sessions"
    )
    is_finished = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def start_study_session(self, tags=None):
        """Crea una sesión de estudio para el usuario dado, con las UserReviews"""

        def order_reviews_by_tags(reviews, tag_order=None):
            if tag_order is None:
                tag_order = [
                    "toque de oído",
                    "lectura a primera vista",
                    "técnica",
                    "literatura",
                    "improvisación",
                ]

            # Primero, recogemos las reviews que coinciden con las etiquetas
            matching_reviews = []
            for tag in tag_order:
                tagged_reviews = reviews.filter(music_item__tags__key=tag).distinct()
                matching_reviews.extend(tagged_reviews)

            # Luego, obtenemos las reviews cuyos MusicItems no tienen ninguna de las etiquetas especificadas
            non_matching_reviews = reviews.exclude(
                id__in=[review.id for review in matching_reviews]
            ).distinct()

            # Combinamos ambas listas, manteniendo primero las que coinciden
            ordered_reviews = list(matching_reviews) + list(non_matching_reviews)
            return ordered_reviews

        def filter_by_tags_provided(reviews, tags):
            # Filtra las UserReviews por las etiquetas proporcionadas
            if len(tags) > 0:
                filtered_reviews = reviews.filter(
                    music_item__tags__in=tags,
                )
                return filtered_reviews
            else:
                return reviews

        # Tratamos de añadir algo nuevo en cada sesión de estudio
        new_music_items = MusicItem.objects.exclude(
            user_review__user=self.user,
        )
        if len(new_music_items) > 0:
            for music_item in new_music_items[:5]:
                UserReview.objects.create(
                    user=self.user,
                    music_item=music_item,
                    box=1,
                )

        # Filtramos las UserReviews por el usuario
        filtered_reviews = UserReview.objects.filter(user=self.user)

        if tags:
            filtered_reviews = filter_by_tags_provided(filtered_reviews, tags)

        # Ordenamos las UserReviews por etiquetas
        ordered_reviews = order_reviews_by_tags(filtered_reviews)

        # Asignamos las UserReviews a la sesión de estudio
        self.reviews.set(ordered_reviews)

        # Marcamos la sesión de estudio como en progreso
        self.is_finished = False
        self.save()
        return self

    def finish_study_session(self):
        self.is_finished = True
        self.save()

    def __str__(self):
        return f"User: {self.user.name} {self.user.surname} - Study Session: {self.created_at} - {self.updated_at}"


######### Modelos para bibliotecas de contenido compartido #########


class ContentLibrary(models.Model):
    """Biblioteca de contenido compartido entre profesores"""
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_libraries')
    collaborators = models.ManyToManyField(User, through='LibraryCollaboration', related_name='collaborated_libraries')
    items = models.ManyToManyField(MusicItem, through='LibraryItem', related_name='libraries')
    
    is_public = models.BooleanField(default=False)
    tags = models.ManyToManyField(Tag, blank=True, related_name='libraries')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Content Libraries"
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Library: {self.name} (by {self.owner})"
    
    def can_be_accessed_by(self, user):
        """Verifica si un usuario puede acceder a esta biblioteca"""
        if self.is_public:
            return True
        if self.owner == user:
            return True
        if self.collaborators.filter(id=user.id).exists():
            return True
        return False


class LibraryCollaboration(models.Model):
    """Colaboración en biblioteca de contenido"""
    PERMISSION_LEVELS = [
        ('view', 'Solo visualización'),
        ('contribute', 'Puede añadir contenido'),
        ('edit', 'Puede editar contenido'),
        ('admin', 'Administrador completo'),
    ]
    
    library = models.ForeignKey(ContentLibrary, on_delete=models.CASCADE)
    collaborator = models.ForeignKey(User, on_delete=models.CASCADE)
    permission_level = models.CharField(max_length=20, choices=PERMISSION_LEVELS, default='view')
    joined_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['library', 'collaborator']
    
    def __str__(self):
        return f"{self.collaborator} - {self.library.name} ({self.permission_level})"


class LibraryItem(models.Model):
    """Relación entre biblioteca y items de contenido"""
    library = models.ForeignKey(ContentLibrary, on_delete=models.CASCADE)
    music_item = models.ForeignKey(MusicItem, on_delete=models.CASCADE)
    added_by = models.ForeignKey(User, on_delete=models.CASCADE)
    order = models.PositiveIntegerField(default=0)
    notes = models.TextField(blank=True, help_text="Notas sobre este item en la biblioteca")
    
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['order', 'added_at']
        unique_together = ['library', 'music_item']
    
    def __str__(self):
        return f"{self.music_item.title} in {self.library.name}"
