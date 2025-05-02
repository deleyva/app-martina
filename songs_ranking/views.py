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
        
        context.update({
            'proposals': proposals,
            'vote_counts': vote_counts,
            'user_proposals': user_proposals,
            'user_votes': user_votes,
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

class VotingPhaseView(LoginRequiredMixin, View):
    template_name = 'songs_ranking/voting_phase.html'
    
    def get(self, request, pk):
        survey = get_object_or_404(Survey, pk=pk)
        
        # Check if survey is in voting phase
        if not survey.is_in_voting_phase:
            messages.error(request, "This survey is not in the voting phase.")
            return redirect('songs_ranking:survey_detail', pk=pk)
        
        # Get all proposals except user's own proposals
        all_proposals = SongProposal.objects.filter(survey=survey) \
            .exclude(participant=request.user) \
            .select_related('song', 'participant') \
            .order_by('?')  # Randomize order
        
        # Collect unique songs (as the same song might be proposed by multiple users)
        seen_songs = set()
        unique_proposals = []
        
        for proposal in all_proposals:
            if proposal.song_id not in seen_songs:
                seen_songs.add(proposal.song_id)
                unique_proposals.append(proposal)
        
        # Get user votes
        user_votes = Vote.objects.filter(
            survey=survey, 
            voter=request.user
        ).values_list('song_id', flat=True)
        
        # Count votes for each song
        vote_counts = {}
        all_votes = Vote.objects.filter(survey=survey) \
            .values('song') \
            .annotate(count=Count('id'))
        
        for vote in all_votes:
            vote_counts[vote['song']] = vote['count']
        
        context = {
            'survey': survey,
            'proposals': unique_proposals,
            'user_votes': user_votes,
            'vote_counts': vote_counts,
            'vote_count': len(user_votes)
        }
        
        return render(request, self.template_name, context)

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
        
        return JsonResponse({
            'song_id': song.id,
            'vote_count': vote_count,
            'total_user_votes': user_votes_count + 1
        })

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
        
        return JsonResponse({
            'song_id': song.id,
            'vote_count': vote_count,
            'total_user_votes': user_votes_count
        })

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
