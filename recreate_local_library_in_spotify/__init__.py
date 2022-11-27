import argparse
import csv
import datetime
import logging
import os
import sys

import requests


logger = logging.getLogger(__name__)


SUBSTRINGS_TO_EXCLUDE_FROM_TRACK_NAME = {
    'capella',
    'cover',
    'edit',
    'instrumental',
    'karaoke',
    'live',
    'radio',
    'remix',
    'unplugged',
    'version',
    'versión',
    'vivo',
}

SUBSTRINGS_TO_EXCLUDE_FROM_ALBUM_NAME = {
    'karaoke',
}


def get_release_date(track) -> datetime.date:
    date = track['album']['release_date']

    while not date.count('-') == 2:
        date += '-01'

    return datetime.date.fromisoformat(date)


def recreate_local_library_in_spotify(music_root: str, playlist_id: str, market: str, spotify_token: str) -> None:
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
                file_artist_name = dirpath.split('/')[-1]

            for filename in filenames:
                # Track.ogg -> Track
                # Track --- label.ogg -> Track
                file_track_name = filename.rsplit('.', maxsplit=1)[0].rsplit('---', maxsplit=1)[0]

                query = f'track:{file_track_name}'
                if file_artist_name:
                    query += f' artist:{file_artist_name}'

                response = session.get(
                    'https://api.spotify.com/v1/search',
                    params={
                        'type': 'track',
                        'market': market,
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
                    match = None

                    candidates = (candidate for candidate in response.json()['tracks']['items'] if candidate is not None)

                    for candidate in sorted(candidates, key=get_release_date):
                        discard_candidate = False

                        for substring_to_exclude in SUBSTRINGS_TO_EXCLUDE_FROM_ALBUM_NAME:
                            if substring_to_exclude in candidate['album']['name'].lower():
                                logger.debug('Skipping album "%s"', candidate['album']['name'])
                                discard_candidate = True
                                break

                        if discard_candidate:
                            continue

                        for substring_to_exclude in SUBSTRINGS_TO_EXCLUDE_FROM_TRACK_NAME:
                            if substring_to_exclude in candidate['name'].lower() and substring_to_exclude not in file_track_name.lower():
                                logger.debug('Skipping track "%s"', candidate['name'])
                                discard_candidate = True
                                break

                        if discard_candidate:
                            continue

                        match = candidate
                        break

                    if match is None:
                        spotify_track_name = ''
                        spotify_artist_name = ''
                        spotify_track_url = ''
                    else:
                        while True:
                            response = session.post(
                                f'https://api.spotify.com/v1/playlists/{playlist_id}/tracks',
                                params={'uris': match['uri']},
                            )
                            logger.debug('%s', response.json())
                            if response.status_code == 201:
                                break
                            elif response.status_code not in {502, 503}:
                                response.raise_for_status()

                        spotify_track_name = match['name']
                        spotify_artist_name = match['artists'][0]['name']
                        spotify_track_url = match['external_urls']['spotify']

                writer.writerow([
                    file_track_name,
                    file_artist_name,
                    spotify_track_name,
                    spotify_artist_name,
                    spotify_track_url,
                ])


def setup_logger() -> None:
    formatter = logging.Formatter('%(name)s:%(levelname)s:%(asctime)s:%(message)s', '%Y-%m-%d %H:%M:%S')

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    fh = logging.FileHandler(f'{datetime.datetime.now():%Y%m%d%H%M%S}.log', mode='w')
    fh.setFormatter(formatter)
    fh.setLevel(logging.DEBUG)
    root_logger.addHandler(fh)

    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    sh.setLevel(logging.INFO)
    root_logger.addHandler(sh)


def main() -> None:
    setup_logger()

    parser = argparse.ArgumentParser(description='Recreate a local music library in Spotify.')
    parser.add_argument('music_root', help='root of the local music library')
    parser.add_argument('playlist_id', help='Spotify playlist ID')
    parser.add_argument('market', help='Market')

    args = parser.parse_args()

    recreate_local_library_in_spotify(
        args.music_root,
        args.playlist_id,
        args.market,
        os.environ['SPOTIFY_TOKEN'],
    )


if __name__ == '__main__':
    main()
