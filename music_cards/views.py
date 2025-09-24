from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from django.template.response import TemplateResponse
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.views.decorators.http import require_POST
import json

from .models import (
    UserStudySession,
    Tag,
    MusicItem,
    Tag,
    File,
    Text,
    Embed,
    Category,
    CategoryItem,
)
from .forms import MusicItemForm, TextForm


# Create your views here.
def counter(request):
    # devolver la hora inicial
    return render(request, "music_cards/partials/counter.html")


def start_study_session(request, study_session_id=None):
    # Obtener las etiquetas de estilo e instrumento
    style_tags = Tag.objects.filter(key="style")
    instrument_tags = Tag.objects.filter(key="instrument")

    # Obtener la última sesión de estudio no terminada
    last_study_session = UserStudySession.objects.filter(
        user=request.user, is_finished=False
    ).last()

    # Si se envía el formulario
    if request.method == "POST":
        tags_selected = request.POST.getlist("tags")
        tags = Tag.objects.filter(id__in=tags_selected)

        # Obtener o crear la sesión de estudio
        study_session, created = UserStudySession.objects.get_or_create(
            user=request.user, is_finished=False
        )
        session = study_session.start_study_session(tags=tags)

        # Redirigir a la página de la sesión de estudio
        return redirect(f"study/{session.id}")

    if (
        request.method == "GET"
        and study_session_id
        and request.headers.get("Hx-Request", False) == "True"
    ):
        study_session = UserStudySession.objects.get(id=study_session_id)
        study_session.finish_study_session()
        return HttpResponse("")

    return render(
        request,
        "music_cards/start_study_session.html",
        {
            "style_tags": style_tags,
            "instrument_tags": instrument_tags,
            "last_study_session": last_study_session,
        },
    )


def finish_study_session(request, study_session_id):
    study_session = UserStudySession.objects.get(id=study_session_id)
    study_session.finish_study_session()
    return HttpResponse("")


def study_session(request, study_session_id):
    study_session = get_object_or_404(UserStudySession, id=study_session_id)
    user_reviews = study_session.reviews.all()

    # # Paginación para UserReviews (y por lo tanto, MusicItems)
    # paginator = Paginator(user_reviews, 1) # Mostrar 1 MusicItem por página
    # page = request.GET.get('page')
    # current_review = paginator.get_page(page)
    # music_item = current_review[0].music_item if current_review else None

    # # Paginación para Files y Embeds del MusicItem actual
    # if music_item:
    #     files_and_embeds = list(music_item.files.all()) + list(music_item.embeds.all())
    #     files_and_embeds_paginator = Paginator(files_and_embeds, 1) # Mostrar 1 File o Embed por página
    #     file_page = request.GET.get('file_page')
    #     current_file_or_embed = files_and_embeds_paginator.get_page(file_page)

    #     # Si se ha mostrado el último File o Embed, mostrar el formulario para actualizar la caja
    #     show_box_update_form = file_page and files_and_embeds_paginator.num_pages == int(file_page)

    # # ...

    # # Aquí puedes manejar el envío del formulario para actualizar la caja si es necesario

    # return render(request, 'music_cards/study_session.html', {
    #     'current_review': current_review,
    #     'current_file_or_embed': current_file_or_embed,
    #     'show_box_update_form': show_box_update_form,
    #     # Otros contextos según sea necesario
    # })

    return render(
        request,
        "music_cards/study_session.html",
        {
            "texto": "hola",
            "study_session": study_session,
            "user_reviews": user_reviews,
        },
    )


def study_item(request):
    # session = UserStudySession.objects.filter(user=request.user, is_finished=False).first()
    # if not session:
    #     return redirect('study_session')
    # review = session.reviews.first()
    # if not review:
    #     session.is_finished = True
    #     session.save()
    #     return redirect('study_session')
    # if request.method == 'POST':
    #     action = request.POST.get('action', 'same')
    #     review.update_box(action)
    #     session.reviews.remove(review)
    #     return redirect('study_item')
    review = "review"
    return render(request, "music_cards/study_item.html", {"review": review})


