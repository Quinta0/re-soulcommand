import os
import time
import importlib
from collections import defaultdict

import config
from apis.slskd_api import SlskdAPI, is_audio_file, score_file


def _find_file_in_dir(directory, username, basename, timeout=90):
    """Recursively search for basename under directory/username, waiting up to timeout seconds."""
    user_dir = os.path.join(directory, username)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isdir(user_dir):
            for root, _, files in os.walk(user_dir):
                if basename in files:
                    return os.path.join(root, basename)
        time.sleep(3)
    return None


def _best_track_result(results):
    """Return the highest-quality unlocked audio result."""
    candidates = [
        r for r in results
        if is_audio_file(r['file'].get('filename', ''))
        and not r['file'].get('isLocked', False)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda r: score_file(r['file']), reverse=True)
    return candidates[0]


def _best_album_folder(results):
    """Group results by (username, remote_folder) and return the most complete high-quality folder."""
    folder_groups = defaultdict(list)
    for r in results:
        fname = r['file'].get('filename', '')
        if is_audio_file(fname) and not r['file'].get('isLocked', False):
            normalized = fname.replace('\\', '/')
            folder = '/'.join(normalized.split('/')[:-1])
            folder_groups[(r['username'], folder)].append(r['file'])

    if not folder_groups:
        return None, []

    best_score = -1
    best_username = None
    best_files = None
    for (username, _folder), files in folder_groups.items():
        avg_quality = sum(score_file(f) for f in files) / len(files)
        score = len(files) * 10000 + avg_quality
        if score > best_score:
            best_score = score
            best_username = username
            best_files = files

    return best_username, best_files or []


class SlskdDownloader:
    def __init__(self, tagger):
        self.tagger = tagger

    def _slskd(self):
        importlib.reload(config)
        return SlskdAPI(config.SLSKD_URL, config.SLSKD_API_KEY)

    async def download_track(self, song_info, lb_recommendation=False):
        importlib.reload(config)
        slskd = self._slskd()

        artist = song_info['artist']
        title = song_info['title']

        source = song_info.get('source', 'ListenBrainz').lower()
        if lb_recommendation or source == 'listenbrainz':
            comment_tag = config.TARGET_COMMENT
        else:
            comment_tag = config.LASTFM_TARGET_COMMENT

        query = f"{artist} {title}"
        print(f"  Searching slskd: {query}")
        results = slskd.search(query)

        best = _best_track_result(results)
        if not best:
            print(f"  No downloadable audio found for {artist} - {title}")
            return None

        username = best['username']
        filename = best['file']['filename']
        size = best['file']['size']
        basename = os.path.basename(filename.replace('\\', '/'))
        bitrate = best['file'].get('bitRate') or '?'
        ext = os.path.splitext(basename)[1].upper().lstrip('.')
        print(f"  Best: {username} / {basename} ({ext}, {bitrate} kbps)")

        try:
            slskd.download(username, filename, size)
        except Exception as e:
            print(f"  Failed to queue download: {e}")
            return None

        if not slskd.wait_for_download(username, filename):
            print(f"  Download failed for {artist} - {title}")
            return None

        local_path = _find_file_in_dir(config.SLSKD_DOWNLOAD_DIR, username, basename)
        if not local_path:
            print(f"  Downloaded file not found on disk for {artist} - {title}")
            return None

        self.tagger.tag_track(
            local_path,
            artist,
            title,
            song_info.get('album', ''),
            song_info.get('release_date', '') or '',
            song_info.get('recording_mbid', '') or '',
            song_info.get('source', 'ListenBrainz'),
            is_album_recommendation=False,
        )

        dest = os.path.join(config.TEMP_DOWNLOAD_FOLDER, basename)
        os.makedirs(config.TEMP_DOWNLOAD_FOLDER, exist_ok=True)
        os.rename(local_path, dest)
        return dest

    async def download_album(self, album_info):
        importlib.reload(config)
        slskd = self._slskd()

        artist = album_info['artist']
        album = album_info['album']

        query = f"{artist} {album}"
        print(f"  Searching slskd for album: {query}")
        results = slskd.search(query, timeout=45, file_limit=500)

        username, files = _best_album_folder(results)
        if not username or not files:
            print(f"  No album folder found for {artist} - {album}")
            return []

        print(f"  Downloading {len(files)} tracks from {username}")
        downloaded = []
        for f in files:
            filename = f['filename']
            size = f['size']
            basename = os.path.basename(filename.replace('\\', '/'))
            try:
                slskd.download(username, filename, size)
            except Exception as e:
                print(f"  Failed to queue {basename}: {e}")
                continue

            if slskd.wait_for_download(username, filename, timeout=300):
                local_path = _find_file_in_dir(config.SLSKD_DOWNLOAD_DIR, username, basename)
                if local_path:
                    self.tagger.tag_track(
                        local_path,
                        artist,
                        os.path.splitext(basename)[0],
                        album,
                        album_info.get('release_date', '') or '',
                        '',
                        'ListenBrainz',
                        is_album_recommendation=True,
                    )
                    dest = os.path.join(config.TEMP_DOWNLOAD_FOLDER, basename)
                    os.makedirs(config.TEMP_DOWNLOAD_FOLDER, exist_ok=True)
                    os.rename(local_path, dest)
                    downloaded.append(dest)
            else:
                print(f"  Timed out waiting for {basename}")

        return downloaded
