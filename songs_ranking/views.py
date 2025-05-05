from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, CreateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse, JsonResponse
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.contrib import messages
from django.db.models import Count
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
import json
import logging

logger = logging.getLogger(__name__)

from .models import Survey, Song, SongProposal, Vote
from .spotify_client import SpotifyClient

class SurveyListView(ListView):
    model = Survey
    context_object_name = 'surveys'
    template_name = 'songs_ranking/survey_list.html'
    
    def get_queryset(self):
        return Survey.objects.filter(is_active=True).order_by('-created_at')

class SurveyDetailView(DetailView):
    model = Survey
    context_object_name = 'survey'
    template_name = 'songs_ranking/survey_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        
        # Get all song proposals for this survey
        proposals = SongProposal.objects.filter(survey=survey).select_related('song', 'participant')
        
        # Count votes for each song in this survey
        song_votes = Vote.objects.filter(survey=survey) \
            .values('song') \
            .annotate(vote_count=Count('id')) \
            .order_by('-vote_count')
        
        # Create a dictionary with song_id as key and vote count as value
        vote_counts = {vote['song']: vote['vote_count'] for vote in song_votes}
        
        # Current user's proposals
        user_proposals = []
        if self.request.user.is_authenticated:
            user_proposals = SongProposal.objects.filter(
                survey=survey, 
                participant=self.request.user
            ).values_list('song_id', flat=True)
        
        # Current user's votes
        user_votes = []
        if self.request.user.is_authenticated:
            user_votes = Vote.objects.filter(
                survey=survey, 
                voter=self.request.user
            ).values_list('song_id', flat=True)
        
        # Count unique participants
        unique_participants_count = proposals.values('participant').distinct().count()
        
        # Preparar los conteos de votos para cada propuesta directamente
        proposals_with_votes = []
        for proposal in proposals:
            proposal.vote_count = vote_counts.get(proposal.song.id, 0)
            proposals_with_votes.append(proposal)
        
        context.update({
            'proposals': proposals_with_votes,
            'vote_counts': vote_counts,
            'user_proposals': user_proposals,
            'user_votes': user_votes,
            'unique_participants_count': unique_participants_count,
        })
        
        return context

class CreateSurveyView(LoginRequiredMixin, CreateView):
    model = Survey
    template_name = 'songs_ranking/create_survey.html'
    fields = ['title', 'description', 'proposal_phase_start', 'proposal_phase_end', 
              'voting_phase_start', 'voting_phase_end']
    success_url = reverse_lazy('songs_ranking:survey_list')
    
    def form_valid(self, form):
        form.instance.creator = self.request.user
        messages.success(self.request, "Survey created successfully!")
        return super().form_valid(form)

class SpotifySearchView(LoginRequiredMixin, View):
    def get(self, request, survey_id=None):
        query = request.GET.get('q', '')
        # Si no viene en la URL, intentamos obtenerlo del GET
        if not survey_id:
            survey_id = request.GET.get('survey_id')
        
        context = {
            'songs': [],
            'survey_id': survey_id
        }
        
        if not query:
            return render(request, 'songs_ranking/partials/song_results.html', context)
        
        try:
            # Validamos que sea un ID válido
            if survey_id and isinstance(survey_id, str) and survey_id.isdigit():
                survey_id = int(survey_id)
                context['survey_id'] = survey_id
            
            spotify_client = SpotifyClient()
            token = spotify_client.get_auth_token()
            
            if not token:
                context['error'] = 'No se pudo obtener el token de autenticación de Spotify'
                return render(request, 'songs_ranking/partials/song_results.html', context)
            
            songs = spotify_client.search_songs(query)
            
            # Registro adicional para depuración
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Spotify search for '{query}' returned {len(songs)} results")
            
            context.update({
                'songs': songs,
                'query': query
            })
            
            return render(request, 'songs_ranking/partials/song_results.html', context)
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in SpotifySearchView: {str(e)}")
            
            context['error'] = f"Error en la búsqueda: {str(e)}"
            return render(request, 'songs_ranking/partials/song_results.html', context)

