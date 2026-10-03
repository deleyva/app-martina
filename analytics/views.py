from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import UserSession, PageVisit, Interaction
import json
import uuid
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg, F, Max, Q
from datetime import timedelta


def resolve_visitor_id(data):
    """
    Identidad de visitante para la analítica, tomada del cuerpo de la petición.

    Esta función existe para que la telemetría NUNCA toque `request.session`.
    La sesión es de autenticación: escribir en ella desde aquí acuñaba una
    cookie nueva a mitad de un login con Google y borraba el `state` que allauth
    había guardado, con lo que el callback moría con `Codigo: unknown`.

    `analytics.js` ya generaba un UUID v4 por navegador y lo guardaba en
    `localStorage`; lo mandaba en el cuerpo como `session_key` y el backend lo
    ignoraba. Se acepta el nombre nuevo (`visitor_id`) y el antiguo, para que
    los navegadores con el JS viejo cacheado sigan midiendo sin día de corte.

    Devuelve None si no llega un UUID válido. En ese caso no se registra nada:
    generar uno aquí crearía una fila por petición para cualquier bot que
    golpee este endpoint, que es `csrf_exempt`.
    """
    raw = data.get('visitor_id') or data.get('session_key')
    if not isinstance(raw, str):
        return None
    try:
        return str(uuid.UUID(raw))
    except ValueError:
        return None


def a_medida(modelo, campo, valor):
    """Recorta `valor` a la anchura de la columna `campo` de `modelo`.

    El navegador manda lo que tenga: un `<title>` de una entrada larga o un
    `target_element` con la lista entera de clases de Tailwind pasan de 255
    caracteres sin esfuerzo, y Postgres contesta `value too long for type
    character varying(255)` con un 500 y un correo. Lo que se mide es dónde
    ha pasado algo, no el texto entero, así que recortar no pierde nada útil.
    Se lee el `max_length` del modelo para que cambiarlo en la migración
    baste, sin un número repetido aquí.
    """
    if not isinstance(valor, str):
        return valor
    limite = modelo._meta.get_field(campo).max_length
    return valor[:limite] if limite else valor


