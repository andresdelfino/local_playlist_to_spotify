import argparse
import base64
import csv
import datetime
import logging
import os
import random
import re
import string
import sys
import urllib.parse
import webbrowser

import requests


logger = logging.getLogger(__name__)


REDIRECT_URI = 'https://example.com/callback'
SCOPES = 'playlist-modify-private'

SUBSTRINGS_TO_EXCLUDE_FROM_TRACK_NAME = {
    'acustico',
    'acústico',
    'capella',
    'clean',
    'cover',
    'demo',
    'edit',
    'en directo',
    'instrumental',
    'karaoke',
    'live',
    'mix',
    'radio',
    'remake',
    'remix',
    'unplugged',
    'version',
    'versión',
    'vivo',
}

SUBSTRINGS_TO_EXCLUDE_FROM_ALBUM_NAME = {
    'karaoke',
}

ERRORS_TO_IGNORE = {502, 503}


def get_release_date(track) -> datetime.date:
    date = track['album']['release_date']

    if date == '0000':
        date = '0001-01-01'

    while not date.count('-') == 2:
        date += '-01'

    return datetime.date.fromisoformat(date)


def recreate_local_library_in_spotify(playlist_name: str, music_root: str, market: str, client_id: str, client_secret: str) -> None:
    state = ''.join(random.choice(string.ascii_letters) for i in range(16))

    query_string = {
      'response_type': 'code',
      'client_id': client_id,
      'scope': SCOPES,
      'redirect_uri': REDIRECT_URI,
      'state': state,
    }

    webbrowser.open('https://accounts.spotify.com/authorize?' + urllib.parse.urlencode(query_string))

    redirection = input('Redirection: ')

    code = urllib.parse.parse_qs(urllib.parse.urlparse(redirection).query)['code']

    response = requests.post(
        'https://accounts.spotify.com/api/token',
        data={
            'code': code,
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code',
        },
        headers={
            'Authorization': 'Basic ' + base64.b64encode((client_id + ':' + client_secret).encode()).decode(),
            'Content-Type': 'application/x-www-form-urlencoded',
        }
    )

    try:
        logger.debug('%s', response.json())
    except requests.exceptions.JSONDecodeError:
        logger.debug('No json response')
    response.raise_for_status()

    access_token = response.json()['access_token']

    with (
        open('songs.csv', 'w', newline='') as f,
        requests.Session() as session,
    ):
        session.headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}',
        }

        response = session.get('https://api.spotify.com/v1/me')

        try:
            logger.debug('%s', response.json())
        except requests.exceptions.JSONDecodeError:
            logger.debug('No json response')
        response.raise_for_status()

        user_id = response.json()['id']

        response = session.post(
            f'https://api.spotify.com/v1/users/{user_id}/playlists',
            json={
                'name': playlist_name,
                'public': False,
            },
        )

        try:
            logger.debug('%s', response.json())
        except requests.exceptions.JSONDecodeError:
            logger.debug('No json response')
        response.raise_for_status()

        playlist_id = response.json()['id']

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
                file_track_name = filename.rsplit('.', maxsplit=1)[0].rsplit(' --- ', maxsplit=1)[0]

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

                try:
                    logger.debug('%s', response.json())
                except requests.exceptions.JSONDecodeError:
                    logger.debug('No json response')
                response.raise_for_status()

                if response.json()['tracks']['total'] == 0:
                    logger.debug('No matches for file track "%s"', file_track_name)

                    spotify_track_name = ''
                    spotify_artist_name = ''
                    spotify_track_url = ''
                else:
                    match = None

                    candidates = (candidate for candidate in response.json()['tracks']['items'] if candidate is not None)

                    normalized_file_track_name = re.sub(' +', ' ', file_track_name).lower().strip()

                    for candidate in sorted(candidates, key=get_release_date):
                        if re.fullmatch('[^ ]+', file_track_name, flags=re.IGNORECASE) and candidate['name'].lower() != file_track_name.lower():
                            logger.debug('Skipping track "%s" due to naming ("%s")', candidate['name'], file_track_name)
                            continue

                        normalized_candidate_name = re.sub(' +', ' ', candidate['name']).lower()
                        if normalized_file_track_name not in normalized_candidate_name:
                            logger.debug('Skipping track "%s" due to naming ("%s", "%s", "%s")', candidate['name'], file_track_name, normalized_file_track_name, normalized_candidate_name)
                            continue

                        discard_candidate = False

                        for substring_to_exclude in SUBSTRINGS_TO_EXCLUDE_FROM_ALBUM_NAME:
                            if re.search(rf'\b{substring_to_exclude}\b', candidate['album']['name'], flags=re.IGNORECASE):
                                logger.debug('Skipping album "%s" due to substring', candidate['album']['name'])
                                discard_candidate = True
                                break

                        if discard_candidate:
                            continue

                        for substring_to_exclude in SUBSTRINGS_TO_EXCLUDE_FROM_TRACK_NAME:
                            if not re.search(rf'\b{substring_to_exclude}\b', file_track_name, flags=re.IGNORECASE) and re.search(rf'\b{substring_to_exclude}\b', candidate['name'], flags=re.IGNORECASE):
                                logger.debug('Skipping track "%s" due to substring', candidate['name'])
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
                                json={
                                    'uris': [
                                        match['uri'],
                                    ],
                                },
                            )

                            try:
                                logger.debug('%s', response.json())
                            except requests.exceptions.JSONDecodeError:
                                logger.debug('No json response')

                            if response.status_code == 200:
                                break
                            elif response.status_code not in ERRORS_TO_IGNORE:
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
    parser.add_argument('playlist_name')
    parser.add_argument('music_root', help='root of the local music library')
    parser.add_argument('market', help='Market')

    args = parser.parse_args()

    recreate_local_library_in_spotify(
        playlist_name=args.playlist_name,
        music_root=args.music_root,
        market=args.market,
        client_id=os.environ['SPOTIFY_CLIENT_ID'],
        client_secret=os.environ['SPOTIFY_CLIENT_SECRET'],
    )


if __name__ == '__main__':
    main()
