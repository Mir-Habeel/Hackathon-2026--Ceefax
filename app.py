"""Ceefax 2026: a numbered-page UK information service, built with Python's stdlib."""

from __future__ import annotations

import errno
import json
import os
import re
import ssl
import struct
import urllib.error
import urllib.parse
import urllib.request
import wave
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree

import certifi

DEPLOY_PORT = os.environ.get("PORT")
HOST = "0.0.0.0" if DEPLOY_PORT else "127.0.0.1"
PORT, TIMEOUT = int(DEPLOY_PORT or "8000"), 6
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
BASE_DIR = Path(__file__).resolve().parent
STATIC_FILES = {
    "/": ("templates/index.html", "text/html; charset=utf-8"),
    "/static/style.css": ("static/style.css", "text/css; charset=utf-8"),
    "/static/app.js": ("static/app.js", "text/javascript; charset=utf-8"),
}
WEATHER_CACHE: dict[str, tuple[datetime, dict]] = {}
WEATHER_CACHE_SECONDS = 300


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_bytes(url: str, timeout: int = TIMEOUT) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Ceefax2026/1.0 (+https://github.com/Mir-Habeel/Hackathon-2026--Ceefax)", "Accept": "application/json, application/rss+xml, application/xml"})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read()


def fetch_json(url: str) -> dict | list:
    return json.loads(fetch_bytes(url))


def service_error(exc: Exception, fallback: str) -> dict:
    message = "CHECK THE DETAILS AND TRY AGAIN." if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 404) else fallback
    return {"live": False, "error": message, "updated": now_iso()}


def postcode_location(postcode: str) -> dict | None:
    """Resolve a UK postcode, with OpenStreetMap as a low-volume fallback."""
    compact = postcode.replace(" ", "")
    try:
        place = fetch_json("https://api.postcodes.io/postcodes/" + urllib.parse.quote(compact, safe=""))
        result = place.get("result") if isinstance(place, dict) else None
        if result:
            return result
    except (OSError, ValueError, urllib.error.URLError):
        pass

    fallback_query = urllib.parse.urlencode({"postalcode": compact, "country": "United Kingdom", "format": "jsonv2", "limit": 1})
    places = fetch_json("https://nominatim.openstreetmap.org/search?" + fallback_query)
    if not isinstance(places, list) or not places:
        return None
    place = places[0]
    address = place.get("address", {}) if isinstance(place.get("address"), dict) else {}
    return {
        "postcode": place.get("name", postcode),
        "latitude": float(place["lat"]),
        "longitude": float(place["lon"]),
        "admin_district": address.get("city") or address.get("town") or address.get("county") or place.get("display_name", "UK LOCATION").split(",", 1)[0].strip(),
    }


def current_weather(latitude: float, longitude: float) -> dict:
    """Get conditions from Open-Meteo, then MET Norway if it is unavailable."""
    descriptions = {0: "CLEAR SKY", 1: "MAINLY CLEAR", 2: "PARTLY CLOUDY", 3: "OVERCAST", 45: "FOG", 48: "RIME FOG", 51: "LIGHT DRIZZLE", 53: "DRIZZLE", 55: "HEAVY DRIZZLE", 61: "LIGHT RAIN", 63: "RAIN", 65: "HEAVY RAIN", 71: "LIGHT SNOW", 73: "SNOW", 75: "HEAVY SNOW", 80: "RAIN SHOWERS", 81: "SHOWERS", 82: "HEAVY SHOWERS", 95: "THUNDERSTORM", 96: "THUNDERSTORM + HAIL", 99: "THUNDERSTORM + HAIL"}
    try:
        params = urllib.parse.urlencode({"latitude": latitude, "longitude": longitude, "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m", "timezone": "auto"})
        current = fetch_json("https://api.open-meteo.com/v1/forecast?" + params)["current"]
        return {"temperature": round(current["temperature_2m"]), "apparent": round(current["apparent_temperature"]), "humidity": current["relative_humidity_2m"], "precipitation": current["precipitation"], "wind": round(current["wind_speed_10m"]), "description": descriptions.get(current.get("weather_code"), "CURRENT CONDITIONS")}
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
        params = urllib.parse.urlencode({"lat": latitude, "lon": longitude})
        timeseries = fetch_json("https://api.met.no/weatherapi/locationforecast/2.0/compact?" + params)["properties"]["timeseries"][0]["data"]
        details = timeseries["instant"]["details"]
        symbol = (timeseries.get("next_1_hours") or timeseries.get("next_6_hours") or timeseries.get("next_12_hours") or {}).get("summary", {}).get("symbol_code", "")
        description = "RAIN" if "rain" in symbol else "SNOW" if "snow" in symbol else "FOG" if "fog" in symbol else "CLOUDY" if "cloudy" in symbol else "CLEAR"
        precipitation = (timeseries.get("next_1_hours") or {}).get("details", {}).get("precipitation_amount", 0)
        return {"temperature": round(details["air_temperature"]), "apparent": round(details["air_temperature"]), "humidity": round(details.get("relative_humidity", 0)), "precipitation": precipitation, "wind": round(details.get("wind_speed", 0) * 3.6), "description": description}


