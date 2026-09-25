"""La libreta musical que se manda a fotocopiar.

Una `Libreta` es una lista ordenada de `Elemento`s, cada uno con su número de
copias. Un elemento es exactamente una de tres cosas: un PDF del CMS (una
plantilla de `plantillas-para-escribir` o cualquier PDF del índice de
recursos), una imagen de Wagtail (del índice o subida por el propio usuario), o
un texto corto. El PDF de salida lo monta `libreta/pdf.py`; aquí vive todo lo
demás: quién puede tocar qué, el orden, y cuántas hojas salen.

**La libreta solo LEE del CMS.** Nunca modifica un documento ni una imagen
existentes; lo único que crea es la imagen que sube el usuario, y es suya.
"""

from __future__ import annotations

from io import BytesIO

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db import transaction
from django.http import Http404
from pypdf import PdfReader


class Libreta(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="libretas",
    )
    titulo = models.CharField(max_length=120, default="Libreta de música")
    subtitulo = models.CharField(
        max_length=120,
        blank=True,
        help_text="El curso, por ejemplo «4º ESO».",
    )
    portada = models.BooleanField(default=True)
    indice = models.BooleanField(default=True)
    primera_pagina = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Número que lleva la primera página del PDF, sea portada u hoja.",
    )
    hoja_nueva_por_seccion = models.BooleanField(
        default=True,
        help_text=(
            "A doble cara, cada elemento empieza en hoja nueva "
            "(se rellena con una página en blanco)."
        ),
    )
    creada = models.DateTimeField(auto_now_add=True)
    actualizada = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-actualizada"]

    def __str__(self):
        return self.titulo

    @classmethod
    def del_usuario(cls, user, pk) -> Libreta:
        """La libreta, si es de este usuario. Si no, 404.

        404 y no 403 a propósito: un 403 confirma que la libreta existe.
        """
        libreta = cls.objects.filter(pk=pk).first()
        if libreta is None or (libreta.user_id != user.pk and not user.is_staff):
            msg = "No existe esa libreta."
            raise Http404(msg)
        return libreta

    # --- Elementos ---------------------------------------------------------

    def elementos_ordenados(self):
        return self.elementos.select_related("documento", "imagen").order_by(
            "orden",
            "pk",
        )

    def total_hojas(self) -> int:
        return sum(e.paginas() for e in self.elementos_ordenados())

    @transaction.atomic
    def insertar(self, elemento: Elemento, posicion: str = "final") -> Elemento:
        """Coloca un elemento nuevo: `final`, `inicio` o `tras:<pk>`.

        Si el pk de `tras:` no es de esta libreta, va al final: es la opción
        que menos sorprende cuando el selector se ha quedado viejo.
        """
        elementos = list(self.elementos_ordenados())
        indice = len(elementos)
        if posicion == "inicio":
            indice = 0
        elif posicion.startswith("tras:"):
            try:
                pk = int(posicion.split(":", 1)[1])
            except ValueError:
                pk = None
            for i, e in enumerate(elementos):
                if e.pk == pk:
                    indice = i + 1
                    break
        elemento.libreta = self
        elemento.full_clean()
        elemento.save()
        elementos.insert(indice, elemento)
        self.renumerar(elementos)
        return elemento

    def renumerar(self, elementos=None):
        elementos = (
            elementos if elementos is not None else list(self.elementos_ordenados())
        )
        for i, e in enumerate(elementos, start=1):
            if e.orden != i:
                Elemento.objects.filter(pk=e.pk).update(orden=i)
                e.orden = i

    # --- Salida ------------------------------------------------------------

    def pdf(self) -> bytes:
        from . import pdf

        return pdf.construir(self)

    def pedido(self) -> bytes:
        from . import pdf

        return pdf.pedido(self)

    def nombre_de_fichero(self) -> str:
        from django.utils.text import slugify

        base = slugify(f"{self.titulo} {self.subtitulo}".strip()) or "libreta"
        return f"{base}.pdf"


