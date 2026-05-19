import os

# Navidrome Configuration
ROOT_ND = ""
USER_ND = ""
PASSWORD_ND = ""
MUSIC_LIBRARY_PATH = "/path/to/music"
TEMP_DOWNLOAD_FOLDER = "/path/to/temp"

# ListenBrainz API Configuration
LISTENBRAINZ_ENABLED = False
ROOT_LB = "https://api.listenbrainz.org"
TOKEN_LB = ""
USER_LB = ""

# Last.fm API Configuration
LASTFM_ENABLED = False
LASTFM_API_KEY = ""
LASTFM_API_SECRET = ""
LASTFM_USERNAME = ""
LASTFM_PASSWORD = ""
LASTFM_PASSWORD_HASH = ""
LASTFM_SESSION_KEY = ""

# slskd Configuration
SLSKD_URL = ""
SLSKD_API_KEY = ""
SLSKD_DOWNLOAD_DIR = "/path/to/slskd/downloads"

# UI Visibility Settings
HIDE_FRESH_RELEASES = os.getenv('HIDE_FRESH_RELEASES', 'false').lower() == 'true'

# Comment Tags for Playlist Creation
TARGET_COMMENT = "lb_recommendation"
LASTFM_TARGET_COMMENT = "lastfm_recommendation"
ALBUM_RECOMMENDATION_COMMENT = "album_recommendation"

# History Tracking
PLAYLIST_HISTORY_FILE = "playlist_history.txt"

# Caching for fresh releases (in seconds)
FRESH_RELEASES_CACHE_DURATION = 300
