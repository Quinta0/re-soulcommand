#!/usr/bin/env python3

import asyncio
import os
import sys
import argparse
from tqdm import tqdm

from config import *
from apis.lastfm_api import LastFmAPI
from utils import update_status_file
from apis.listenbrainz_api import ListenBrainzAPI
from apis.navidrome_api import NavidromeAPI
from downloaders.slskd_downloader import SlskdDownloader
from utils import remove_empty_folders, Tagger


async def process_recommendations(source="all", bypass_playlist_check=False, download_id=None):
    print(f"Starting re-soulcommand for source: {source}...")

    tagger = Tagger()
    lastfm_api = LastFmAPI(
        api_key=LASTFM_API_KEY,
        api_secret=LASTFM_API_SECRET,
        username=LASTFM_USERNAME,
        password=LASTFM_PASSWORD,
        session_key=LASTFM_SESSION_KEY,
        lastfm_enabled=LASTFM_ENABLED
    )
    listenbrainz_api = ListenBrainzAPI(
        root_lb=ROOT_LB,
        token_lb=TOKEN_LB,
        user_lb=USER_LB,
        listenbrainz_enabled=LISTENBRAINZ_ENABLED
    )
    navidrome_api = NavidromeAPI(
        root_nd=ROOT_ND,
        user_nd=USER_ND,
        password_nd=PASSWORD_ND,
        music_library_path=MUSIC_LIBRARY_PATH,
        target_comment=TARGET_COMMENT,
        lastfm_target_comment=LASTFM_TARGET_COMMENT,
        album_recommendation_comment=ALBUM_RECOMMENDATION_COMMENT,
        listenbrainz_enabled=LISTENBRAINZ_ENABLED,
        lastfm_enabled=LASTFM_ENABLED
    )
    downloader = SlskdDownloader(tagger)

    all_recommendations = []

    if source in ["all", "listenbrainz"] and LISTENBRAINZ_ENABLED:
        print("\033[1;34m=== LISTENBRAINZ RECOMMENDATIONS ===\033[0m")
        if bypass_playlist_check or await listenbrainz_api.has_playlist_changed():
            lb_recs = await listenbrainz_api.get_listenbrainz_recommendations()
            if lb_recs:
                print(f"Found {len(lb_recs)} ListenBrainz recommendations.")
                all_recommendations.extend(lb_recs)
            else:
                print("No new ListenBrainz recommendations found.")
        else:
            print("ListenBrainz playlist unchanged. Skipping.")
    elif source == "listenbrainz":
        print("ListenBrainz is not enabled.")

    if source in ["all", "lastfm"] and LASTFM_ENABLED:
        print("\033[1;31m=== LAST.FM RECOMMENDATIONS ===\033[0m")
        lf_recs = await lastfm_api.get_lastfm_recommendations()
        if lf_recs:
            print(f"Found {len(lf_recs)} Last.fm recommendations.")
            all_recommendations.extend(lf_recs)
        else:
            print("No new Last.fm recommendations found.")
    elif source == "lastfm":
        print("Last.fm is not enabled.")

    # Deduplicate by (artist, title)
    seen = set()
    unique = []
    for rec in all_recommendations:
        key = (rec['artist'].lower(), rec['title'].lower())
        if key not in seen:
            unique.append(rec)
            seen.add(key)

    if not unique:
        print("No recommendations found.")
        update_status_file(download_id, "completed", "No recommendations found.", "No recommendations",
                           current_track_count=0, total_track_count=0)
        return 0, 0

    print(f"\033[1;33m=== DOWNLOADING {len(unique)} TRACKS ===\033[0m")
    update_status_file(download_id, "in_progress", f"Starting download of {len(unique)} tracks.",
                       "Downloading playlist", current_track_count=0, total_track_count=len(unique))

    downloaded_songs = []
    with tqdm(unique, desc="Downloading", unit="track") as pbar:
        for i, song_info in enumerate(pbar):
            tqdm.write(f"  {song_info['artist']} - {song_info['title']} [{song_info.get('source', '?')}]")
            try:
                lb_rec = song_info.get('source', '').lower() == 'listenbrainz'
                path = await downloader.download_track(song_info, lb_recommendation=lb_rec)
                if path:
                    downloaded_songs.append(song_info)
                    update_status_file(download_id, "in_progress",
                                       f"Downloaded {len(downloaded_songs)} of {len(unique)} tracks.",
                                       "Downloading playlist",
                                       current_track_count=len(downloaded_songs),
                                       total_track_count=len(unique))
            except Exception as e:
                tqdm.write(f"  Error: {song_info['artist']} - {song_info['title']}: {e}")

    if downloaded_songs:
        navidrome_api.organize_music_files(TEMP_DOWNLOAD_FOLDER, MUSIC_LIBRARY_PATH)

    downloaded_count = len(downloaded_songs)
    update_status_file(download_id, "completed",
                       f"Downloaded {downloaded_count} of {len(unique)} tracks.",
                       "Download complete",
                       current_track_count=downloaded_count,
                       total_track_count=len(unique))
    return downloaded_count, len(unique)


