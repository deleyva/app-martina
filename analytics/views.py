from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import UserSession, PageVisit, Interaction
import json
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.db.models import Count, Avg, F, Q

@csrf_exempt
def track_activity(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        event_type = data.get('event_type')

        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key

        user_session, created = UserSession.objects.get_or_create(
            session_key=session_key,
            defaults={
                'user': request.user if request.user.is_authenticated else None,
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT')
            }
        )

        if event_type == 'pageview':
            PageVisit.objects.create(
                session=user_session,
                url=data.get('url'),
                title=data.get('title'),
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
                    event_type=db_event_type,
                    target_element=data.get('target_element'),
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
    visits_queryset = PageVisit.objects.select_related('session', 'session__user')
    
    if user_query:
        visits_queryset = visits_queryset.filter(
            Q(session__user__email__icontains=user_query) |
            Q(session__user__name__icontains=user_query) |
            Q(session__user__first_name__icontains=user_query) |
            Q(session__user__last_name__icontains=user_query)
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

    context = {
        'total_sessions': total_sessions,
        'total_pageviews': total_pageviews,
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
