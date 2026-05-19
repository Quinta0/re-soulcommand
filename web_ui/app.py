from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import subprocess
import re
import asyncio
import sys
import traceback
import time
import threading
import json
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import *
from apis.lastfm_api import LastFmAPI
from apis.listenbrainz_api import ListenBrainzAPI
from apis.navidrome_api import NavidromeAPI
from downloaders.slskd_downloader import SlskdDownloader
from utils import Tagger
import uuid

app = Flask(__name__)

CRON_FILE = '/etc/cron.d/re-soulcommand-cron'
DEFAULT_CRON_SCHEDULE = "0 0 * * 2"
CRON_COMMAND = "root cd /app && /usr/local/bin/python3 /app/re-soulcommand.py >> /proc/1/fd/1 2>&1"

downloads_queue = {}

tagger_global = Tagger(ALBUM_RECOMMENDATION_COMMENT)
navidrome_api_global = NavidromeAPI(
    root_nd=ROOT_ND,
    user_nd=USER_ND,
    password_nd=PASSWORD_ND,
    music_library_path=MUSIC_LIBRARY_PATH,
    target_comment=TARGET_COMMENT,
    lastfm_target_comment=LASTFM_TARGET_COMMENT,
    album_recommendation_comment=ALBUM_RECOMMENDATION_COMMENT,
    listenbrainz_enabled=LISTENBRAINZ_ENABLED,
    lastfm_enabled=LASTFM_ENABLED,
)


def write_cron_file(schedule):
    with open(CRON_FILE, 'w', newline='\n') as f:
        f.write(f"{schedule} {CRON_COMMAND}\n")
    os.chmod(CRON_FILE, 0o644)


def get_current_cron_schedule():
    try:
        with open(CRON_FILE, 'r') as f:
            cron_line = f.read().strip()
        match = re.match(r"^(\S+\s+\S+\s+\S+\s+\S+\s+\S+)\s+.*", cron_line)
        if match:
            return match.group(1)
    except FileNotFoundError:
        return DEFAULT_CRON_SCHEDULE
    return DEFAULT_CRON_SCHEDULE


def update_download_status(download_id, status, message=None, title=None,
                           current_track_count=None, total_track_count=None):
    if download_id in downloads_queue:
        item = downloads_queue[download_id]
        item['status'] = status
        if message is not None:
            item['message'] = message
        if title is not None:
            item['title'] = title
        if current_track_count is not None:
            item['current_track_count'] = current_track_count
        if total_track_count is not None:
            item['total_track_count'] = total_track_count
    else:
        downloads_queue[download_id] = {
            'id': download_id,
            'artist': 'Playlist Download',
            'title': title or f'Download {download_id[:8]}...',
            'status': status,
            'start_time': datetime.now().isoformat(),
            'message': message,
            'current_track_count': current_track_count,
            'total_track_count': total_track_count,
        }


DOWNLOAD_STATUS_DIR = "/tmp/recommand_download_status"
DOWNLOAD_QUEUE_CLEANUP_INTERVAL_SECONDS = 300


def poll_download_statuses():
    print("Download status poller started.")
    while True:
        try:
            if os.path.exists(DOWNLOAD_STATUS_DIR):
                for filename in os.listdir(DOWNLOAD_STATUS_DIR):
                    if not filename.endswith(".json"):
                        continue
                    download_id = filename.split(".")[0]
                    filepath = os.path.join(DOWNLOAD_STATUS_DIR, filename)
                    try:
                        with open(filepath, 'r') as f:
                            status_data = json.load(f)
                        update_download_status(
                            download_id,
                            status_data.get('status'),
                            status_data.get('message'),
                            status_data.get('title'),
                            status_data.get('current_track_count'),
                            status_data.get('total_track_count'),
                        )
                        if status_data.get('status') in ('completed', 'failed'):
                            if download_id in downloads_queue:
                                start = datetime.fromisoformat(downloads_queue[download_id]['start_time'])
                                if (datetime.now() - start).total_seconds() > DOWNLOAD_QUEUE_CLEANUP_INTERVAL_SECONDS:
                                    del downloads_queue[download_id]
                                    os.remove(filepath)
                    except Exception as e:
                        print(f"Error processing status file {filepath}: {e}")
        except Exception as e:
            print(f"Error in poll_download_statuses: {e}")
        time.sleep(5)