class ProposalPhaseView(LoginRequiredMixin, View):
    template_name = 'songs_ranking/proposal_phase.html'
    
    def get(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Check if survey is in proposal phase
        if not survey.is_in_proposal_phase:
            messages.error(request, "This survey is not in the proposal phase.")
            return redirect('songs_ranking:survey_detail', pk=pk)
        
        # Get user proposals
        user_proposals = SongProposal.objects.filter(
            survey=survey, 
            participant=request.user
        ).select_related('song')
        
        # Get all proposals count to show statistics
        all_proposals_count = SongProposal.objects.filter(survey=survey).count()
        
        context = {
            'survey': survey,
            'user_proposals': user_proposals,
            'proposal_count': user_proposals.count(),
            'all_proposals_count': all_proposals_count
        }
        
        return render(request, self.template_name, context)

@method_decorator(require_POST, name='post')
class AddProposalView(LoginRequiredMixin, View):
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Check if survey is in proposal phase
        if not survey.is_in_proposal_phase:
            messages.error(request, "Esta encuesta no está en fase de propuestas.")
            return HttpResponse("Encuesta no en fase de propuestas", status=400)
        
        # Check if user already has 3 proposals
        user_proposals_count = SongProposal.objects.filter(
            survey=survey, 
            participant=request.user
        ).count()
        
        if user_proposals_count >= 3:
            return HttpResponse("Ya has propuesto 3 canciones", status=400)
        
        # Get song data from request
        spotify_id = request.POST.get('spotify_id')
        name = request.POST.get('name')
        artist = request.POST.get('artist')
        album = request.POST.get('album', '')
        preview_url = request.POST.get('preview_url', '')
        image_url = request.POST.get('image_url', '')
        
        if not all([spotify_id, name, artist]):
            return HttpResponse("Faltan datos requeridos de la canción", status=400)
        
        # Get or create song
        song, created = Song.objects.get_or_create(
            spotify_id=spotify_id,
            defaults={
                'name': name,
                'artist': artist,
                'album': album,
                'preview_url': preview_url,
                'image_url': image_url
            }
        )
        
        # Si la canción ya existía, actualizar la URL de previsualización si está disponible
        if not created and preview_url:
            song.preview_url = preview_url
            song.save(update_fields=['preview_url'])
        
        # Check if this proposal already exists
        proposal, created = SongProposal.objects.get_or_create(
            survey=survey,
            song=song,
            participant=request.user
        )
        
        if not created:
            return HttpResponse("Ya has propuesto esta canción", status=400)
        
        # Render the new proposal item for the list
        return render(request, 'songs_ranking/partials/proposal_item.html', {'proposal': proposal})

class VotingPhaseView(LoginRequiredMixin, DetailView):
    model = Survey
    template_name = 'songs_ranking/voting_phase.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        
        # Check if survey is in voting phase
        if not survey.is_in_voting_phase:
            messages.error(self.request, "This survey is not in the voting phase yet.")
            return context
        
        # Get all proposals for this survey, excluding those made by the current user
        proposals = SongProposal.objects.filter(
            survey=survey
        ).exclude(
            participant=self.request.user
        ).select_related('song')
        
        # Count votes for each song in this survey
        vote_counts = {}
        for vote in Vote.objects.filter(survey=survey).values('song').annotate(count=Count('id')):
            vote_counts[vote.get('song')] = vote.get('count')
        
        # Refresh preview URLs for all songs
        self.refresh_preview_urls([p.song for p in proposals])
        
        # Add vote count to each proposal for sorting
        proposals_with_votes = []
        for proposal in proposals:
            vote_count = vote_counts.get(proposal.song.id, 0)
            proposals_with_votes.append({
                'proposal': proposal,
                'vote_count': vote_count
            })
        
        # Sort proposals by vote count in descending order
        sorted_proposals = sorted(proposals_with_votes, key=lambda x: x['vote_count'], reverse=True)
        
        # Extract just the proposals for the template
        context['proposals'] = [item['proposal'] for item in sorted_proposals]
        
        # Get all votes by the current user
        user_votes = Vote.objects.filter(
            survey=survey,
            voter=self.request.user
        ).values_list('song_id', flat=True)
        
        context['vote_counts'] = vote_counts
        context['user_votes'] = user_votes
        context['vote_count'] = len(user_votes)
        
        return context
    
    def refresh_preview_urls(self, songs):
        """Actualiza las URLs de previsualización de las canciones usando la API de Spotify"""
        from .spotify_client import SpotifyClient
        
        spotify_client = SpotifyClient()
        
        for song in songs:
            # Solo actualizar si no tiene URL de previsualización o si está vacía
            if not song.preview_url:
                try:
                    # Obtener datos actualizados de Spotify
                    song_data = spotify_client.get_song_by_id(song.spotify_id)
                    if song_data and song_data.get('preview_url'):
                        song.preview_url = song_data.get('preview_url')
                        song.save(update_fields=['preview_url'])
                except Exception as e:
                    # No interrumpir el flujo si hay un error con la API de Spotify
                    logger.error(f"Error al actualizar URL de previsualización para {song.name}: {str(e)}")

@method_decorator(require_POST, name='post')
class AddVoteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Check if survey is in voting phase
        if not survey.is_in_voting_phase:
            return HttpResponse("Survey not in voting phase", status=400)
        
        # Check if user already has 3 votes
        user_votes_count = Vote.objects.filter(
            survey=survey, 
            voter=request.user
        ).count()
        
        if user_votes_count >= 3:
            return HttpResponse("You've already voted for 3 songs", status=400)
        
        # Get song
        song_id = request.POST.get('song_id')
        if not song_id:
            return HttpResponse("Missing song id", status=400)
        
        song = get_object_or_404(Song, pk=song_id)
        
        # Check if user proposed this song
        user_proposed = SongProposal.objects.filter(
            survey=survey,
            song=song,
            participant=request.user
        ).exists()
        
        if user_proposed:
            return HttpResponse("You cannot vote for a song you proposed", status=400)
        
        # Check if vote already exists
        vote, created = Vote.objects.get_or_create(
            survey=survey,
            song=song,
            voter=request.user
        )
        
        if not created:
            return HttpResponse("You've already voted for this song", status=400)
        
        # Get updated vote count for this song
        vote_count = Vote.objects.filter(survey=survey, song=song).count()
        
        # Get total user votes
        total_user_votes = Vote.objects.filter(survey=survey, voter=request.user).count()
        
        # Update the response with both the button and vote count
        response = render(request, 'songs_ranking/partials/vote_actions.html', {
            'song': song,
            'survey': survey,
            'user_votes': [song.id],  # Incluimos el ID de la canción actual
            'vote_count': vote_count
        })
        
        # Script to update only the vote counter in the page
        response['HX-Trigger'] = json.dumps({
            'updateVoteCounter': {
                'total_votes': total_user_votes
            }
        })
        
        return response

@method_decorator(require_POST, name='post')
class RemoveVoteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Check if survey is in voting phase
        if not survey.is_in_voting_phase:
            return HttpResponse("Survey not in voting phase", status=400)
        
        # Get song
        song_id = request.POST.get('song_id')
        if not song_id:
            return HttpResponse("Missing song id", status=400)
        
        song = get_object_or_404(Song, pk=song_id)
        
        # Remove vote if exists
        try:
            vote = Vote.objects.get(survey=survey, song=song, voter=request.user)
            vote.delete()
        except Vote.DoesNotExist:
            return HttpResponse("Vote does not exist", status=400)
        
        # Get updated vote count for this song
        vote_count = Vote.objects.filter(survey=survey, song=song).count()
        
        # Get total user votes
        user_votes_count = Vote.objects.filter(survey=survey, voter=request.user).count()
        
        # Update the response with both the button and vote count
        response = render(request, 'songs_ranking/partials/vote_actions.html', {
            'song': song,
            'survey': survey,
            'user_votes': [],  # No incluimos este ID porque acabamos de eliminar el voto
            'vote_count': vote_count
        })
        
        # Script to update only the vote counter in the page
        response['HX-Trigger'] = json.dumps({
            'updateVoteCounter': {
                'total_votes': user_votes_count
            }
        })
        
        return response

class ResultsView(DetailView):
    model = Survey
    template_name = 'songs_ranking/results.html'
    context_object_name = 'survey'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        survey = self.get_object()
        
        # Get vote counts for each song
        song_votes = Vote.objects.filter(survey=survey) \
            .values('song') \
            .annotate(vote_count=Count('id')) \
            .order_by('-vote_count')
        
        # Get songs data
        songs_with_votes = []
        for vote in song_votes:
            song = Song.objects.get(pk=vote['song'])
            songs_with_votes.append({
                'song': song,
                'vote_count': vote['vote_count']
            })
        
        context['songs_with_votes'] = songs_with_votes
        context['total_votes'] = Vote.objects.filter(survey=survey).count()
        context['total_participants'] = SongProposal.objects.filter(survey=survey) \
            .values('participant').distinct().count()
            
        return context

@method_decorator(require_POST, name='post')
class AdvanceToVotingPhaseView(LoginRequiredMixin, View):
    """
    Vista para avanzar manualmente una encuesta de la fase de propuestas a la fase de votación
    Esto se consigue modificando las fechas de las fases
    """
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Comprobar que el usuario tiene permisos (creador o superusuario)
        if not (request.user == survey.creator or request.user.is_superuser):
            messages.error(request, "No tienes permisos para realizar esta acción.")
            return redirect('songs_ranking:survey_detail', pk=pk)
        
        # Comprobar que la encuesta esté en fase de propuestas o no haya empezado aún
        if survey.current_phase not in ["proposal", "not_started"]:
            messages.error(request, "Esta encuesta no está en fase de propuestas o aún no ha comenzado.")
            return redirect('songs_ranking:survey_detail', pk=pk)
        
        # Modificar las fechas para avanzar a la fase de votación
        now = timezone.now()
        
        # Ajustar las fechas de la fase de propuestas (finalizarla)
        if survey.proposal_phase_start > now:
            survey.proposal_phase_start = now - timezone.timedelta(minutes=1)
        survey.proposal_phase_end = now
        
        # Ajustar las fechas de la fase de votación (iniciarla ahora)
        survey.voting_phase_start = now
        
        # Si la fecha de fin de votación está en el pasado, añadir un periodo razonable
        if survey.voting_phase_end <= now:
            survey.voting_phase_end = now + timezone.timedelta(days=3)
        
        survey.save()
        
        messages.success(request, "La encuesta ha sido avanzada a la fase de votación.")
        return redirect('songs_ranking:voting_phase', pk=pk)

@method_decorator(require_POST, name='post')
class ReturnToProposalPhaseView(LoginRequiredMixin, View):
    """
    Vista para volver manualmente una encuesta de la fase de votación a la fase de propuestas
    Esto se consigue modificando las fechas de las fases
    """
    def post(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Comprobar que el usuario tiene permisos (creador o superusuario)
        if not (request.user == survey.creator or request.user.is_superuser):
            messages.error(request, "No tienes permisos para realizar esta acción.")
            return redirect('songs_ranking:survey_detail', pk=pk)
        
        # Comprobar que la encuesta esté en fase de votación
        if survey.current_phase != "voting":
            messages.error(request, "Esta encuesta no está en fase de votación.")
            return redirect('songs_ranking:survey_detail', pk=pk)
        
        # Modificar las fechas para volver a la fase de propuestas
        now = timezone.now()
        
        # Extender la fase de propuestas hasta una fecha futura
        # Si la fase de propuestas estaba en el pasado, la actualizamos para que comience ahora
        if survey.proposal_phase_start > now:
            survey.proposal_phase_start = now
        
        # Establecer el fin de la fase de propuestas para dentro de unos días
        survey.proposal_phase_end = now + timezone.timedelta(days=3)
        
        # Ajustar las fechas de la fase de votación para que comience después
        survey.voting_phase_start = survey.proposal_phase_end + timezone.timedelta(minutes=1)
        
        # Si la fecha de fin de votación es anterior a la nueva fecha de inicio, también la ajustamos
        if survey.voting_phase_end <= survey.voting_phase_start:
            survey.voting_phase_end = survey.voting_phase_start + timezone.timedelta(days=3)
        
        # Ya no eliminamos los votos existentes
        # Vote.objects.filter(survey=survey).delete()
        
        survey.save()
        
        messages.success(request, "La encuesta ha vuelto a la fase de propuestas. Los votos existentes se han mantenido.")
        return redirect('songs_ranking:proposal_phase', pk=pk)
