from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

User = get_user_model()

class Survey(models.Model):
    """Model to represent a song ranking survey with two phases: proposals and voting"""
    title = models.CharField(_("Title"), max_length=200)
    description = models.TextField(_("Description"), blank=True)
    creator = models.ForeignKey(
        User, 
        verbose_name=_("Creator"), 
        on_delete=models.CASCADE,
        related_name="created_surveys"
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    proposal_phase_start = models.DateTimeField(_("Proposal phase start"))
    proposal_phase_end = models.DateTimeField(_("Proposal phase end"))
    voting_phase_start = models.DateTimeField(_("Voting phase start"))
    voting_phase_end = models.DateTimeField(_("Voting phase end"))
    is_active = models.BooleanField(_("Is active"), default=True)
    
    def __str__(self):
        return self.title
    
    @property
    def is_in_proposal_phase(self):
        now = timezone.now()
        return self.proposal_phase_start <= now <= self.proposal_phase_end
    
    @property
    def is_in_voting_phase(self):
        now = timezone.now()
        return self.voting_phase_start <= now <= self.voting_phase_end
    
    @property
    def is_completed(self):
        return timezone.now() > self.voting_phase_end
    
    @property
    def current_phase(self):
        if self.is_in_proposal_phase:
            return "proposal"
        elif self.is_in_voting_phase:
            return "voting"
        elif timezone.now() < self.proposal_phase_start:
            return "not_started"
        else:
            return "completed"

class Song(models.Model):
    """Model to represent a song from Spotify"""
    spotify_id = models.CharField(_("Spotify ID"), max_length=100, unique=True)
    name = models.CharField(_("Name"), max_length=255)
    artist = models.CharField(_("Artist"), max_length=255)
    album = models.CharField(_("Album"), max_length=255, blank=True)
    preview_url = models.URLField(_("Preview URL"), max_length=500, blank=True, null=True)
    image_url = models.URLField(_("Image URL"), max_length=500, blank=True, null=True)
    
    def __str__(self):
        return f"{self.name} by {self.artist}"

class SongProposal(models.Model):
    """Model to represent a song proposal by a participant"""
    survey = models.ForeignKey(
        Survey, 
        verbose_name=_("Survey"), 
        on_delete=models.CASCADE,
        related_name="proposals"
    )
    song = models.ForeignKey(
        Song, 
        verbose_name=_("Song"), 
        on_delete=models.CASCADE,
        related_name="proposals"
    )
    participant = models.ForeignKey(
        User, 
        verbose_name=_("Participant"), 
        on_delete=models.CASCADE,
        related_name="song_proposals"
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    
    class Meta:
        unique_together = ('survey', 'song', 'participant')
        
    def __str__(self):
        return f"{self.participant.username} proposed {self.song} for {self.survey}"

class Vote(models.Model):
    """Model to represent a vote for a song"""
    survey = models.ForeignKey(
        Survey, 
        verbose_name=_("Survey"), 
        on_delete=models.CASCADE,
        related_name="votes"
    )
    song = models.ForeignKey(
        Song, 
        verbose_name=_("Song"), 
        on_delete=models.CASCADE,
        related_name="votes"
    )
    voter = models.ForeignKey(
        User, 
        verbose_name=_("Voter"), 
        on_delete=models.CASCADE,
        related_name="song_votes"
    )
    created_at = models.DateTimeField(_("Created at"), auto_now_add=True)
    
    class Meta:
        unique_together = ('survey', 'song', 'voter')
        
    def __str__(self):
        return f"{self.voter.username} voted for {self.song} in {self.survey}"
