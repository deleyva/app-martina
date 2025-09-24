from django.db import models
from martina_bescos_app.users.models import User

# from django.contrib.contenttypes.models import ContentType
# from django.contrib.contenttypes.fields import GenericForeignKey

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
    title = models.CharField(max_length=200)
    texts = models.ManyToManyField("Text", blank=True, related_name="music_items")
    files = models.ManyToManyField("File", blank=True, related_name="music_items")
    embeds = models.ManyToManyField("Embed", blank=True, related_name="music_items")
    tags = models.ManyToManyField(Tag, blank=True, related_name="music_items")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = MusicItemManager()

    def __str__(self):
        return f"Song: {self.title}"


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
