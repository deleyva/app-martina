from django.urls import path
from . import views
from .debug_views import SpotifyDebugView

app_name = 'songs_ranking'

urlpatterns = [
    path('', views.SurveyListView.as_view(), name='survey_list'),
    path('create/', views.CreateSurveyView.as_view(), name='create_survey'),
    path('<int:pk>/', views.SurveyDetailView.as_view(), name='survey_detail'),
    path('<int:pk>/proposal/', views.ProposalPhaseView.as_view(), name='proposal_phase'),
    path('<int:pk>/proposal/add/', views.AddProposalView.as_view(), name='add_proposal'),
    path('<int:pk>/voting/', views.VotingPhaseView.as_view(), name='voting_phase'),
    path('<int:pk>/vote/add/', views.AddVoteView.as_view(), name='add_vote'),
    path('<int:pk>/vote/remove/', views.RemoveVoteView.as_view(), name='remove_vote'),
    path('<int:pk>/results/', views.ResultsView.as_view(), name='results'),
    path('<int:pk>/advance-to-voting/', views.AdvanceToVotingPhaseView.as_view(), name='advance_to_voting'),
    path('<int:pk>/return-to-proposal/', views.ReturnToProposalPhaseView.as_view(), name='return_to_proposal'),
    path('spotify/search/', views.SpotifySearchView.as_view(), name='spotify_search'),
    path('<int:survey_id>/spotify/search/', views.SpotifySearchView.as_view(), name='spotify_search_with_survey'),
    # Ruta de depuración
    path('debug/spotify/', SpotifyDebugView.as_view(), name='spotify_debug'),
]