class RhythmicReadingListView(ListView):
    model = MusicItem
    template_name = "music_cards/rhythmic_readings_list.html"
    context_object_name = "music_items"

    def get_queryset(self):
        # Filtrar MusicItems que tengan la etiqueta 'type: lectura rítmica'
        rhythmic_reading_tag = get_object_or_404(
            Tag, key="type", value="lectura rítmica"
        )
        return MusicItem.objects.filter(tags=rhythmic_reading_tag)


class FilterableMusicItemListView(ListView):
    model = MusicItem
    template_name = "music_cards/music_items_list.html"
    context_object_name = "music_items"

    def get_queryset(self):
        tags = (
            self.request.GET.dict()
        )  # Obtener todos los parámetros como un diccionario
        file_type = self.request.GET.get("file_type")
        embed_type = self.request.GET.get("embed_type")

        # Filtrar utilizando el Manager personalizado
        queryset = MusicItem.objects.filter_by_tags(
            tags=tags, file_type=file_type, embed_type=embed_type
        )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for item in context["music_items"]:
            item.pdf_file = item.files.filter(file__endswith=".pdf").first()
            item.mxml_file = item.files.filter(file__endswith=".mxl").first()
            item.text = item.texts.first()
            item.first_embed = item.embeds.first()
        return context


class MusicItemDetailView(DetailView):
    model = MusicItem
    template_name = "music_cards/music_item_detail.html"
    context_object_name = "music_item"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Obtener el archivo XML si existe
        xml_file = self.get_object().files.filter(file__endswith=".mxl").first()
        context["xml_file"] = xml_file
        return context


class CategoryListView(ListView):
    model = Category
    template_name = "music_cards/categories_list.html"
    context_object_name = "categories"


def category_detail(request, pk):
    # Obtener la categoría por su ID
    category = get_object_or_404(Category, pk=pk)

    # Obtener todos los CategoryItems asociados a esta categoría
    category_items = CategoryItem.objects.filter(category=category).order_by("order")

    return render(
        request,
        "music_cards/category_detail.html",
        {
            "category": category,
            "category_items": category_items,
        },
    )


def duplicate_text(request, pk):
    original_text = get_object_or_404(Text, pk=pk)

    if request.method == "POST":
        form = TextForm(request.POST)
        if form.is_valid():
            duplicated_text = form.save(commit=False)
            duplicated_text.pk = (
                None  # Eliminar la clave primaria para crear un nuevo objeto
            )
            duplicated_text.save()  # Guardar el nuevo objeto en la base de datos
            form.save_m2m()  # Guardar las relaciones ManyToMany
            return redirect(
                "music_cards:categories_list"
            )  # Redirige a la lista de textos o a la vista que desees

    else:
        text_form = TextForm(
            instance=original_text
        )  # Pre-rellena el formulario con los datos del original

    return render(request, "music_cards/music_text_form.html", {"text_form": text_form})


def create_text(request):
    if request.method == "POST":
        form = TextForm(request.POST)
        if form.is_valid():
            text = form.save()
            # Crear el CategoryItem
            category = form.cleaned_data["category"]
            CategoryItem.objects.create(category=category, text=text, order=0)
            return redirect(
                "music_cards:categories_list"
            )  # Redirige a alguna página de éxito
    else:
        form = TextForm()

    return render(request, "music_cards/music_text_form.html", {"text_form": form})


def text_detail(request, pk):
    text = get_object_or_404(Text, pk=pk)
    return render(
        request, "music_cards/partials/text_detail.html", {"single_text": text}
    )


@require_POST
def update_order(request):
    ids = request.POST.getlist("item")
    # Obtener la categoría
    category = get_object_or_404(Category, pk=request.POST.get("category"))

    for i, item_id in enumerate(ids, start=1):
        category_item = get_object_or_404(CategoryItem, pk=item_id)
        category_item.order = i
        category_item.save()

    # Obtener todos los CategoryItems asociados a esta categoría
    category_items = CategoryItem.objects.filter(category=category).order_by("order")

    return render(
        request,
        "music_cards/partials/category_detail.html",
        {
            "category": category,
            "category_items": category_items,
        },
    )


def delete_text(request, pk):
    text = get_object_or_404(Text, pk=pk)
    text.delete()

    return render(
        request, "music_cards/partials/categories_list_partial.html", {"texts": text}
    )
