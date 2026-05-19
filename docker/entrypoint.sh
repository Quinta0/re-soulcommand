#!/bin/bash

export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt

# Fix permissions for mounted volumes
chown -R 1000:1000 /app/music /app/temp_downloads

# Generate config.py from environment variables
echo "# Generated config.py from Docker environment variables" > config.py
echo "import os" >> config.py
echo "" >> config.py

# Navidrome Configuration
echo "ROOT_ND = os.getenv(\"ROOT_ND\", \"${RECOMMAND_ROOT_ND:-}\")" >> config.py
echo "USER_ND = os.getenv(\"USER_ND\", \"${RECOMMAND_USER_ND:-}\")" >> config.py
echo "PASSWORD_ND = os.getenv(\"PASSWORD_ND\", \"${RECOMMAND_PASSWORD_ND:-}\")" >> config.py
echo "MUSIC_LIBRARY_PATH = os.getenv(\"MUSIC_LIBRARY_PATH\", \"/app/music\")" >> config.py
echo "TEMP_DOWNLOAD_FOLDER = os.getenv(\"TEMP_DOWNLOAD_FOLDER\", \"/app/temp_downloads\")" >> config.py
echo "" >> config.py

# Soulseek (slskd) Configuration
echo "SLSKD_URL = os.getenv(\"SLSKD_URL\", \"${RECOMMAND_SLSKD_URL:-}\")" >> config.py
echo "SLSKD_API_KEY = os.getenv(\"SLSKD_API_KEY\", \"${RECOMMAND_SLSKD_API_KEY:-}\")" >> config.py
echo "SLSKD_DOWNLOAD_DIR = os.getenv(\"SLSKD_DOWNLOAD_DIR\", \"${RECOMMAND_SLSKD_DOWNLOAD_DIR:-/app/slskd_downloads}\")" >> config.py
echo "" >> config.py

# ListenBrainz API Configuration (Optional)
echo "LISTENBRAINZ_ENABLED = os.getenv(\"LISTENBRAINZ_ENABLED\", \"${RECOMMAND_LISTENBRAINZ_ENABLED:-False}\").lower() == \"true\"" >> config.py
echo "ROOT_LB = os.getenv(\"ROOT_LB\", \"${RECOMMAND_ROOT_LB:-https://api.listenbrainz.org}\")" >> config.py
echo "TOKEN_LB = os.getenv(\"TOKEN_LB\", \"${RECOMMAND_TOKEN_LB:-}\")" >> config.py
echo "USER_LB = os.getenv(\"USER_LB\", \"${RECOMMAND_USER_LB:-}\")" >> config.py
echo "" >> config.py

# Last.fm API Configuration (Optional)
echo "LASTFM_ENABLED = os.getenv(\"LASTFM_ENABLED\", \"${RECOMMAND_LASTFM_ENABLED:-False}\").lower() == \"true\"" >> config.py
echo "LASTFM_API_KEY = os.getenv(\"LASTFM_API_KEY\", \"${RECOMMAND_LASTFM_API_KEY:-}\")" >> config.py
echo "LASTFM_API_SECRET = os.getenv(\"LASTFM_API_SECRET\", \"${RECOMMAND_LASTFM_API_SECRET:-}\")" >> config.py
echo "LASTFM_USERNAME = os.getenv(\"LASTFM_USERNAME\", \"${RECOMMAND_LASTFM_USERNAME:-}\")" >> config.py
echo "LASTFM_PASSWORD = os.getenv(\"LASTFM_PASSWORD\", \"${RECOMMAND_LASTFM_PASSWORD:-}\")" >> config.py
echo "LASTFM_PASSWORD_HASH = os.getenv(\"LASTFM_PASSWORD_HASH\", \"${RECOMMAND_LASTFM_PASSWORD_HASH:-}\")" >> config.py
echo "LASTFM_SESSION_KEY = os.getenv(\"LASTFM_SESSION_KEY\", \"${RECOMMAND_LASTFM_SESSION_KEY:-}\")" >> config.py
echo "" >> config.py

# Album Recommendation Settings
echo "ALBUM_RECOMMENDATION_ENABLED = os.getenv(\"ALBUM_RECOMMENDATION_ENABLED\", \"${RECOMMAND_ALBUM_RECOMMENDATION_ENABLED:-false}\").lower() == \"true\"" >> config.py
echo "" >> config.py

# UI Visibility Settings
echo "HIDE_FRESH_RELEASES = os.getenv(\"HIDE_FRESH_RELEASES\", \"${RECOMMAND_HIDE_FRESH_RELEASES:-false}\").lower() == \"true\"" >> config.py
echo "" >> config.py

# Comment Tags for Playlist Creation
echo "TARGET_COMMENT = os.getenv(\"TARGET_COMMENT\", \"${RECOMMAND_TARGET_COMMENT:-lb_recommendation}\")" >> config.py
echo "LASTFM_TARGET_COMMENT = os.getenv(\"LASTFM_TARGET_COMMENT\", \"${RECOMMAND_LASTFM_TARGET_COMMENT:-lastfm_recommendation}\")" >> config.py
echo "ALBUM_RECOMMENDATION_COMMENT = os.getenv(\"ALBUM_RECOMMENDATION_COMMENT\", \"${RECOMMAND_ALBUM_RECOMMENDATION_COMMENT:-album_recommendation}\")" >> config.py
echo "" >> config.py

# History Tracking
echo "PLAYLIST_HISTORY_FILE = os.getenv(\"PLAYLIST_HISTORY_FILE\", \"/app/playlist_history.txt\")" >> config.py
echo "" >> config.py

# Caching for fresh releases (in seconds)
echo "FRESH_RELEASES_CACHE_DURATION = int(os.getenv(\"FRESH_RELEASES_CACHE_DURATION\", \"${RECOMMAND_FRESH_RELEASES_CACHE_DURATION:-300}\"))" >> config.py
echo "" >> config.py

# Set up cron job (runs every Tuesday at 00:00)
mkdir -p /app/logs
touch /app/logs/re-soulcommand.log
echo "0 0 * * 2 root cd /app && /usr/local/bin/python3 /app/re-soulcommand.py >> /proc/1/fd/1 2>&1" > /etc/cron.d/re-soulcommand-cron
chmod 0644 /etc/cron.d/re-soulcommand-cron

# Start syslog service (required for cron)
rsyslogd

# Give syslog a moment to start
sleep 2

# Start cron service
cron

# Execute the main command & keep container running
exec "$@"
