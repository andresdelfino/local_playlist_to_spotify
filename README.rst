Request a token selecting scope ``playlist-modify-private``:
https://developer.spotify.com/console/post-playlist-tracks/

Export the token as an environment variable::

    export SPOTIFY_TOKEN=OWFLQ4CwURUdHkIkZvtN9xTS8bzeB3ovqwFuD6tXlo3CyZO4dHOynPXxnXrqlul96t3qbJl45HDu3zoJx9QWSvnT0n4GosGgG4PLRQTEMHs79apr85dR    GnJREFKtkdpksTJpyCkAeBe0PRoqF0p7cLCv7I7SIncOTj1UBJTPrkpe7fDFnJJbXq80lUMeyrNaDub0D9MVBMCP3qEDyhc

Run::

    pip install -r requirements.txt
    ./recreate_local_library_in_spotify.py /home/me/música gLOF49eo6DCx7xqyVDLIV1