async def process_fresh_releases_albums(download_id=None):
    print("Starting fresh releases album download...")

    tagger = Tagger()
    listenbrainz_api = ListenBrainzAPI(
        root_lb=ROOT_LB,
        token_lb=TOKEN_LB,
        user_lb=USER_LB,
        listenbrainz_enabled=LISTENBRAINZ_ENABLED
    )
    navidrome_api = NavidromeAPI(
        root_nd=ROOT_ND,
        user_nd=USER_ND,
        password_nd=PASSWORD_ND,
        music_library_path=MUSIC_LIBRARY_PATH,
        target_comment=TARGET_COMMENT,
        lastfm_target_comment=LASTFM_TARGET_COMMENT,
        album_recommendation_comment=ALBUM_RECOMMENDATION_COMMENT,
        listenbrainz_enabled=LISTENBRAINZ_ENABLED,
        lastfm_enabled=LASTFM_ENABLED
    )
    downloader = SlskdDownloader(tagger)

    if not LISTENBRAINZ_ENABLED:
        print("ListenBrainz is not enabled. Cannot fetch fresh releases.")
        return

    fresh_releases_data = await listenbrainz_api.get_fresh_releases()
    releases = fresh_releases_data.get('payload', {}).get('releases', [])

    if not releases:
        print("No fresh releases found.")
        update_status_file(download_id, "completed", "No fresh releases found.", "No fresh releases",
                           current_track_count=0, total_track_count=0)
        return

    total = len(releases)
    update_status_file(download_id, "in_progress", f"Starting download of {total} albums.",
                       "Downloading fresh releases", current_track_count=0, total_track_count=total)

    downloaded_albums = []
    for release in tqdm(releases, desc="Downloading albums", unit="album"):
        artist = release.get('artist_credit_name', 'Unknown Artist')
        album = release.get('release_name', 'Unknown Album')
        release_date = release.get('release_date')

        print(f"  Album: {artist} - {album}")
        try:
            files = await downloader.download_album({
                'artist': artist,
                'album': album,
                'release_date': release_date,
            })
            if files:
                downloaded_albums.append({'artist': artist, 'album': album})
                update_status_file(download_id, "in_progress",
                                   f"Downloaded {len(downloaded_albums)} of {total} albums.",
                                   "Downloading fresh releases",
                                   current_track_count=len(downloaded_albums),
                                   total_track_count=total)
        except Exception as e:
            print(f"  Error downloading {artist} - {album}: {e}")

    if downloaded_albums:
        navidrome_api.organize_music_files(TEMP_DOWNLOAD_FOLDER, MUSIC_LIBRARY_PATH)

    count = len(downloaded_albums)
    update_status_file(download_id, "completed",
                       f"Downloaded {count} of {total} albums.",
                       "Download complete",
                       current_track_count=count,
                       total_track_count=total)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="re-soulcommand — Soulseek music recommendation downloader")
    parser.add_argument(
        "--source",
        type=str,
        default="all",
        choices=["all", "listenbrainz", "lastfm", "fresh_releases"],
        help="Recommendation source to use"
    )
    parser.add_argument(
        "--bypass-playlist-check",
        action="store_true",
        help="Bypass ListenBrainz playlist change detection"
    )
    parser.add_argument(
        "--download-id",
        type=str,
        help="UUID for download status tracking"
    )
    args = parser.parse_args()

    update_status_file(args.download_id, "in_progress", "Download initiated.")

    try:
        if args.source == "fresh_releases":
            asyncio.run(process_fresh_releases_albums(download_id=args.download_id))
        else:
            asyncio.run(process_recommendations(
                source=args.source,
                bypass_playlist_check=args.bypass_playlist_check,
                download_id=args.download_id
            ))
    except Exception as e:
        update_status_file(args.download_id, "failed", f"Download failed: {e}", "Download failed")
        raise