# --- Routes ---

@app.route('/api/download_queue', methods=['GET'])
def get_download_queue():
    if os.path.exists(DOWNLOAD_STATUS_DIR):
        for filename in os.listdir(DOWNLOAD_STATUS_DIR):
            if not filename.endswith(".json"):
                continue
            download_id = filename.split(".")[0]
            filepath = os.path.join(DOWNLOAD_STATUS_DIR, filename)
            try:
                with open(filepath, 'r') as f:
                    status_data = json.load(f)
                update_download_status(
                    download_id,
                    status_data.get('status'),
                    status_data.get('message'),
                    status_data.get('title'),
                    status_data.get('current_track_count'),
                    status_data.get('total_track_count'),
                )
            except Exception as e:
                print(f"Error reading status file {filepath}: {e}")
    return jsonify({"status": "success", "queue": list(downloads_queue.values())})


@app.route('/')
def index():
    current_cron = get_current_cron_schedule()
    cron_parts = current_cron.split()
    try:
        cron_hour = int(cron_parts[1]) if len(cron_parts) >= 5 else 0
        cron_day = int(cron_parts[4]) if len(cron_parts) >= 5 else 2
    except (ValueError, IndexError):
        cron_hour, cron_day = 0, 2
    return render_template('index.html', cron_schedule=current_cron, cron_hour=cron_hour, cron_day=cron_day)


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'assets'), 'favicon.png', mimetype='image/png')


@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(os.path.join(app.root_path, 'assets'), filename)


@app.route('/api/config', methods=['GET'])
def get_config():
    return jsonify({
        "ROOT_ND": "••••••••" if ROOT_ND else "",
        "USER_ND": USER_ND,
        "PASSWORD_ND": "••••••••" if PASSWORD_ND else "",
        "LISTENBRAINZ_ENABLED": LISTENBRAINZ_ENABLED,
        "TOKEN_LB": "••••••••" if TOKEN_LB else "",
        "USER_LB": USER_LB,
        "LASTFM_ENABLED": LASTFM_ENABLED,
        "LASTFM_API_KEY": "••••••••" if LASTFM_API_KEY else "",
        "LASTFM_API_SECRET": "••••••••" if LASTFM_API_SECRET else "",
        "LASTFM_USERNAME": LASTFM_USERNAME,
        "SLSKD_URL": SLSKD_URL,
        "SLSKD_API_KEY": "••••••••" if SLSKD_API_KEY else "",
        "SLSKD_DOWNLOAD_DIR": SLSKD_DOWNLOAD_DIR,
        "HIDE_FRESH_RELEASES": HIDE_FRESH_RELEASES,
        "CRON_SCHEDULE": get_current_cron_schedule(),
    })


