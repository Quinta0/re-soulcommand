import os
import time
import uuid

import requests

AUDIO_EXTENSIONS = {'.flac', '.mp3', '.ogg', '.m4a', '.aac', '.opus', '.wav', '.wv'}


def _file_ext(filename):
    return os.path.splitext(filename.replace('\\', '/').split('/')[-1])[1].lower()


def is_audio_file(filename):
    return _file_ext(filename) in AUDIO_EXTENSIONS


def score_file(f):
    ext = _file_ext(f.get('filename', ''))
    format_score = {'.flac': 100, '.mp3': 80, '.ogg': 60, '.m4a': 60, '.aac': 50, '.opus': 55}.get(ext, 0)
    bitrate = f.get('bitRate') or 0
    return format_score * 1000 + bitrate


class SlskdAPI:
    def __init__(self, url, api_key):
        self.url = url.rstrip('/')
        self.headers = {'X-API-Key': api_key, 'Content-Type': 'application/json'}

    def _get(self, path, **kwargs):
        return requests.get(f'{self.url}{path}', headers=self.headers, timeout=30, **kwargs)

    def _post(self, path, json=None, **kwargs):
        return requests.post(f'{self.url}{path}', headers=self.headers, json=json, timeout=30, **kwargs)

    def _delete(self, path, **kwargs):
        return requests.delete(f'{self.url}{path}', headers=self.headers, timeout=10, **kwargs)

    def search(self, query, timeout=30, file_limit=200):
        """Run a search, wait for results, return list of {'username', 'file', 'peer'} dicts."""
        search_id = str(uuid.uuid4())
        resp = self._post('/api/v0/searches', json={
            'id': search_id,
            'searchText': query,
            'fileLimit': file_limit,
            'filterResponses': True,
            'minimumResponseFileCount': 1,
        })
        resp.raise_for_status()

        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(3)
            try:
                status = self._get(f'/api/v0/searches/{search_id}')
                if status.ok:
                    data = status.json()
                    if data.get('isComplete') or data.get('state') in ('Completed', 'Stopped'):
                        break
            except Exception:
                pass

        results = []
        try:
            resp = self._get(f'/api/v0/searches/{search_id}/responses')
            if resp.ok:
                for response in resp.json():
                    username = response.get('username', '')
                    for f in response.get('files', []):
                        results.append({'username': username, 'file': f, 'peer': response})
        except Exception as e:
            print(f"Error fetching search results: {e}")

        try:
            self._delete(f'/api/v0/searches/{search_id}')
        except Exception:
            pass

        return results

    def download(self, username, filename, size):
        """Queue a single file download from a peer."""
        encoded = requests.utils.quote(username, safe='')
        resp = self._post(
            f'/api/v0/transfers/downloads/{encoded}',
            json=[{'filename': filename, 'size': size}]
        )
        resp.raise_for_status()
        return resp.json() if resp.content else {}

    def get_user_downloads(self, username):
        encoded = requests.utils.quote(username, safe='')
        resp = self._get(f'/api/v0/transfers/downloads/{encoded}')
        resp.raise_for_status()
        return resp.json()

    def wait_for_download(self, username, filename, timeout=120, poll_interval=5):
        """Poll until the download of `filename` from `username` completes. Returns True on success."""
        deadline = time.time() + timeout
        seen_in_api = False
        not_found_streak = 0
        while time.time() < deadline:
            time.sleep(poll_interval)
            try:
                transfers = self.get_user_downloads(username)
                found_in_api = False
                for entry in transfers if isinstance(transfers, list) else []:
                    if not isinstance(entry, dict):
                        continue
                    # Flat list format
                    if entry.get('filename') == filename:
                        found_in_api = True
                        state = entry.get('state', '')
                        if 'Succeeded' in state:
                            return True
                        if any(x in state for x in ('Errored', 'Cancelled', 'TimedOut')):
                            print(f"  Download ended with state: {state}")
                            return False
                    # Nested by directory format
                    for f in entry.get('files', []):
                        if f.get('filename') == filename:
                            found_in_api = True
                            state = f.get('state', '')
                            if 'Succeeded' in state:
                                return True
                            if any(x in state for x in ('Errored', 'Cancelled', 'TimedOut')):
                                print(f"  Download ended with state: {state}")
                                return False
                if found_in_api:
                    seen_in_api = True
                    not_found_streak = 0
                elif seen_in_api:
                    # Transfer was previously visible but has now vanished — slskd cleaned it up after success
                    not_found_streak += 1
                    if not_found_streak >= 2:
                        return True
            except Exception as e:
                print(f"  Error polling download status: {e}")

        print(f"  Download timed out after {timeout}s for: {filename}")
        return False
