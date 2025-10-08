from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView
import json

from .models import (
    UserStudySession,
    UserReview,
    Tag,
    MusicItem,
    Text,
    File,
    Embed,
    Category,
    CategoryItem,
)
from .forms import TextForm, MusicItemForm



# Create your views here.
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

        # Redirigir a la nueva página de la sesión de estudio
        return redirect(f"study-new/{session.id}")

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
    
    # Redirect to the main music cards page after finishing the session
    return redirect('music_cards:home')


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


@require_POST
def rate_item(request):
    """
    Vista para calificar un elemento de estudio con el sistema Leitner.
    Acepta tanto form data como JSON para compatibilidad.
    """
    try:
        # Try form data first (from current rateItem function)
        if request.POST:
            review_id = request.POST.get('review_id')
            rating = request.POST.get('rating')
        else:
            # Fallback to JSON
            data = json.loads(request.body)
            review_id = data.get('review_id')
            rating = data.get('rating')
        
        if not review_id or not rating:
            return JsonResponse({'success': False, 'error': 'Faltan parámetros'})
        
        # Convert to int
        try:
            review_id = int(review_id)
            rating = int(rating)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Parámetros inválidos'})
        
        if rating not in [1, 2, 3, 4, 5]:
            return JsonResponse({'success': False, 'error': 'Calificación inválida (1-5)'})
        
        # Obtener la review y verificar que pertenece al usuario actual
        review = get_object_or_404(UserReview, id=review_id, user=request.user)
        
        # Map 1-5 stars to 1-4 boxes (1-2 stars = box 1, 3 = box 2, 4 = box 3, 5 = box 4)
        box_mapping = {1: 1, 2: 1, 3: 2, 4: 3, 5: 4}
        box_rating = box_mapping[rating]
        
        # Actualizar la caja usando el nuevo método
        review.update_box(box_rating)
        
        return JsonResponse({
            'success': True, 
            'new_box': review.box,
            'rating': rating,
            'times_reviewed': review.n_times_reiewed
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


def study_session_new(request, study_session_id):
    """
    Nueva vista de sesión de estudio con interfaz mejorada y full-screen.
    """
    study_session = get_object_or_404(UserStudySession, id=study_session_id, user=request.user)
    user_reviews = study_session.reviews.all()

    return render(
        request,
        "music_cards/study_session_new.html",
        {
            "study_session": study_session,
            "user_reviews": user_reviews,
        },
    )


def study_session_fullscreen(request, study_session_id):
    """
    Vista de sesión de estudio en pantalla completa estilo forScore.
    Muestra cada elemento (texto, PDF, audio, video) individualmente en pantalla completa.
    """
    study_session = get_object_or_404(UserStudySession, id=study_session_id, user=request.user)
    user_reviews = list(study_session.reviews.all())
    
    if not user_reviews:
        # Redirect back if no reviews
        return redirect('music_cards:study_session_new', study_session_id=study_session_id)
    
    # Get current index from session or default to 0
    current_index = int(request.session.get(f'fullscreen_index_{study_session_id}', 0))
    current_index = max(0, min(current_index, len(user_reviews) - 1))
    
    # Get current review
    current_review = user_reviews[current_index]
    
    # Calculate progress
    progress_percentage = ((current_index + 1) / len(user_reviews)) * 100

    return render(
        request,
        "music_cards/study_session_fullscreen_static.html",
        {
            "study_session": study_session,
            "user_reviews": user_reviews,
            "current_review": current_review,
            "current_index": current_index,
            "total_items": len(user_reviews),
            "progress_percentage": progress_percentage,
        },
    )


def fullscreen_navigate(request, study_session_id):
    """
    HTMX endpoint para navegación en pantalla completa.
    """
    if request.method != 'POST':
        return HttpResponse(status=405)  # Method not allowed
        
    study_session = get_object_or_404(UserStudySession, id=study_session_id, user=request.user)
    user_reviews = list(study_session.reviews.all())
    
    direction = request.POST.get('direction', 'next')
    current_index = int(request.POST.get('current_index', 0))
    
    if direction == 'next' and current_index < len(user_reviews) - 1:
        current_index += 1
    elif direction == 'prev' and current_index > 0:
        current_index -= 1
    
    # Save current index in session
    request.session[f'fullscreen_index_{study_session_id}'] = current_index
    
    # Get current review
    current_review = user_reviews[current_index] if current_index < len(user_reviews) else None
    
    # Return the full page content for navigation
    return render(
        request,
        "music_cards/study_session_fullscreen_simple.html",
        {
            "study_session": study_session,
            "user_reviews": user_reviews,
            "current_review": current_review,
            "current_index": current_index,
            "total_items": len(user_reviews),
            "progress_percentage": ((current_index + 1) / len(user_reviews)) * 100,
        },
    )


# CRUD Views for MusicItem

def music_item_create(request):
    """
    Vista para crear un nuevo MusicItem con contenido asociado.
    """
    if request.method == 'POST':
        form = MusicItemForm(request.POST)
        if form.is_valid():
            music_item = form.save(commit=False)
            music_item.created_by = request.user
            music_item.save()
            
            # Lista para almacenar todas las etiquetas del MusicItem (inicializar antes de procesar contenido)
            music_item_tags = []
            
            # Procesar textos
            text_count = 0
            while f'text_name_{text_count}' in request.POST:
                name = request.POST.get(f'text_name_{text_count}')
                content = request.POST.get(f'text_content_{text_count}')
                copyrighted = f'text_copyrighted_{text_count}' in request.POST
                
                if name and content:
                    text = Text.objects.create(
                        name=name,
                        content=content,
                        copyrighted=copyrighted
                    )
                    music_item.texts.add(text)
                    # Heredar etiquetas del MusicItem
                    for tag in music_item_tags:
                        text.tags.add(tag)
                text_count += 1
            
            # Procesar archivos
            file_count = 0
            while f'file_name_{file_count}' in request.POST:
                name = request.POST.get(f'file_name_{file_count}')
                file_upload = request.FILES.get(f'file_upload_{file_count}')
                copyrighted = f'file_copyrighted_{file_count}' in request.POST
                
                if name and file_upload:
                    file_obj = File.objects.create(
                        name=name,
                        file=file_upload,
                        copyrighted=copyrighted
                    )
                    music_item.files.add(file_obj)
                    # Heredar etiquetas del MusicItem
                    for tag in music_item_tags:
                        file_obj.tags.add(tag)
                file_count += 1
            
            # Procesar embeds
            embed_count = 0
            while f'embed_name_{embed_count}' in request.POST:
                name = request.POST.get(f'embed_name_{embed_count}')
                url = request.POST.get(f'embed_url_{embed_count}')
                copyrighted = f'embed_copyrighted_{embed_count}' in request.POST
                
                if name and url:
                    embed = Embed.objects.create(
                        name=name,
                        url=url,
                        copyrighted=copyrighted
                    )
                    music_item.embeds.add(embed)
                    # Heredar etiquetas del MusicItem
                    for tag in music_item_tags:
                        embed.tags.add(tag)
                embed_count += 1
            
            # Procesar tags existentes
            style_tag_id = request.POST.get('style_tag')
            instrument_tag_id = request.POST.get('instrument_tag')
            difficulty = request.POST.get('difficulty_tag')
            
            if style_tag_id:
                music_item.tags.add(style_tag_id)
                music_item_tags.append(Tag.objects.get(id=style_tag_id))
            if instrument_tag_id:
                music_item.tags.add(instrument_tag_id)
                music_item_tags.append(Tag.objects.get(id=instrument_tag_id))
            if difficulty:
                # Crear o obtener tag de dificultad
                difficulty_tag, created = Tag.objects.get_or_create(
                    key='difficulty',
                    value=difficulty
                )
                music_item.tags.add(difficulty_tag)
                music_item_tags.append(difficulty_tag)
            
            # Procesar nuevas etiquetas
            new_style = request.POST.get('new_style_value')
            new_instrument = request.POST.get('new_instrument_value')
            new_difficulty = request.POST.get('new_difficulty_value')
            
            if new_style:
                style_tag, created = Tag.objects.get_or_create(
                    key='style',
                    value=new_style
                )
                music_item.tags.add(style_tag)
                music_item_tags.append(style_tag)
                
            if new_instrument:
                instrument_tag, created = Tag.objects.get_or_create(
                    key='instrument',
                    value=new_instrument
                )
                music_item.tags.add(instrument_tag)
                music_item_tags.append(instrument_tag)
                
            if new_difficulty:
                difficulty_tag, created = Tag.objects.get_or_create(
                    key='difficulty',
                    value=new_difficulty
                )
                music_item.tags.add(difficulty_tag)
                music_item_tags.append(difficulty_tag)
            
            # Procesar etiquetas personalizadas
            custom_tag_count = 0
            while f'custom_tag_key_{custom_tag_count}' in request.POST:
                key = request.POST.get(f'custom_tag_key_{custom_tag_count}')
                value = request.POST.get(f'custom_tag_value_{custom_tag_count}')
                
                if key and value:
                    custom_tag, created = Tag.objects.get_or_create(
                        key=key,
                        value=value
                    )
                    music_item.tags.add(custom_tag)
                    music_item_tags.append(custom_tag)
                custom_tag_count += 1
            
            return redirect('music_cards:music_item_detail', pk=music_item.pk)
    else:
        form = MusicItemForm()
    
    # Obtener tags para el formulario
    style_tags = Tag.objects.filter(key='style')
    instrument_tags = Tag.objects.filter(key='instrument')
    
    return render(request, 'music_cards/music_item_form.html', {
        'form': form,
        'style_tags': style_tags,
        'instrument_tags': instrument_tags,
    })


def music_item_edit(request, pk):
    """
    Vista para editar un MusicItem existente.
    """
    music_item = get_object_or_404(MusicItem, pk=pk)
    
    # Verificar permisos
    if music_item.created_by != request.user and not request.user.is_staff:
        return redirect('music_cards:music_items_list')
    
    if request.method == 'POST':
        form = MusicItemForm(request.POST, instance=music_item)
        if form.is_valid():
            music_item = form.save()
            
            # Limpiar contenido existente si se especifica
            if 'clear_content' in request.POST:
                music_item.texts.clear()
                music_item.files.clear()
                music_item.embeds.clear()
            
            # En edición: actualizar textos existentes o crear nuevos
            # Primero, obtener textos existentes
            existing_texts = list(music_item.texts.all())
            
            # Procesar textos del formulario
            text_count = 0
            processed_text_ids = []
            
            while f'text_name_{text_count}' in request.POST:
                name = request.POST.get(f'text_name_{text_count}')
                content = request.POST.get(f'text_content_{text_count}')
                copyrighted = f'text_copyrighted_{text_count}' in request.POST
                
                if name and content:
                    # Si hay un texto existente en esta posición, actualizarlo
                    if text_count < len(existing_texts):
                        existing_text = existing_texts[text_count]
                        existing_text.name = name
                        existing_text.content = content
                        existing_text.copyrighted = copyrighted
                        existing_text.save()
                        processed_text_ids.append(existing_text.id)
                    else:
                        # Crear nuevo texto si no existe
                        new_text = Text.objects.create(
                            name=name,
                            content=content,
                            copyrighted=copyrighted
                        )
                        music_item.texts.add(new_text)
                        processed_text_ids.append(new_text.id)
                
                text_count += 1
            
            # Eliminar textos que ya no están en el formulario
            for existing_text in existing_texts:
                if existing_text.id not in processed_text_ids:
                    music_item.texts.remove(existing_text)
                    existing_text.delete()
            
            return redirect('music_cards:music_item_detail', pk=music_item.pk)
    else:
        form = MusicItemForm(instance=music_item)
    
    # Obtener tags para el formulario
    style_tags = Tag.objects.filter(key='style')
    instrument_tags = Tag.objects.filter(key='instrument')
    
    return render(request, 'music_cards/music_item_form.html', {
        'form': form,
        'music_item': music_item,
        'style_tags': style_tags,
        'instrument_tags': instrument_tags,
    })


def music_item_delete(request, pk):
    """
    Vista para eliminar un MusicItem.
    """
    music_item = get_object_or_404(MusicItem, pk=pk)
    
    # Verificar permisos
    if music_item.created_by != request.user and not request.user.is_staff:
        return redirect('music_cards:music_items_list')
    
    if request.method == 'POST':
        music_item.delete()
        return redirect('music_cards:music_items_list')
    
    return render(request, 'music_cards/music_item_confirm_delete.html', {
        'music_item': music_item
    })


# Vista HTMX eliminada - ahora la conversión se hace automáticamente en el backend
