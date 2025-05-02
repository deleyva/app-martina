import requests
import base64
import json
import logging
from django.conf import settings

logger = logging.getLogger(__name__)

class SpotifyClient:
    """Client for interacting with the Spotify API"""
    
    def __init__(self):
        self.client_id = settings.SPOTIFY_CLIENT_ID
        self.client_secret = settings.SPOTIFY_CLIENT_SECRET
        self.token = None
        self.base_url = "https://api.spotify.com/v1"
        
    def get_auth_token(self):
        """Get a new authorization token from Spotify"""
        auth_url = "https://accounts.spotify.com/api/token"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {"grant_type": "client_credentials"}
        
        try:
            response = requests.post(auth_url, headers=headers, data=data)
            response.raise_for_status()
            
            auth_data = response.json()
            self.token = auth_data["access_token"]
            return self.token
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Spotify auth token: {str(e)}")
            return None
    
    def search_songs(self, query, limit=10):
        """Search for songs using the Spotify API"""
        if not self.token:
            self.get_auth_token()
            
        if not self.token:
            logger.error("Failed to get Spotify authentication token")
            return []
            
        search_url = f"{self.base_url}/search"
        headers = {"Authorization": f"Bearer {self.token}"}
        params = {
            "q": query,
            "type": "track",
            "limit": limit
        }
        
        try:
            logger.info(f"Searching Spotify for: {query}")
            response = requests.get(search_url, headers=headers, params=params)
            response.raise_for_status()
            
            results = response.json()
            logger.info(f"Spotify API response status: {response.status_code}")
            
            if 'tracks' not in results or 'items' not in results.get('tracks', {}):
                logger.error(f"Unexpected response format from Spotify API: {results}")
                return []
                
            tracks = results.get("tracks", {}).get("items", [])
            logger.info(f"Found {len(tracks)} tracks in Spotify search")
            
            song_data = []
            for track in tracks:
                artists = ", ".join([artist["name"] for artist in track["artists"]])
                album_name = track["album"]["name"] if track["album"] else ""
                images = track["album"]["images"] if track["album"] and "images" in track["album"] else []
                image_url = images[0]["url"] if images else None
                
                song = {
                    "spotify_id": track["id"],
                    "name": track["name"],
                    "artist": artists,
                    "album": album_name,
                    "preview_url": track.get("preview_url"),
                    "image_url": image_url
                }
                song_data.append(song)
            
            return song_data
        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Spotify songs: {str(e)}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error in Spotify search: {str(e)}")
            return []
    
    def get_song_by_id(self, spotify_id):
        """Get a specific song by its Spotify ID"""
        if not self.token:
            self.get_auth_token()
            
        if not self.token:
            return None
            
        track_url = f"{self.base_url}/tracks/{spotify_id}"
        headers = {"Authorization": f"Bearer {self.token}"}
        
        try:
            response = requests.get(track_url, headers=headers)
            response.raise_for_status()
            
            track = response.json()
            artists = ", ".join([artist["name"] for artist in track["artists"]])
            album_name = track["album"]["name"] if track["album"] else ""
            images = track["album"]["images"] if track["album"] and "images" in track["album"] else []
            image_url = images[0]["url"] if images else None
            
            song = {
                "spotify_id": track["id"],
                "name": track["name"],
                "artist": artists,
                "album": album_name,
                "preview_url": track.get("preview_url"),
                "image_url": image_url
            }
            
            return song
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching Spotify song {spotify_id}: {str(e)}")
            return None
