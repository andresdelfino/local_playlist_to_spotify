#!/bin/env python

import csv
import os
import types

import requests


#export SPOTIFY_TOKEN=
#export PLAYLIST_ID=
#export MUSIC_ROOT=/home/me/música


def main():
    # https://developer.spotify.com/console/post-playlist-tracks/
    SPOTIFY_TOKEN = os.environ['SPOTIFY_TOKEN']

    MUSIC_ROOT = os.environ['MUSIC_ROOT']
    PLAYLIST_ID = os.environ['PLAYLIST_ID']

    HEADERS = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {SPOTIFY_TOKEN}',
    }

    COMMON_PARAMS = {
        'type': 'track',
        'market': 'AR',
        'limit': '1',
    }

    table = []

    with open('songs.csv', 'w', newline='') as f:
        writer = csv.writer(f, delimiter=' ', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(['Track', 'Artist', 'URI', 'URL'])

        for dirpath, dirnames, filenames in os.walk(MUSIC_ROOT):
            if dirpath == MUSIC_ROOT:
                file_artist_name = ''
            else:
                # MUSIC_ROOT/Artist -> Artist -> Artist
                # MUSIC_ROOT/Artist/Album -> Artist/Album -> Artist
                file_artist_name = dirpath.removeprefix(MUSIC_ROOT + '/').split('/')[0]

            for filename in filenames:
                file_track_name = filename.rsplit('.', maxsplit=1)[0]

                param = {
                    'q': f'track:{file_track_name} artist:{file_artist_name}',
                }

                response = requests.get(
                    'https://api.spotify.com/v1/search',
                    params=COMMON_PARAMS | param,
                    headers=HEADERS,
                )

                print(param)
                print(response.json())

                if response.json()['tracks']['total'] == 0:
                    continue

                match = response.json()['tracks']['items'][0]

                spotify_track_name = match['name']
                spotify_artist_name = match['artists'][0]['name']
                spotify_track_uri = match['uri']
                spotify_track_url = match['external_urls']['spotify']

                post_params = {
                    'uris': spotify_track_uri,
                }

                requests.post(
                    f'https://api.spotify.com/v1/playlists/{PLAYLIST_ID}/tracks',
                    params=post_params,
                    headers=HEADERS,
                )

                writer.writerow([spotify_track_name, spotify_artist_name, spotify_track_uri, spotify_track_url])


if __name__ == '__main__':
    main()