def news_data() -> dict:
    try:
        xml = ElementTree.fromstring(fetch_bytes("https://feeds.bbci.co.uk/news/uk/rss.xml"))
        items = []
        for item in xml.findall(".//item")[:10]:
            title, url = item.findtext("title", "").strip(), item.findtext("link", "")
            if title:
                items.append({"title": title, "url": url if urllib.parse.urlparse(url).scheme in ("http", "https") else "", "date": item.findtext("pubDate", "")})
        if not items:
            raise ValueError("No headlines")
        return {"live": True, "updated": now_iso(), "subtitle": "BBC NEWS UK · HEADLINES", "items": items}
    except (OSError, ValueError, ElementTree.ParseError) as exc:
        return {**service_error(exc, "NEWS FEED TEMPORARILY UNAVAILABLE."), "subtitle": "UK HEADLINES"}


def weather_data(postcode: str) -> dict:
    postcode = " ".join(postcode.upper().split())
    if not postcode:
        return {"live": False, "updated": now_iso(), "postcode": "", "error": "ENTER A UK POSTCODE TO LOAD LOCAL WEATHER."}
    if not re.fullmatch(r"[A-Z]{1,2}\d[A-Z\d]? ?\d[A-Z]{2}", postcode):
        return {"live": False, "updated": now_iso(), "postcode": postcode, "error": "THAT DOESN’T LOOK LIKE A UK POSTCODE. CHECK IT AND TRY AGAIN."}
    try:
        cached = WEATHER_CACHE.get(postcode)
        if cached and (datetime.now(timezone.utc) - cached[0]).total_seconds() < WEATHER_CACHE_SECONDS:
            return cached[1]
        result = postcode_location(postcode)
        if not result:
            return {"live": False, "updated": now_iso(), "postcode": postcode, "error": "POSTCODE NOT FOUND. CHECK IT AND TRY AGAIN."}
        reading = current_weather(result["latitude"], result["longitude"])
        payload = {"live": True, "updated": now_iso(), "postcode": result.get("postcode", postcode), "location": result.get("admin_district") or result.get("region") or "UK LOCATION", **reading}
        WEATHER_CACHE[postcode] = (datetime.now(timezone.utc), payload)
        return payload
    except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError) as exc:
        return {**service_error(exc, "WEATHER SERVICE TEMPORARILY UNAVAILABLE."), "postcode": postcode}


def status_lines(modes: str) -> list[dict]:
    raw = fetch_json("https://api.tfl.gov.uk/Line/Mode/" + urllib.parse.quote(modes, safe=",-") + "/Status")
    lines = []
    for line in raw if isinstance(raw, list) else []:
        statuses = line.get("lineStatuses", [])
        record = statuses[0] if statuses else {}
        status = record.get("statusSeverityDescription", "Status unavailable")
        lines.append({"name": line.get("name", "TRANSPORT"), "status": status.upper(), "detail": record.get("reason", ""), "good": status.lower() in ("good service", "no issues")})
    return lines


def tube_data() -> dict:
    try:
        return {"live": True, "updated": now_iso(), "subtitle": "TRANSPORT FOR LONDON · UNDERGROUND", "lines": status_lines("tube")}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {**service_error(exc, "TFL TUBE STATUS TEMPORARILY UNAVAILABLE."), "subtitle": "LONDON UNDERGROUND", "lines": []}


def carbon_data() -> dict:
    try:
        reading = fetch_json("https://api.carbonintensity.org.uk/intensity")["data"][0]
        intensity = reading["intensity"]
        return {"live": True, "updated": now_iso(), "subtitle": "NATIONAL ENERGY SYSTEM OPERATOR · GREAT BRITAIN", "forecast": intensity.get("forecast", "—"), "actual": intensity.get("actual"), "index": (intensity.get("index") or "UNKNOWN").upper(), "period": f"{reading.get('from', '')} — {reading.get('to', '')}"}
    except (OSError, ValueError, KeyError, IndexError, TypeError, urllib.error.URLError) as exc:
        return {**service_error(exc, "CARBON INTENSITY FEED TEMPORARILY UNAVAILABLE."), "subtitle": "UK ELECTRICITY GRID"}


