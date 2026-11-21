# Ceefax 2026

A Python web app with a retro teletext feel and numbered pages as its main navigation.

## Run

From the project folder:

```sh
cd ceefax-2026 && python3 app.py
```

Open the URL printed in the terminal. The app normally uses `http://127.0.0.1:8000`; if that is occupied, it automatically tries the next available port through `8019`.

## Pages

- **100** — Page index
- **101** — BBC UK headlines
- **401** — UK postcode weather; the postcode is remembered for the current browser visit
- **501** — London Underground status
- **601** — Great Britain electricity carbon intensity
- **701** — Other London transport statuses
- **777** — Bonus text-to-chiptune studio

Use the page-number field and press Enter, choose a page from the Page 100 channel grid, or use the Fastext buttons. Each data page has a Home control, refresh button, and update time. If a feed is unreachable, the page shows an offline message and the rest of Ceefax continues to work.

Weather uses Postcodes.io to geocode the postcode and Open-Meteo for current conditions. News comes from the BBC UK RSS feed; Tube and wider transport statuses come from the TfL Unified API; carbon intensity comes from the NESO Carbon Intensity API. Live data requires an internet connection. The optional radio feature is omitted because a reliably working stream with clear permission for embedding could not be verified.

## Deploy to Render

This project includes a `Dockerfile` so it can be hosted as a public Python web service. Render is the simplest route for a hackathon submission because it can build directly from a GitHub repository and gives the app a public `onrender.com` URL.

1. Push this `ceefax-2026` project folder to a GitHub repository.
2. Create a Render account and select **New → Web Service**.
3. Connect the repository and choose the **Docker** runtime. If the repository contains other projects, set its root directory to `ceefax-2026`.
4. Deploy. Render provides the `PORT` environment variable automatically; Ceefax binds to it on `0.0.0.0` in production.
5. Copy the resulting `https://…onrender.com` address into the submission's website or demo URL field.

Render's free service can sleep after inactivity, so open the link shortly before presenting it. It may take a short time to wake on the first visit.