class Elemento(models.Model):
    """Una sección de la libreta: qué se fotocopia y cuántas veces."""

    PDF, IMAGEN, TEXTO, PLANTILLA = "pdf", "imagen", "texto", "plantilla"

    libreta = models.ForeignKey(
        Libreta,
        on_delete=models.CASCADE,
        related_name="elementos",
    )
    orden = models.PositiveIntegerField(default=0)
    titulo = models.CharField(max_length=120)
    copias = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    documento = models.ForeignKey(
        "wagtaildocs.Document",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="+",
    )
    texto = models.TextField(blank=True)
    # Clave de una hoja A4 generada en código (`libreta/plantillas.py`).
    plantilla = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["orden", "pk"]

    def __str__(self):
        return f"{self.titulo} ×{self.copias}"  # noqa: RUF001

    def clean(self):
        from . import plantillas

        contenidos = [
            bool(self.documento_id),
            bool(self.imagen_id),
            bool(self.texto.strip()),
            bool(self.plantilla),
        ]
        if sum(contenidos) != 1:
            msg = "Un elemento es una sola cosa: PDF, imagen, texto o plantilla."
            raise ValidationError(msg)
        if self.documento_id and not self.documento.file.name.lower().endswith(".pdf"):
            msg = "Solo se pueden fotocopiar documentos PDF."
            raise ValidationError(msg)
        if self.plantilla and self.plantilla not in plantillas.HOJAS:
            msg = "No existe esa plantilla."
            raise ValidationError(msg)

    @property
    def tipo(self) -> str:
        if self.documento_id:
            return self.PDF
        if self.imagen_id:
            return self.IMAGEN
        if self.plantilla:
            return self.PLANTILLA
        return self.TEXTO

    @property
    def icono(self) -> str:
        return {
            self.PDF: "📄",
            self.IMAGEN: "🖼️",
            self.TEXTO: "📝",
            self.PLANTILLA: "🎼",
        }[self.tipo]

    def paginas_por_copia(self) -> int:
        """Páginas que ocupa una copia. Un PDF, las suyas; imagen o texto, una."""
        if self.tipo != self.PDF:
            return 1
        if not hasattr(self, "_paginas_por_copia"):
            with self.documento.file.open("rb") as fichero:
                self._paginas_por_copia = len(PdfReader(BytesIO(fichero.read())).pages)
        return self._paginas_por_copia

    def paginas(self) -> int:
        return self.copias * self.paginas_por_copia()

    @classmethod
    def desde_plantilla(cls, clave: str, titulo: str | None = None) -> Elemento:
        from . import plantillas

        if clave not in plantillas.HOJAS:
            msg = "No existe esa plantilla."
            raise ValidationError(msg)
        return cls(titulo=(titulo or plantillas.titulo(clave))[:120], plantilla=clave)

    @classmethod
    def desde_medio(cls, objeto, titulo: str | None = None) -> Elemento:
        """Un elemento a partir de un `Document` o una `Image` de Wagtail."""
        titulo = (titulo or getattr(objeto, "title", "") or str(objeto))[:120]
        nombre = objeto.__class__.__name__.lower()
        if nombre == "document":
            return cls(titulo=titulo, documento=objeto)
        if nombre == "image":
            return cls(titulo=titulo, imagen=objeto)
        msg = "Solo se pueden añadir PDF e imágenes."
        raise ValidationError(msg)

    @transaction.atomic
    def mover(self, direccion: str) -> None:
        """Intercambia el orden con el vecino. En los extremos no hace nada."""
        elementos = list(self.libreta.elementos_ordenados())
        i = next((n for n, e in enumerate(elementos) if e.pk == self.pk), None)
        if i is None:
            return
        j = i - 1 if direccion == "arriba" else i + 1
        if j < 0 or j >= len(elementos):
            return
        elementos[i], elementos[j] = elementos[j], elementos[i]
        self.libreta.renumerar(elementos)

    @transaction.atomic
    def borrar(self) -> None:
        libreta = self.libreta
        self.delete()
        libreta.renumerar()
