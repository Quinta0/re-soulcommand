import requests
import hashlib
import os
import shutil
from config import TEMP_DOWNLOAD_FOLDER
from mutagen import File, MutagenError
from utils import sanitize_filename


class NavidromeAPI:
    def __init__(self, root_nd, user_nd, password_nd, music_library_path, target_comment,
                 lastfm_target_comment, album_recommendation_comment=None,
                 listenbrainz_enabled=False, lastfm_enabled=False, **_ignored):
        self.root_nd = root_nd
        self.user_nd = user_nd
        self.password_nd = password_nd
        self.music_library_path = music_library_path
        self.target_comment = target_comment
        self.lastfm_target_comment = lastfm_target_comment
        self.album_recommendation_comment = album_recommendation_comment
        self.listenbrainz_enabled = listenbrainz_enabled
        self.lastfm_enabled = lastfm_enabled

    def _get_navidrome_auth_params(self):
        salt = os.urandom(6).hex()
        token = hashlib.md5((self.password_nd + salt).encode('utf-8')).hexdigest()
        return salt, token

    def _song_exists(self, artist, album, title):
        """Check whether a matching song already exists in Navidrome."""
        salt, token = self._get_navidrome_auth_params()
        url = f"{self.root_nd}/rest/search3.view"
        params = {
            'u': self.user_nd,
            't': token,
            's': salt,
            'v': '1.16.1',
            'c': 'python-script',
            'f': 'json',
            'query': f"{artist} {album} {title}",
            'songCount': 50
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            songs = []
            if data['subsonic-response']['status'] == 'ok' and 'searchResult3' in data['subsonic-response']:
                songs = data['subsonic-response']['searchResult3'].get('song', [])
            for song in songs:
                if (song.get('artist', '').strip().lower() == artist.strip().lower() and
                        song.get('album', '').strip().lower() == album.strip().lower() and
                        song.get('title', '').strip().lower() == title.strip().lower()):
                    return True
        except Exception as e:
            print(f"Error checking song existence in Navidrome: {e}")
        return False

    def organize_music_files(self, source_folder, destination_base_folder):
        """Move music files from source_folder into destination_base_folder/Artist/Album/filename."""
        from mutagen.id3 import ID3, ID3NoHeaderError
        from mutagen.flac import FLAC
        from mutagen.mp3 import MP3
        from mutagen.oggvorbis import OggVorbis
        from mutagen.m4a import M4A

        print(f"\nOrganizing music files from '{source_folder}' to '{destination_base_folder}'...")

        audio_extensions = ('.mp3', '.flac', '.m4a', '.aac', '.ogg', '.wma', '.wv', '.opus')

        for root, dirs, files in os.walk(source_folder):
            for filename in files:
                if not filename.lower().endswith(audio_extensions):
                    continue
                file_path = os.path.join(root, filename)
                file_ext = os.path.splitext(filename)[1].lower()

                try:
                    if file_ext == '.mp3':
                        audio = ID3(file_path)
                        artist = str(audio.get('TPE1', ['Unknown Artist'])[0])
                        album = str(audio.get('TALB', ['Unknown Album'])[0])
                    elif file_ext == '.flac':
                        audio = FLAC(file_path)
                        artist = (audio.get('artist') or ['Unknown Artist'])[0]
                        album = (audio.get('album') or ['Unknown Album'])[0]
                    elif file_ext in ('.m4a', '.aac'):
                        audio = M4A(file_path)
                        artist_tag = audio.get('\xa9ART')
                        artist = (artist_tag[0] if isinstance(artist_tag, list) else str(artist_tag)) if artist_tag else 'Unknown Artist'
                        album_tag = audio.get('\xa9alb')
                        album = (album_tag[0] if isinstance(album_tag, list) else str(album_tag)) if album_tag else 'Unknown Album'
                    elif file_ext in ('.ogg', '.oga'):
                        audio = OggVorbis(file_path)
                        artist = (audio.get('artist') or ['Unknown Artist'])[0]
                        album = (audio.get('album') or ['Unknown Album'])[0]
                    else:
                        artist = 'Unknown Artist'
                        album = 'Unknown Album'

                    artist = sanitize_filename(str(artist))
                    album = sanitize_filename(str(album))

                    dest_dir = os.path.join(destination_base_folder, artist, album)
                    os.makedirs(dest_dir, exist_ok=True)
                    dest_path = os.path.join(dest_dir, filename)

                    if os.path.exists(dest_path):
                        print(f"  Skipping (already exists): {dest_path}")
                    else:
                        shutil.move(file_path, dest_path)
                        print(f"  Moved: {filename} → {artist}/{album}/")

                except Exception as e:
                    print(f"  Error organizing {filename}: {e}")

        print("Organization complete.")
