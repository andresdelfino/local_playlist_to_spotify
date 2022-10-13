#!/bin/env python

import argparse
import csv
import logging
import os

import requests


logger = logging.getLogger(__name__)


SUBSTRINGS_TO_EXCLUDE = [
    'cover',
    'edit',
    'live',
    'radio',
    'remix',
    'version',
    'versión',
    'vivo',
]


def recreate_local_library_in_spotify(music_root: str, playlist_id: str, spotify_token: str) -> None:
    with (
        open('songs.csv', 'w', newline='') as f,
        requests.Session() as session,
    ):
        session.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {spotify_token}',
        }

        writer = csv.writer(f)

        writer.writerow([
            'File track',
            'File artist',
            'Spotify track',
            'Spotify artist',
            'URL',
        ])

        for dirpath, dirnames, filenames in os.walk(music_root):
            if len(dirpath.removeprefix(music_root + '/').split('/')) > 1:
                logger.debug('Skipping album "%s"', dirpath)
                continue

            if dirpath == music_root:
                file_artist_name = 'N/A'
            else:
                # music_root/Artist -> Artist -> Artist
                # music_root/Artist/Album -> Artist/Album -> Artist
                file_artist_name = dirpath.removeprefix(music_root + '/').split('/')[0]

            for filename in filenames:
                file_track_name = filename.rsplit('.', maxsplit=1)[0]

                query = f'track:{file_track_name}'
                if file_artist_name:
                    query += f' artist:{file_artist_name}'

                response = session.get(
                    'https://api.spotify.com/v1/search',
                    params={
                        'type': 'track',
                        'market': 'AR',
                        'limit': '1',
                        'q': query,
                    },
                )
                logger.debug('%s', response.json())
                response.raise_for_status()

                if response.json()['tracks']['total'] == 0:
                    spotify_track_name = ''
                    spotify_artist_name = ''
                    spotify_track_url = ''
                else:
                    candidate = response.json()['tracks']['items'][0]

                    mismatch = False

                    for substring_to_exclude in SUBSTRINGS_TO_EXCLUDE:
                        if substring_to_exclude in candidate['name'].lower() and substring_to_exclude not in file_track_name.lower():
                            mismatch = True
                            break

                    if mismatch:
                        spotify_track_name = ''
                        spotify_artist_name = ''
                        spotify_track_url = ''
                    else:
                        match = candidate

                        spotify_track_name = match['name']
                        spotify_artist_name = match['artists'][0]['name']
                        spotify_track_url = match['external_urls']['spotify']

                        while True:
                            response = session.post(
                                f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                                params={'uris': match['uri']},
                            )
                            logger.debug('%s', response.json())
                            if response.status_code == 201:
                                break
                            elif response.status_code != 503:
                                response.raise_for_status()

                writer.writerow([
                    file_track_name,
                    file_artist_name,
                    spotify_track_name,
                    spotify_artist_name,
                    spotify_track_url,
                ])


def main() -> None:
    logging.basicConfig(level=logging.DEBUG)

    parser = argparse.ArgumentParser(description='Recreate a local music library in Spotify.')
    parser.add_argument('music_root', help='root of the local music library')
    parser.add_argument('playlist_id', help='Spotify playlist ID')

    args = parser.parse_args()

    recreate_local_library_in_spotify(args.music_root, args.playlist_id, os.environ['SPOTIFY_TOKEN'])


if __name__ == '__main__':
    main()
