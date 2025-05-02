from django.contrib import admin
from .models import Survey, Song, SongProposal, Vote

# Register your models here.

@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ('title', 'creator', 'current_phase', 'is_active')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')

@admin.register(Song)
class SongAdmin(admin.ModelAdmin):
    list_display = ('name', 'artist', 'album', 'spotify_id')
    search_fields = ('name', 'artist', 'album', 'spotify_id')

@admin.register(SongProposal)
class SongProposalAdmin(admin.ModelAdmin):
    list_display = ('survey', 'song', 'participant', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('survey__title', 'song__name', 'participant__username')

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ('survey', 'song', 'voter', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('survey__title', 'song__name', 'voter__username')