@app.route('/api/update_config', methods=['POST'])
def update_config():
    data = request.get_json()
    try:
        with open('config.py', 'r') as f:
            current_config_content = f.read()

        sensitive_fields = {'ROOT_ND', 'PASSWORD_ND', 'TOKEN_LB', 'LASTFM_API_KEY',
                            'LASTFM_API_SECRET', 'LASTFM_SESSION_KEY', 'SLSKD_API_KEY'}

        for key, value in data.items():
            if key in sensitive_fields and value == '••••••••':
                if key in globals():
                    globals()[key] = globals()[key]
                continue

            if key in {'LISTENBRAINZ_ENABLED', 'LASTFM_ENABLED', 'HIDE_FRESH_RELEASES', 'ALBUM_RECOMMENDATION_ENABLED'}:
                new_value_str = str(value)
            else:
                new_value_str = f'"{value}"' if isinstance(value, str) else str(value)

            globals()[key] = value
            pattern = re.compile(rf'^{key}\s*=\s*.*$', re.MULTILINE)
            if pattern.search(current_config_content):
                current_config_content = pattern.sub(f'{key} = {new_value_str}', current_config_content)

        with open('config.py', 'w') as f:
            f.write(current_config_content)

        global navidrome_api_global
        navidrome_api_global = NavidromeAPI(
            root_nd=globals().get('ROOT_ND', ''),
            user_nd=globals().get('USER_ND', ''),
            password_nd=globals().get('PASSWORD_ND', ''),
            music_library_path=globals().get('MUSIC_LIBRARY_PATH', ''),
            target_comment=globals().get('TARGET_COMMENT', ''),
            lastfm_target_comment=globals().get('LASTFM_TARGET_COMMENT', ''),
            album_recommendation_comment=globals().get('ALBUM_RECOMMENDATION_COMMENT', ''),
            listenbrainz_enabled=globals().get('LISTENBRAINZ_ENABLED', False),
            lastfm_enabled=globals().get('LASTFM_ENABLED', False),
        )

        return jsonify({"status": "success", "message": "Configuration updated successfully."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Failed to update configuration: {e}"}), 500


@app.route('/api/update_cron', methods=['POST'])
def update_cron():
    data = request.get_json()
    new_schedule = data.get('schedule')
    if not new_schedule:
        return jsonify({"status": "error", "message": "Cron schedule is required"}), 400
    try:
        write_cron_file(new_schedule)
        return jsonify({"status": "success", "message": "Cron schedule updated."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Failed to update cron: {e}"}), 500


@app.route('/api/toggle_cron', methods=['POST'])
def toggle_cron():
    data = request.get_json()
    disabled = data.get('disabled', False)
    try:
        if disabled:
            if os.path.exists(CRON_FILE):
                os.remove(CRON_FILE)
            return jsonify({"status": "success", "message": "Automatic downloads disabled."})
        else:
            if not os.path.exists(CRON_FILE):
                write_cron_file(DEFAULT_CRON_SCHEDULE)
                return jsonify({"status": "success", "message": "Automatic downloads re-enabled."})
            return jsonify({"status": "success", "message": "Automatic downloads already enabled."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error toggling cron: {e}"}), 500


@app.route('/api/get_listenbrainz_playlist', methods=['GET'])
def get_listenbrainz_playlist():
    if not USER_LB or not TOKEN_LB:
        return jsonify({"status": "error", "message": "ListenBrainz credentials not configured."}), 400
    try:
        listenbrainz_api = ListenBrainzAPI(ROOT_LB, TOKEN_LB, USER_LB, LISTENBRAINZ_ENABLED)
        lb_recs = asyncio.run(listenbrainz_api.get_listenbrainz_recommendations())
        if lb_recs:
            return jsonify({"status": "success", "recommendations": lb_recs})
        return jsonify({"status": "info", "message": "No new ListenBrainz recommendations found."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/trigger_listenbrainz_download', methods=['POST'])
def trigger_listenbrainz_download():
    try:
        listenbrainz_api = ListenBrainzAPI(ROOT_LB, TOKEN_LB, USER_LB, LISTENBRAINZ_ENABLED)
        recs = asyncio.run(listenbrainz_api.get_listenbrainz_recommendations())
        if not recs:
            return jsonify({"status": "error", "message": "No ListenBrainz recommendations found."}), 400

        download_id = str(uuid.uuid4())
        downloads_queue[download_id] = {
            'id': download_id,
            'artist': 'ListenBrainz Playlist',
            'title': 'Multiple Tracks',
            'status': 'in_progress',
            'start_time': datetime.now().isoformat(),
            'message': 'Download initiated.',
            'current_track_count': 0,
            'total_track_count': None,
        }
        subprocess.Popen([
            sys.executable, '/app/re-soulcommand.py',
            '--source', 'listenbrainz',
            '--bypass-playlist-check',
            '--download-id', download_id,
        ])
        return jsonify({"status": "info", "message": "ListenBrainz download initiated."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/get_lastfm_playlist', methods=['GET'])
def get_lastfm_playlist():
    if not LASTFM_USERNAME or not LASTFM_API_KEY or not LASTFM_API_SECRET:
        return jsonify({"status": "error", "message": "Last.fm credentials not configured."}), 400
    try:
        lastfm_api = LastFmAPI(LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME,
                               LASTFM_PASSWORD, LASTFM_SESSION_KEY, LASTFM_ENABLED)
        lf_recs = asyncio.run(lastfm_api.get_lastfm_recommendations())
        if lf_recs:
            return jsonify({"status": "success", "recommendations": lf_recs})
        return jsonify({"status": "info", "message": "No Last.fm recommendations found."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/trigger_lastfm_download', methods=['POST'])
def trigger_lastfm_download():
    try:
        lastfm_api = LastFmAPI(LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME,
                               LASTFM_PASSWORD, LASTFM_SESSION_KEY, LASTFM_ENABLED)
        recs = asyncio.run(lastfm_api.get_lastfm_recommendations())
        if not recs:
            return jsonify({"status": "error", "message": "No Last.fm recommendations found."}), 400

        download_id = str(uuid.uuid4())
        downloads_queue[download_id] = {
            'id': download_id,
            'artist': 'Last.fm Playlist',
            'title': 'Multiple Tracks',
            'status': 'in_progress',
            'start_time': datetime.now().isoformat(),
            'message': 'Download initiated.',
            'current_track_count': 0,
            'total_track_count': None,
        }
        subprocess.Popen([
            sys.executable, '/app/re-soulcommand.py',
            '--source', 'lastfm',
            '--download-id', download_id,
        ])
        return jsonify({"status": "info", "message": "Last.fm download initiated."})
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/get_fresh_releases', methods=['GET'])
async def get_fresh_releases():
    if not USER_LB or not TOKEN_LB:
        return jsonify({"status": "error", "message": "ListenBrainz credentials not configured."}), 400
    try:
        listenbrainz_api = ListenBrainzAPI(ROOT_LB, TOKEN_LB, USER_LB, LISTENBRAINZ_ENABLED)
        data = await listenbrainz_api.get_fresh_releases()
        releases = data.get('payload', {}).get('releases', [])
        if not releases:
            return jsonify({"status": "info", "message": "No fresh releases found."})
        return jsonify({"status": "success", "releases": releases})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/trigger_fresh_release_download', methods=['POST'])
def trigger_fresh_release_download():
    try:
        data = request.get_json()
        artist = data.get('artist')
        album = data.get('album')
        release_date = data.get('release_date')

        if not artist or not album:
            return jsonify({"status": "error", "message": "Artist and album are required"}), 400

        download_id = str(uuid.uuid4())
        downloads_queue[download_id] = {
            'id': download_id,
            'artist': artist,
            'title': album,
            'status': 'in_progress',
            'start_time': datetime.now().isoformat(),
            'message': 'Download initiated.',
        }

        album_info = {'artist': artist, 'album': album, 'release_date': release_date}

        def run_download():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tagger = Tagger(ALBUM_RECOMMENDATION_COMMENT)
                downloader = SlskdDownloader(tagger)
                files = loop.run_until_complete(downloader.download_album(album_info))
                if files:
                    navidrome_api_global.organize_music_files(TEMP_DOWNLOAD_FOLDER, MUSIC_LIBRARY_PATH)
                    update_download_status(download_id, 'completed', f"Downloaded {len(files)} tracks.")
                else:
                    update_download_status(download_id, 'failed', 'No tracks found on Soulseek.')
            except Exception as e:
                update_download_status(download_id, 'failed', str(e))
            finally:
                loop.close()

        threading.Thread(target=run_download, daemon=True).start()
        return jsonify({"status": "info", "message": f"Album download started for {artist} - {album}."})

    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/trigger_track_download', methods=['POST'])
def trigger_track_download():
    try:
        data = request.get_json()
        artist = data.get('artist')
        title = data.get('title')
        lb_recommendation = data.get('lb_recommendation', False)
        source = data.get('source', 'Manual')

        if not artist or not title:
            return jsonify({"status": "error", "message": "Artist and title are required"}), 400

        download_id = str(uuid.uuid4())
        downloads_queue[download_id] = {
            'id': download_id,
            'artist': artist,
            'title': title,
            'status': 'in_progress',
            'start_time': datetime.now().isoformat(),
            'message': 'Download initiated.',
        }

        track_info = {
            'artist': artist, 'title': title, 'album': '',
            'release_date': '', 'recording_mbid': '', 'source': source,
        }

        def run_download():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                tagger = Tagger(ALBUM_RECOMMENDATION_COMMENT)
                downloader = SlskdDownloader(tagger)
                path = loop.run_until_complete(downloader.download_track(track_info, lb_recommendation=lb_recommendation))
                if path:
                    navidrome_api_global.organize_music_files(TEMP_DOWNLOAD_FOLDER, MUSIC_LIBRARY_PATH)
                    update_download_status(download_id, 'completed', 'Download complete.')
                else:
                    update_download_status(download_id, 'failed', 'Track not found on Soulseek.')
            except Exception as e:
                update_download_status(download_id, 'failed', str(e))
            finally:
                loop.close()

        threading.Thread(target=run_download, daemon=True).start()
        return jsonify({"status": "info", "message": f"Download started: {artist} - {title}"})

    except Exception as e:
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/submit_listenbrainz_feedback', methods=['POST'])
def submit_listenbrainz_feedback():
    try:
        data = request.get_json()
        recording_mbid = data.get('recording_mbid')
        score = data.get('score')

        if not recording_mbid or score not in [1, -1]:
            return jsonify({"status": "error", "message": "Valid recording_mbid and score required"}), 400
        if not TOKEN_LB or not USER_LB:
            return jsonify({"status": "error", "message": "ListenBrainz credentials not configured"}), 400

        listenbrainz_api = ListenBrainzAPI(ROOT_LB, TOKEN_LB, USER_LB, LISTENBRAINZ_ENABLED)
        asyncio.run(listenbrainz_api.submit_feedback(recording_mbid, score))
        feedback_type = "positive" if score == 1 else "negative"
        return jsonify({"status": "success", "message": f"{feedback_type.capitalize()} feedback submitted."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/submit_lastfm_feedback', methods=['POST'])
def submit_lastfm_feedback():
    try:
        data = request.get_json()
        track = data.get('track')
        artist = data.get('artist')

        if not track or not artist:
            return jsonify({"status": "error", "message": "Track and artist are required"}), 400
        if not LASTFM_API_KEY or not LASTFM_API_SECRET or not LASTFM_SESSION_KEY:
            return jsonify({"status": "error", "message": "Last.fm credentials not configured"}), 400

        lastfm_api = LastFmAPI(LASTFM_API_KEY, LASTFM_API_SECRET, LASTFM_USERNAME,
                               LASTFM_PASSWORD, LASTFM_SESSION_KEY, LASTFM_ENABLED)
        lastfm_api.love_track(track, artist)
        return jsonify({"status": "success", "message": "Track loved on Last.fm."})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.route('/api/create_smart_playlists', methods=['POST'])
def create_smart_playlists():
    try:
        music_library_path = MUSIC_LIBRARY_PATH
        if not music_library_path or music_library_path == "/path/to/music":
            return jsonify({"status": "error", "message": "Music library path not configured."}), 400
        if not os.path.exists(music_library_path):
            return jsonify({"status": "error", "message": f"Path does not exist: {music_library_path}"}), 400

        templates = []
        if LISTENBRAINZ_ENABLED:
            templates.append({"filename": "lb.nsp", "name": "ListenBrainz Recommendations",
                               "comment_value": TARGET_COMMENT})
        if LASTFM_ENABLED:
            templates.append({"filename": "lastfm.nsp", "name": "Last.fm Recommendations",
                               "comment_value": LASTFM_TARGET_COMMENT})

        if not templates:
            return jsonify({"status": "info", "message": "No sources enabled."})

        created = []
        for t in templates:
            nsp = {"name": t["name"], "all": [{"is": {"comment": t["comment_value"]}}],
                   "sort": "title", "order": "asc", "limit": 10000}
            path = os.path.join(music_library_path, t["filename"])
            with open(path, 'w') as f:
                json.dump(nsp, f, indent=2)
            created.append(t["filename"])

        return jsonify({"status": "success", "message": f"Created: {', '.join(created)}", "created_files": created})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"status": "error", "message": f"Error: {e}"}), 500


@app.errorhandler(Exception)
def handle_exception(e):
    print(f"Unhandled exception: {e}", file=sys.stderr)
    return jsonify({"status": "error", "message": "An unexpected error occurred.", "details": str(e)}), 500


if __name__ == '__main__':
    download_poller_thread = threading.Thread(target=poll_download_statuses, daemon=True)
    download_poller_thread.start()
    app.run(host='0.0.0.0', port=5000, debug=True)
