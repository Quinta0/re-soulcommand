# re-soulcommand

<p align="center">
  <img src="web_ui/assets/logo.svg" width="200" alt="re-soulcommand Logo">
</p>

**re-soulcommand** is a fork of [re-command](https://github.com/Snapyou2/re-command) stripped of its bloat and rebuilt around [slskd](https://github.com/slskd/slskd) (a Soulseek daemon with a REST API) as the sole download backend. It keeps the Navidrome integration, ListenBrainz/Last.fm recommendations, fresh releases, cron scheduling, and the web interface — but drops Deezer, LLM suggestions, library-maintenance cleanup, and the Download-from-Link feature.

## What changed from re-command

| Feature | re-command | re-soulcommand |
|---------|-----------|----------------|
| Download backend | Streamrip / Deemix (Deezer) | slskd (Soulseek) |
| LLM suggestions | ✔ | ✘ |
| Download from Link | ✔ | ✘ |
| Library maintenance / cleanup | ✔ | ✘ |
| Track previews | ✔ | ✘ |
| ListenBrainz recommendations | ✔ | ✔ |
| Last.fm recommendations | ✔ | ✔ |
| Fresh releases | ✔ | ✔ |
| Navidrome organisation | ✔ | ✔ |
| Cron scheduling | ✔ | ✔ |
| Docker | ✔ | ✔ |

## Prerequisites

- [Docker](https://www.docker.com/get-started) and [Docker Compose](https://docs.docker.com/compose/) installed
- A running [slskd](https://github.com/slskd/slskd) instance with the REST API enabled
- A running [Navidrome](https://www.navidrome.org/) instance (optional — only needed for library scanning)
- A [ListenBrainz](https://listenbrainz.org/) account and/or [Last.fm](https://www.last.fm) API account for recommendations

## Quick Start with Docker Compose

### 1. Clone the repository

```bash
git clone https://github.com/ceemoo91/re-soulcommand.git
cd re-soulcommand
```

### 2. Configure volumes in `docker/docker-compose.yml`

Edit the volumes section to match your paths:

```yaml
volumes:
  - /your/music/library:/app/music
  - /your/music/library/.tempfolder:/app/temp_downloads
  - /your/slskd/downloads:/app/slskd_downloads:ro
```

- `/app/music` — your Navidrome music library root
- `/app/temp_downloads` — staging area; downloaded files are moved here before being organised into the library
- `/app/slskd_downloads` — mount the slskd download directory **read-only** so re-soulcommand can read completed files

### 3. (Optional) Pre-configure via environment variables

You can set credentials in `docker/docker-compose.yml` or via a `.env` file instead of the web UI:

```env
RECOMMAND_SLSKD_URL=http://host.docker.internal:5030
RECOMMAND_SLSKD_API_KEY=your-slskd-api-key
RECOMMAND_SLSKD_DOWNLOAD_DIR=/app/slskd_downloads

RECOMMAND_LISTENBRAINZ_ENABLED=true
RECOMMAND_TOKEN_LB=your-listenbrainz-token
RECOMMAND_USER_LB=your-listenbrainz-username

RECOMMAND_LASTFM_ENABLED=true
RECOMMAND_LASTFM_API_KEY=your-lastfm-api-key
RECOMMAND_LASTFM_API_SECRET=your-lastfm-api-secret
RECOMMAND_LASTFM_USERNAME=your-lastfm-username

RECOMMAND_ROOT_ND=http://your-navidrome:4533
RECOMMAND_USER_ND=admin
RECOMMAND_PASSWORD_ND=your-password
```

### 4. Build and start

```bash
cd docker
docker compose up -d --build
```

### 5. Open the web interface

Navigate to `http://localhost:5000`. If you didn't set environment variables, open Settings (gear icon, top-left) and fill in your credentials there, then save.

## slskd Setup

re-soulcommand talks to slskd via its REST API. To enable it in slskd:

1. Open the slskd web UI → **Options** → **Remote Control**
2. Enable the API and create an API key
3. Note the URL (default: `http://localhost:5030`) and paste both into re-soulcommand's Settings

The slskd download directory (set under slskd's **Downloads** option) must be the same path mounted into the container at `/app/slskd_downloads`.

## Usage

### Web interface

| Action | How |
|--------|-----|
| Discover & preview ListenBrainz playlist | Click **Discover Weekly Playlist** in the ListenBrainz section |
| Download the full ListenBrainz playlist | Click **Download Weekly Playlist** or **Download all** after discovering |
| Discover & download Last.fm playlist | Same buttons in the Last.fm section |
| Download a single track | Click the download icon on any playlist item |
| Download a fresh release album | Click **Download** on a carousel card in Fresh Releases |
| Like / dislike a track | Click the heart / broken-heart icon (submits feedback to ListenBrainz or Last.fm) |
| Create Navidrome smart playlists | Settings → Maintenance → **Create Smart Playlists** |
| Schedule automatic downloads | Settings → Automation (pick day + hour, or disable) |

### Command line

```bash
# Download this week's ListenBrainz recommendations
python re-soulcommand.py --source listenbrainz

# Download Last.fm recommendations
python re-soulcommand.py --source lastfm

# Download both sources
python re-soulcommand.py --source all

# Download fresh release albums from ListenBrainz
python re-soulcommand.py --source fresh_releases

# Force re-download even if the playlist hasn't changed
python re-soulcommand.py --source listenbrainz --bypass-playlist-check
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `RECOMMAND_ROOT_ND` | _(empty)_ | Navidrome server URL |
| `RECOMMAND_USER_ND` | _(empty)_ | Navidrome username |
| `RECOMMAND_PASSWORD_ND` | _(empty)_ | Navidrome password |
| `RECOMMAND_SLSKD_URL` | _(empty)_ | slskd base URL, e.g. `http://host.docker.internal:5030` |
| `RECOMMAND_SLSKD_API_KEY` | _(empty)_ | slskd API key |
| `RECOMMAND_SLSKD_DOWNLOAD_DIR` | `/app/slskd_downloads` | Path where slskd saves completed files (as seen inside the container) |
| `RECOMMAND_LISTENBRAINZ_ENABLED` | `False` | Enable ListenBrainz |
| `RECOMMAND_TOKEN_LB` | _(empty)_ | ListenBrainz API token |
| `RECOMMAND_USER_LB` | _(empty)_ | ListenBrainz username |
| `RECOMMAND_LASTFM_ENABLED` | `False` | Enable Last.fm |
| `RECOMMAND_LASTFM_API_KEY` | _(empty)_ | Last.fm API key |
| `RECOMMAND_LASTFM_API_SECRET` | _(empty)_ | Last.fm API secret |
| `RECOMMAND_LASTFM_USERNAME` | _(empty)_ | Last.fm username |
| `RECOMMAND_LASTFM_PASSWORD` | _(empty)_ | Last.fm password (for mobile auth) |
| `RECOMMAND_LASTFM_SESSION_KEY` | _(empty)_ | Last.fm session key (skips re-auth) |
| `RECOMMAND_TARGET_COMMENT` | `lb_recommendation` | Comment tag written to ListenBrainz downloads |
| `RECOMMAND_LASTFM_TARGET_COMMENT` | `lastfm_recommendation` | Comment tag written to Last.fm downloads |
| `RECOMMAND_ALBUM_RECOMMENDATION_COMMENT` | `album_recommendation` | Comment tag written to fresh-release downloads |
| `RECOMMAND_ALBUM_RECOMMENDATION_ENABLED` | `false` | Tag fresh-release downloads with `album_recommendation` |
| `RECOMMAND_HIDE_FRESH_RELEASES` | `false` | Hide the Fresh Releases carousel |
| `RECOMMAND_FRESH_RELEASES_CACHE_DURATION` | `300` | Seconds to cache the fresh-releases response |

## How downloads work

1. **Search** — re-soulcommand sends a search query (`artist title`) to slskd and waits for results
2. **Score** — results are ranked by format (FLAC > MP3 > others) and bitrate; locked files are skipped
3. **Download** — the best match is queued in slskd
4. **Poll** — the app polls slskd's transfer API until the download completes (up to 10 minutes)
5. **Tag** — Mutagen writes the recommendation comment tag to the file
6. **Organise** — the file is moved to `MUSIC_LIBRARY_PATH/Artist/Album/filename`

Album downloads (fresh releases) follow the same steps but group results by `(username, folder)` and pick the folder with the most audio files.

## Local Development Setup

```bash
git clone https://github.com/ceemoo91/re-soulcommand.git
cd re-soulcommand
pip install -r requirements.txt
# Fill in config.py
python re-soulcommand.py          # CLI
python -m gunicorn --bind 0.0.0.0:5000 web_ui.app:app  # web UI
```

## Troubleshooting

**Downloads never complete**
- Verify slskd URL and API key in Settings
- Check that `SLSKD_DOWNLOAD_DIR` (inside the container) matches the mount point for slskd's downloads folder
- Make sure slskd has an active Soulseek connection (check the slskd UI)

**No search results**
- The query times out after 30 s by default; try less-popular tracks first
- Ensure your Soulseek account is not banned or rate-limited

**Container can't reach slskd**
- If slskd runs on the host, use `http://host.docker.internal:<port>` as the URL (the compose file already adds the `host.docker.internal` extra host)

**Web interface not loading**
- Check port 5000 is free: `docker ps`
- Check logs: `docker logs re-soulcommand-container`

## Credits

Forked from [re-command](https://github.com/Snapyou2/re-command) by Snapyou2. Original project license applies.
