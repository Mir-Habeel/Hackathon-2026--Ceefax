# Ceefax 2026

A small Python web app inspired by the old Ceefax and Teletext services. Enter a page number to see UK headlines, weather, transport updates, electricity carbon intensity, or a short chiptune made from text.

## Run it on your computer

You need Python 3.14 or later and an internet connection for the live information pages.

From this folder, run:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install certifi
python app.py
```

Open the address printed in the terminal. It will usually be `http://127.0.0.1:8000`. If that port is busy, the app tries the next few ports and prints the one it uses.

To stop the app, click the terminal and press **Control+C**.

## Pages

| Number | Page |
| --- | --- |
| 100 | Page index |
| 101 | BBC UK headlines |
| 401 | Weather for a UK postcode |
| 501 | London Underground status |
| 601 | Great Britain electricity carbon intensity |
| 701 | Other London transport updates |
| 777 | Text-to-chiptune studio |

Type a page number and press Enter, or choose a page from the index. Use **Refresh** to fetch the latest information again. The weather postcode is remembered for the current browser session.

## How the music page works

Enter a short phrase and choose a mood, or leave mood selection on Auto. The Python app maps the characters to notes from a five-note musical scale, then writes the notes into a WAV file. The browser plays the file and draws its waveform. Auto mood uses a small list of words associated with upbeat or moody text; it does not use AI to interpret the phrase.

**Sample London Data** uses the current Tube status to make a phrase, then turns that phrase into a tune. The music is generated locally by this app; it is not a radio stream.

## Live information

The app fetches data when a page is opened or refreshed. It uses:

- BBC UK RSS feed for headlines
- Postcodes.io to find a postcode's location
- Open-Meteo for current weather
- Transport for London's API for Tube and other London transport statuses
- The Carbon Intensity API for Great Britain electricity data

Live pages need an internet connection. If a service is unavailable, that page shows an error message; the other pages can still be used.

## Project files

- `app.py` is the Python entry point for the app.
- `pyproject.toml` records the project name, Python requirement, and dependency.
- `Dockerfile` describes how to run the app in a container.