@csrf_exempt
def track_activity(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        event_type = data.get('event_type')

        visitor_id = resolve_visitor_id(data)
        if visitor_id is None:
            return JsonResponse(
                {'status': 'ignored', 'reason': 'missing or invalid visitor_id'},
                status=202,
            )

        user = request.user if request.user.is_authenticated else None
        user_session, created = UserSession.objects.get_or_create(
            visitor_id=visitor_id,
            defaults={
                'user': user,
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT')
            }
        )
        # La sesión nace casi siempre anónima, en la página de login. Se
        # actualiza al último usuario autenticado visto; la atribución fiable
        # es la de cada visita (`PageVisit.user`).
        if user is not None and user_session.user_id != user.pk:
            user_session.user = user
            user_session.save(update_fields=['user'])

        if event_type == 'pageview':
            PageVisit.objects.create(
                session=user_session,
                user=user,
                url=a_medida(PageVisit, 'url', data.get('url')),
                title=a_medida(PageVisit, 'title', data.get('title')),
                timestamp=timezone.now()
            )
        elif event_type in ['interaction', 'accordion_toggle', 'audio_play', 'audio_pause']:
            # Find the latest page visit for this session
            latest_visit = PageVisit.objects.filter(session=user_session).order_by('-timestamp').first()
            if latest_visit:
                # Handle specific event types
                db_event_type = 'click'
                if event_type == 'accordion_toggle':
                    action = data.get('action', 'toggle')
                    db_event_type = f'accordion_{action}' # accordion_open or accordion_close
                elif event_type in ['audio_play', 'audio_pause']:
                    db_event_type = event_type
                
                # Truncate text if needed
                target_text = data.get('target_text', '')
                if target_text and len(target_text) > 100:
                    target_text = target_text[:97] + '...'

                Interaction.objects.create(
                    visit=latest_visit,
                    event_type=a_medida(Interaction, 'event_type', db_event_type),
                    target_element=a_medida(
                        Interaction, 'target_element', data.get('target_element')
                    ),
                    target_text=target_text,
                    x_coordinate=data.get('x'),
                    y_coordinate=data.get('y'),
                    timestamp=timezone.now()
                )

        return JsonResponse({'status': 'ok'})

    return JsonResponse({'status': 'error'}, status=400)


@staff_member_required
def analytics_dashboard(request):
    # Summary stats
    total_sessions = UserSession.objects.count()
    total_pageviews = PageVisit.objects.count()
    total_interactions = Interaction.objects.count()
    
    # User filtering
    user_query = request.GET.get('user', '')
    visits_queryset = PageVisit.objects.select_related('user')
    
    if user_query:
        visits_queryset = visits_queryset.filter(
            Q(user__email__icontains=user_query) |
            Q(user__name__icontains=user_query) |
            Q(user__first_name__icontains=user_query) |
            Q(user__last_name__icontains=user_query)
        )

    # Pagination parameters
    VISITS_PER_PAGE = 10
    HOTSPOTS_PER_PAGE = 10
    
    visits_offset = int(request.GET.get('visits_offset', 0))
    hotspots_offset = int(request.GET.get('hotspots_offset', 0))
    
    # Recent activity
    recent_visits = visits_queryset.order_by('-timestamp')[visits_offset:visits_offset + VISITS_PER_PAGE + 1]
    recent_visits_list = list(recent_visits)
    has_more_visits = len(recent_visits_list) > VISITS_PER_PAGE
    if has_more_visits:
        recent_visits_list = recent_visits_list[:VISITS_PER_PAGE]
    
    # Check for HTMX request for visits
    if request.headers.get('HX-Request') and 'visits_offset' in request.GET:
        return render(request, 'analytics/partials/recent_visits_rows.html', {
            'recent_visits': recent_visits_list,
            'has_more_visits': has_more_visits,
            'next_visits_offset': visits_offset + VISITS_PER_PAGE,
            'user_query': user_query,
            'is_htmx': True
        })

    # Top pages
    top_pages = PageVisit.objects.values('url', 'title').annotate(
        views=Count('id'),
        avg_duration=Avg('duration')
    ).order_by('-views')[:10]

    # Interaction hotspots
    hotspots = Interaction.objects.values('target_element', 'visit__url', 'visit__title').annotate(
        count=Count('id')
    ).order_by('-count')[hotspots_offset:hotspots_offset + HOTSPOTS_PER_PAGE + 1]
    
    hotspots_list = list(hotspots)
    has_more_hotspots = len(hotspots_list) > HOTSPOTS_PER_PAGE
    if has_more_hotspots:
        hotspots_list = hotspots_list[:HOTSPOTS_PER_PAGE]

    # Check for HTMX request for hotspots
    if request.headers.get('HX-Request') and 'hotspots_offset' in request.GET:
        return render(request, 'analytics/partials/hotspots_rows.html', {
            'hotspots': hotspots_list,
            'total_interactions': total_interactions,
            'has_more_hotspots': has_more_hotspots,
            'next_hotspots_offset': hotspots_offset + HOTSPOTS_PER_PAGE,
            'user_query': user_query,
            'is_htmx': True
        })

    days = periodo(request)
    context = {
        'total_sessions': total_sessions,
        'total_pageviews': total_pageviews,
        'anonymous_pageviews': PageVisit.objects.filter(user__isnull=True).count(),
        'top_users': ranking_usuarios(days),
        'days': days,
        'periodos': PERIODOS,
        'total_interactions': total_interactions,
        'recent_visits': recent_visits_list,
        'top_pages': top_pages,
        'hotspots': hotspots_list,
        'user_query': user_query,
        'has_more_visits': has_more_visits,
        'next_visits_offset': visits_offset + VISITS_PER_PAGE,
        'has_more_hotspots': has_more_hotspots,
        'next_hotspots_offset': hotspots_offset + HOTSPOTS_PER_PAGE,
    }
    return render(request, 'analytics/dashboard.html', context)


#: Periodos del ranking, en días; 0 = todo el histórico.
PERIODOS = [(7, '7 días'), (30, '30 días'), (0, 'Todo')]


def periodo(request):
    """Días del ranking pedidos en `?days=`; 30 si falta o no es válido."""
    try:
        days = int(request.GET.get('days', 30))
    except ValueError:
        return 30
    return days if days in dict(PERIODOS) else 30


def ranking_usuarios(days, limite=20):
    """Usuarios con más páginas vistas en los últimos `days` días (0 = siempre)."""
    visitas = PageVisit.objects.filter(user__isnull=False)
    if days:
        visitas = visitas.filter(timestamp__gte=timezone.now() - timedelta(days=days))
    return list(
        visitas.values('user', 'user__email', 'user__name')
        .annotate(visits=Count('id'), last_visit=Max('timestamp'))
        .order_by('-visits')[:limite]
    )


@staff_member_required
def user_activity(request, pk):
    """Lo que ha visto un usuario: sus visitas, de la más reciente a la más antigua."""
    usuario = get_object_or_404(get_user_model(), pk=pk)
    visitas = PageVisit.objects.filter(user=usuario)

    PER_PAGE = 50
    try:
        offset = max(int(request.GET.get('offset', 0)), 0)
    except ValueError:
        offset = 0
    pagina = list(
        visitas.annotate(clicks=Count('interactions'))
        .order_by('-timestamp')[offset:offset + PER_PAGE + 1]
    )
    has_more = len(pagina) > PER_PAGE
    context = {
        'usuario': usuario,
        'visits': pagina[:PER_PAGE],
        'has_more': has_more,
        'next_offset': offset + PER_PAGE,
    }
    if request.headers.get('HX-Request') and 'offset' in request.GET:
        return render(request, 'analytics/partials/user_visits_rows.html', context)

    context.update({
        'total_visits': visitas.count(),
        'first_visit': visitas.order_by('timestamp').values_list('timestamp', flat=True).first(),
        'top_pages': visitas.values('url', 'title')
            .annotate(views=Count('id')).order_by('-views')[:10],
    })
    return render(request, 'analytics/user_activity.html', context)