def travel_data() -> dict:
    try:
        lines = status_lines("dlr,overground,tram")
        affected = [line for line in lines if not line["good"]]
        return {"live": True, "updated": now_iso(), "subtitle": "TRANSPORT FOR LONDON · OTHER SERVICES", "lines": affected[:20] if affected else lines[:10]}
    except (OSError, ValueError, urllib.error.URLError) as exc:
        return {**service_error(exc, "TRAVEL UPDATES TEMPORARILY UNAVAILABLE."), "subtitle": "LONDON TRANSPORT", "lines": []}


def infer_mood(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return "moody" if len(words & {"rain","delay","delays","storm","night","late","closed","disruption","grey","sad","lost","cold","fog","moody"}) > len(words & {"sun","sunny","good","joy","love","bright","party","summer","clear","happy","win","upbeat"}) else "upbeat"


def song_spec(text: str, mood: str) -> dict:
    cleaned = " ".join(text.split())[:240] or "A signal from London"
    actual = infer_mood(cleaned) if mood == "auto" else ("moody" if mood == "moody" else "upbeat")
    return {"text": cleaned, "mood": actual, "title": cleaned[:26], "notes": min(max(len(cleaned), 8), 48), "bpm": 104 if actual == "moody" else 142}


def generate_wav(text: str, mood: str) -> tuple[bytes, dict]:
    spec = song_spec(text, mood)
    scale, chars, rate, frames = [261.63 * 2 ** (step / 12) for step in (0, 2, 4, 7, 9)], [ord(c) for c in spec["text"] if c.isprintable()], 22050, bytearray()
    notes, beat = min(max(len(chars), 8), 48), 60 / spec["bpm"] * (0.72 if spec["mood"] == "moody" else 0.48)
    for index in range(notes):
        value = chars[index % len(chars)] if chars else 65
        frequency = scale[(value + index * (1 if spec["mood"] == "upbeat" else 3)) % len(scale)] * (2 if (value // 5 + index) % 4 == 0 else 1)
        count = int(rate * beat)
        for sample in range(count):
            square, envelope = (0.28 if (sample / rate * frequency) % 1 < .5 else -0.28), min(1.0, sample / 150, (count - sample) / 350)
            frames.extend(struct.pack("<h", int(square * envelope * 32767)))
        frames.extend(b"\0\0" * int(rate * .018))
    output = BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(frames)
    spec.update({"notes": notes, "duration": round(notes * beat, 1)})
    return output.getvalue(), spec


def sample_live() -> dict:
    tube = tube_data()
    if not tube.get("live"):
        return {"text": "London is waiting on a live signal. Make your own transmission.", "source": "local fallback", "mood": "upbeat"}
    affected = [line["name"] for line in tube["lines"] if not line["good"]]
    text = "London signal. " + ("Tube disruption on " + ", ".join(affected[:4]) + "." if affected else "The Tube is running with good service.")
    return {"text": text, "source": "London Tube", "mood": "moody" if affected else "upbeat"}


class Handler(BaseHTTPRequestHandler):
    def respond(self, body: bytes, content_type: str, status: int = 200):
        self.send_response(status); self.send_header("Content-Type", content_type); self.send_header("Content-Length", str(len(body))); self.send_header("Cache-Control", "no-store"); self.send_header("X-Content-Type-Options", "nosniff"); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        route = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(route.query)
        if route.path in STATIC_FILES:
            filename, content_type = STATIC_FILES[route.path]
            return self.respond((BASE_DIR / filename).read_bytes(), content_type)
        handlers = {"/api/101": news_data, "/api/401": lambda: weather_data(query.get("postcode", [""])[0]), "/api/501": tube_data, "/api/601": carbon_data, "/api/701": travel_data, "/api/sample": sample_live}
        if route.path in handlers:
            return self.respond(json.dumps(handlers[route.path](), ensure_ascii=False).encode(), "application/json; charset=utf-8")
        if route.path in ("/api/song", "/api/song.wav"):
            audio, info = generate_wav(query.get("text", [""])[0], query.get("mood", ["auto"])[0])
            return self.respond(audio if route.path.endswith(".wav") else json.dumps(info).encode(), "audio/wav" if route.path.endswith(".wav") else "application/json; charset=utf-8")
        return self.respond(b"Not found", "text/plain; charset=utf-8", 404)

    def log_message(self, *_args):
        pass


def main():
    server = None
    candidates = (PORT,) if DEPLOY_PORT else range(PORT, PORT + 20)
    for port in candidates:
        try:
            server = ThreadingHTTPServer((HOST, port), Handler)
            break
        except OSError as error:
            if error.errno != errno.EADDRINUSE:
                raise
    if server is None:
        raise OSError("Ceefax could not find a free port between 8000 and 8019.")
    print(f"Ceefax 2026 on http://{HOST}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
