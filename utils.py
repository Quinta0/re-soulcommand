from datetime import datetime
import json
import os
import re
import requests
import imghdr
from mutagen.id3 import ID3, COMM, APIC, TPE1, TALB, TIT2, TDRC, TXXX, UFID, error as ID3Error
from mutagen import File, MutagenError
from mutagen.mp3 import MP3
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from mutagen.m4a import M4A
from config import *


def get_last_playlist_name(playlist_history_file):
    try:
        with open(playlist_history_file, "r") as f:
            return f.readline().strip()
    except FileNotFoundError:
        return None


def save_playlist_name(playlist_history_file, playlist_name):
    try:
        with open(playlist_history_file, "w") as f:
            f.write(playlist_name)
    except OSError as e:
        print(f"Error saving playlist name to file: {e}")


def sanitize_filename(filename):
    return re.sub(r'[\\/:*?"<>|]', '_', filename)


def remove_empty_folders(path):
    for root, dirs, files in os.walk(path, topdown=False):
        for dir in dirs:
            full_path = os.path.join(root, dir)
            if not os.listdir(full_path):
                try:
                    os.rmdir(full_path)
                except OSError as e:
                    print(f"Error removing folder: {full_path}. Error: {e}")


class Tagger:
    def __init__(self, album_recommendation_comment=None):
        self.target_comment = TARGET_COMMENT
        self.lastfm_target_comment = LASTFM_TARGET_COMMENT
        self.album_recommendation_comment = album_recommendation_comment or ALBUM_RECOMMENDATION_COMMENT

    def add_comment_to_file(self, file_path, comment):
        try:
            if file_path.lower().endswith('.mp3'):
                try:
                    audio = ID3(file_path)
                except ID3Error:
                    audio = ID3()
                audio.add(COMM(encoding=3, lang='eng', desc='', text=comment))
                audio.save(file_path, v2_version=3, v1=2)
            elif file_path.lower().endswith('.flac'):
                audio = FLAC(file_path)
                audio['comment'] = comment
                audio.save()
            elif file_path.lower().endswith(('.ogg', '.oga')):
                audio = OggVorbis(file_path)
                audio['comment'] = comment
                audio.save()
            elif file_path.lower().endswith('.m4a'):
                audio = M4A(file_path)
                audio['\xa9cmt'] = [comment]
                audio.save()
            else:
                print(f"Unsupported file type for adding comment: {file_path}")
        except Exception as e:
            print(f"Error adding comment to {file_path}: {e}")

    def _embed_album_art(self, file_path, album_art_url):
        if not album_art_url:
            return
        try:
            response = requests.get(album_art_url, stream=True, timeout=15)
            response.raise_for_status()
            image_data = response.content
            image_type = imghdr.what(None, h=image_data)
            if not image_type:
                return
            mime_type = f"image/{image_type}"
            if file_path.lower().endswith('.mp3'):
                audio = MP3(file_path, ID3=ID3)
                audio.tags.add(APIC(encoding=3, mime=mime_type, type=3, desc='Cover', data=image_data))
                audio.save()
            elif file_path.lower().endswith('.flac'):
                audio = FLAC(file_path)
                image = FLAC.Picture()
                image.data = image_data
                image.type = 3
                image.mime = mime_type
                audio.add_picture(image)
                audio.save()
        except Exception as e:
            print(f"Error embedding album art into {file_path}: {e}")

    def tag_track(self, file_path, artist, title, album, release_date, recording_mbid, source,
                  album_art_url=None, is_album_recommendation=False):
        if not title:
            base_filename = os.path.splitext(os.path.basename(file_path))[0]
            extracted_title = base_filename
            artist_pattern = re.compile(f"^{re.escape(artist)}\\s*-\\s*", re.IGNORECASE)
            extracted_title = artist_pattern.sub("", extracted_title, 1)
            extracted_title = re.sub(r"^\d+\s*-\s*", "", extracted_title)
            extracted_title = re.sub(r"^\d+\.\s*", "", extracted_title)
            extracted_title = re.sub(r"^\(\d+\)\s*", "", extracted_title)
            extracted_title = extracted_title.strip(' -').strip()
            title = extracted_title or base_filename

        if is_album_recommendation and self.album_recommendation_comment:
            comment = self.album_recommendation_comment
        elif source == "ListenBrainz":
            comment = self.target_comment
        else:
            comment = self.lastfm_target_comment

        try:
            audio = File(file_path)
            if audio is None:
                print(f"Could not open audio file with Mutagen: {file_path}")
                return

            if file_path.lower().endswith('.mp3'):
                if audio.tags is None:
                    audio.tags = ID3()
                audio.tags.add(TPE1(encoding=3, text=[artist]))
                audio.tags.add(TIT2(encoding=3, text=[title]))
                audio.tags.add(TALB(encoding=3, text=[album]))
                audio.tags.add(TDRC(encoding=3, text=[release_date]))
                audio.tags.add(COMM(encoding=3, lang='eng', desc='', text=[comment]))
                if recording_mbid:
                    audio.tags.add(TXXX(encoding=3, desc='MUSICBRAINZ_RECORDINGID', text=[recording_mbid]))
                    audio.tags.add(UFID(owner='http://musicbrainz.org',
                                        data=f'http://musicbrainz.org/recording/{recording_mbid}'.encode('utf-8')))
            elif file_path.lower().endswith('.flac'):
                audio['artist'] = artist
                audio['title'] = title
                audio['album'] = album
                audio['date'] = release_date
                audio['comment'] = comment
                if recording_mbid:
                    audio['musicbrainz_recordingid'] = recording_mbid
            elif file_path.lower().endswith(('.ogg', '.oga')):
                audio['artist'] = artist
                audio['title'] = title
                audio['album'] = album
                audio['date'] = release_date
                audio['comment'] = comment
                if recording_mbid:
                    audio['musicbrainz_recordingid'] = recording_mbid
            elif file_path.lower().endswith('.m4a'):
                audio['\xa9ART'] = [artist]
                audio['\xa9nam'] = [title]
                audio['\xa9alb'] = [album]
                audio['\xa9day'] = [release_date]
                audio['\xa9cmt'] = [comment]
                if recording_mbid:
                    audio['----:com.apple.iTunes:MusicBrainz Recording Id'] = [recording_mbid.encode('utf-8')]
            else:
                print(f"Unsupported file type for tagging: {file_path}")
                return

            audio.save()
            print(f"Tagged: {file_path}")

            if album_art_url:
                self._embed_album_art(file_path, album_art_url)

        except MutagenError as e:
            print(f"Error tagging {file_path}: {e}")
        except Exception as e:
            print(f"Unexpected error tagging {file_path}: {e}")


def update_status_file(download_id, status, message=None, title=None, current_track_count=None, total_track_count=None):
    if not download_id:
        return

    status_dir = "/tmp/recommand_download_status"
    os.makedirs(status_dir, exist_ok=True)
    status_file_path = os.path.join(status_dir, f"{download_id}.json")

    status_data = {"status": status, "timestamp": datetime.now().isoformat()}
    if message:
        status_data["message"] = message
    if title:
        status_data["title"] = title
    else:
        if status == "completed":
            status_data["title"] = "Download completed"
        elif status == "failed":
            status_data["title"] = "Download failed"
        elif status == "in_progress":
            status_data["title"] = "Download in progress"
    if current_track_count is not None:
        status_data["current_track_count"] = current_track_count
    if total_track_count is not None:
        status_data["total_track_count"] = total_track_count

    with open(status_file_path, 'w') as f:
        json.dump(status_data, f)
    print(f"Status [{download_id}]: {status}")
