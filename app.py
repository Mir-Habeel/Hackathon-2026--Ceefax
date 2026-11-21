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
from xml.etree import ElementTree

import certifi

DEPLOY_PORT = os.environ.get("PORT")
HOST = "0.0.0.0" if DEPLOY_PORT else "127.0.0.1"
PORT, TIMEOUT = int(DEPLOY_PORT or "8000"), 6
SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())

CSS = r"""
:root{--black:#000;--blue:#001bc9;--cyan:#00ffff;--yellow:#ffff00;--white:#fff;--green:#00ff00;--red:#ff1b1b;--magenta:#ff00ff}
*{box-sizing:border-box}body{margin:0;min-height:100vh;background:#15171b;color:var(--white);font-family:"Courier New",Courier,monospace;font-weight:700;padding:28px;display:grid;place-items:center}
button,input,textarea,select{font:inherit}.tv{width:min(1050px,100%);padding:18px;background:linear-gradient(135deg,#424951,#181c21 45%,#50575d);border:2px solid #737b81;border-radius:30px;box-shadow:0 30px 90px #000d,inset 0 0 0 5px #252a2f}.screen{position:relative;min-height:660px;background:var(--black);padding:17px 22px 22px;overflow:hidden;border:10px solid #050607;border-radius:13px;box-shadow:inset 0 0 45px #000}
.screen:before{content:"";position:absolute;z-index:2;inset:0;pointer-events:none;opacity:.14;background:repeating-linear-gradient(transparent 0 3px,#000 4px),radial-gradient(ellipse at center,transparent 42%,#0008 100%)}.screen>*{position:relative;z-index:1}
.broadcast{display:grid;grid-template-columns:92px 1fr auto;align-items:center;gap:12px;padding:8px 10px;background:var(--blue);border-bottom:3px solid var(--cyan);letter-spacing:.06em}.current-page{color:var(--yellow);font-size:26px;line-height:1}.channel{justify-self:center;color:var(--white);font-size:23px;letter-spacing:.13em}.teletext-time{color:var(--cyan);font-size:14px;white-space:nowrap}
.tune{display:flex;justify-content:flex-end;align-items:center;gap:4px;padding:11px 0 14px;color:var(--cyan)}.tune label{font-size:13px}.page-input{width:58px;padding:5px;border:2px solid var(--yellow);outline:0;background:#000;color:var(--yellow);font-size:18px;font-weight:900;text-align:center;letter-spacing:.08em}.go,.refresh,.home{padding:6px 10px;border:0;background:var(--cyan);color:#000;cursor:pointer}.go:hover,.refresh:hover,.home:hover{background:var(--yellow)}.home{margin-right:auto;background:var(--yellow)}.refresh{margin-left:7px;background:var(--green)}
.page{min-height:465px}.page-heading{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px;padding-bottom:8px;border-bottom:2px solid var(--cyan)}.page-heading h1{margin:0;color:var(--yellow);font-size:27px;letter-spacing:.07em}.page-kicker{margin-top:5px;color:var(--cyan);font-size:13px}.updated{margin:7px 0 14px;color:var(--cyan);font-size:12px}.updated strong{color:var(--green)}.message{margin-top:20px;padding:12px;border:2px solid var(--yellow);color:var(--yellow);line-height:1.6}.error{border-color:var(--red);color:var(--yellow)}
.ceefax-banner{margin:5px 0 17px;padding:13px 16px;background:var(--blue);color:var(--yellow);font-size:clamp(30px,6vw,59px);line-height:1;letter-spacing:.1em;text-align:center;text-shadow:3px 3px #000}.index-intro{margin:0 0 14px;color:var(--cyan);text-align:center;font-size:14px}.channel-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.channel-card{min-height:126px;padding:11px;border:1px solid #315162;background:#000;color:var(--white);text-align:left;cursor:pointer;text-decoration:none}.channel-card:hover,.channel-card:focus-visible{background:#06132c;border-color:var(--cyan);outline:0}.channel-card.studio{border:2px solid var(--yellow);background:#101000}.channel-card.studio:hover{background:#292400}.card-number{display:block;color:var(--yellow);font-size:25px;line-height:1}.card-title{display:block;margin-top:4px;color:var(--white);font-size:15px}.studio .card-title{color:var(--yellow)}.preview{display:block;min-height:37px;margin-top:14px;color:var(--white);font-size:12px;line-height:1.35}.preview.loading{color:var(--cyan)}.preview.live{color:var(--green)}
.news-list,.line-list{margin:0;padding:0;list-style:none}.news-list li,.line-list li{padding:10px 0;border-bottom:1px solid #005d6e}.news-list a{color:var(--white);text-decoration:none}.news-list a:hover{color:var(--yellow)}.story-no{display:inline-block;min-width:40px;color:var(--yellow)}.story-date{display:block;margin:3px 0 0 40px;color:var(--cyan);font-size:12px}.data-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.data-box{padding:12px;border:2px solid var(--cyan)}.data-label{color:var(--cyan);font-size:12px}.data-value{margin-top:5px;color:var(--yellow);font-size:33px;line-height:1.1}.data-note{margin-top:5px;color:var(--white);font-size:13px}.line-list li{display:grid;grid-template-columns:1fr 2fr;gap:10px}.line-name{color:var(--white)}.line-status.good{color:var(--green)}.line-status.bad{color:var(--yellow)}.line-detail{display:block;margin-top:3px;color:var(--cyan);font-size:12px}.postcode-form{display:flex;align-items:center;gap:7px;margin-bottom:14px;color:var(--cyan)}.postcode-form input{width:118px;padding:5px;background:#000;color:var(--white);border:2px solid var(--cyan);text-transform:uppercase}.postcode-form button{padding:6px 10px;border:0;background:var(--cyan);color:#000;cursor:pointer}
.studio-layout{display:grid;grid-template-columns:1.2fr .8fr;gap:16px}.studio-layout textarea{width:100%;height:105px;padding:10px;background:#000;border:2px solid var(--cyan);color:var(--white);resize:vertical}.studio-controls{display:flex;gap:7px;flex-wrap:wrap;margin:9px 0}.studio-controls button,.studio-controls select{padding:6px;border:2px solid var(--cyan);background:#000;color:var(--cyan);cursor:pointer}.studio-controls button:first-child{background:var(--yellow);border-color:var(--yellow);color:#000}.cassette{min-height:185px;padding:12px;border:2px solid var(--yellow);background:#071f2c;display:flex;flex-direction:column;justify-content:space-between}.cassette-title{margin-top:8px;color:var(--yellow)}.tape{height:60px;border:2px solid var(--cyan);display:flex;align-items:center;justify-content:space-evenly}.reel{width:38px;height:38px;border:3px solid var(--yellow);border-radius:50%;background:radial-gradient(circle,#000 0 5px,var(--cyan) 6px 8px,transparent 9px);animation:spin 3s linear infinite}.reel.paused{animation-play-state:paused}@keyframes spin{to{transform:rotate(360deg)}}canvas{width:100%;height:90px;margin-top:8px;border:2px solid var(--cyan);background:#000}
.fastext{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-top:22px;padding-top:12px;border-top:2px solid var(--cyan)}.fastext button{padding:10px 7px;border:0;color:#000;font-weight:900;cursor:pointer;letter-spacing:.03em}.fastext button:hover{filter:brightness(1.3)}.fast-red{background:var(--red)}.fast-green{background:var(--green)}.fast-yellow{background:var(--yellow)}.fast-blue{background:var(--cyan)}
@media(max-width:720px){body{padding:6px}.tv{padding:8px;border-radius:16px}.screen{min-height:94vh;padding:12px;border-width:6px}.broadcast{grid-template-columns:63px 1fr;gap:7px}.current-page{font-size:21px}.channel{justify-self:start;font-size:19px}.teletext-time{grid-column:1/-1;font-size:11px}.channel-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.channel-card{min-height:110px}.studio-layout{grid-template-columns:1fr}.page-heading h1{font-size:22px}.tune{justify-content:flex-start}.fastext{grid-template-columns:repeat(2,1fr)}}@media(max-width:400px){.channel-grid{grid-template-columns:1fr}.fastext{grid-template-columns:1fr 1fr}.channel-card{min-height:96px}}
"""

PAGE = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#000000"><title>Ceefax 2026 · Page 100</title><style>__CSS__</style></head>
<body><main class="tv"><section class="screen">
<header class="broadcast"><span class="current-page" id="headerPage">100</span><span class="channel">CEEFAX 1</span><time class="teletext-time" id="clock"></time></header>
<form class="tune" id="pageForm"><button class="home" data-page="100" type="button">HOME 100</button><label for="pageInput">PAGE</label><input class="page-input" id="pageInput" value="100" maxlength="3" inputmode="numeric" pattern="[0-9]{3}" aria-label="Three digit page number"><button class="go" type="submit">GO</button><button class="refresh" id="refresh" type="button">REFRESH</button></form>
<main class="page" id="view" aria-live="polite"><div class="message">TUNING IN…</div></main>
<footer class="fastext" aria-label="Fastext navigation"><button class="fast-red" data-page="101">101 NEWS</button><button class="fast-green" data-page="401">401 WEATHER</button><button class="fast-yellow" data-page="501">501 TUBE</button><button class="fast-blue" data-page="777">777 8-BIT STUDIO</button></footer>
</section></main>
<script>
const $=s=>document.querySelector(s),pages={"100":"INDEX","101":"NEWS","401":"WEATHER","501":"TUBE","601":"POWER","701":"TRAVEL","777":"8-BIT STUDIO"};let currentPage="100",audioContext=null,audioSource=null;
function esc(v){return String(v??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function clock(){const d=new Date(),day=d.toLocaleDateString("en-GB",{timeZone:"Europe/London",weekday:"short"}).toUpperCase(),date=d.toLocaleDateString("en-GB",{timeZone:"Europe/London",day:"2-digit",month:"short"}).toUpperCase(),time=d.toLocaleTimeString("en-GB",{timeZone:"Europe/London",hour:"2-digit",minute:"2-digit",second:"2-digit"});$("#clock").textContent=day+" "+date+" "+time}clock();setInterval(clock,1000);
function updated(data){return data.updated?new Date(data.updated).toLocaleTimeString("en-GB",{timeZone:"Europe/London",hour:"2-digit",minute:"2-digit",second:"2-digit"}):"—"}
function frame(data){return '<div class="page-heading"><div><h1>'+currentPage+" · "+pages[currentPage]+'</h1><div class="page-kicker">'+esc(data.subtitle||"CEEFAX 2026 LIVE SERVICE")+'</div></div></div><div class="updated">LAST UPDATED <strong>'+updated(data)+"</strong>"+(data.live?" · LIVE":" · UNAVAILABLE")+'</div><div class="page-body">'+data.html+"</div>"}
function infoCard(number,title){return '<a href="#'+number+'" data-page="'+number+'" class="channel-card '+(number==="777"?"studio":"")+'"><span class="card-number">'+number+'</span><span class="card-title">'+title+'</span><span class="preview loading" id="preview'+number+'">LOADING LIVE DATA…</span></a>'}
function indexMarkup(){return '<div class="ceefax-banner">CEEFAX 2026</div><p class="index-intro">SELECT A CHANNEL OR ENTER A PAGE NUMBER ABOVE</p><div class="channel-grid">'+infoCard("101","NEWS")+infoCard("401","WEATHER")+infoCard("501","LONDON TUBE")+infoCard("601","GRID POWER")+infoCard("701","TRAVEL UPDATES")+infoCard("777","8-BIT SOUND STUDIO")+"</div>"}
function indexPage(){$("#view").innerHTML=frame({subtitle:"PAGE 100 · CHANNEL INDEX",updated:new Date().toISOString(),live:true,html:indexMarkup()});loadPreviews()}
function preview(id,text,live=true){const el=$("#preview"+id);if(el){el.textContent=text;el.className="preview "+(live?"live":"")}}
async function loadPreviews(){const postcode=sessionStorage.getItem("ceefax:postcode")||"SW1A 1AA";const jobs=[["101","/api/101",d=>d.items?.[0]?.title||d.error||"HEADLINES UNAVAILABLE"],["401","/api/401?postcode="+encodeURIComponent(postcode),d=>d.live?(d.location+": "+d.temperature+"°C · "+d.description):(d.error||"SET A POSTCODE")],["501","/api/501",d=>{const trouble=d.lines?.find(x=>!x.good);return trouble?(trouble.name+": "+trouble.status):(d.lines?.[0]?"TUBE: "+d.lines[0].status:"TUBE STATUS UNAVAILABLE")}],["601","/api/601",d=>d.live?d.forecast+" gCO₂/kWh · "+d.index:(d.error||"GRID DATA UNAVAILABLE")],["701","/api/701",d=>{const trouble=d.lines?.find(x=>!x.good);return trouble?(trouble.name+": "+trouble.status):(d.lines?.[0]?"LONDON SERVICES: "+d.lines[0].status:"TRAVEL UPDATES UNAVAILABLE")}]];await Promise.all(jobs.map(async([id,url,format])=>{try{const d=await fetch(url,{cache:"no-store"}).then(r=>r.json());preview(id,format(d),Boolean(d.live))}catch{preview(id,"LIVE DATA UNAVAILABLE",false)}}));preview("777","TEXT + LIVE DATA → CHIPTUNE",true)}
function weatherMarkup(d){const form='<form class="postcode-form" id="postcodeForm"><label for="postcode">UK POSTCODE</label><input id="postcode" maxlength="8" placeholder="e.g. LS1 1UR" value="'+esc(d.postcode||"")+'"><button type="submit">SET</button></form>';if(!d.live)return form+'<div class="message error">'+esc(d.error||"ENTER A UK POSTCODE.")+"</div>";return form+`<div class="data-grid"><div class="data-box"><div class="data-label">${esc(d.location||"LOCAL WEATHER")}</div><div class="data-value">${esc(d.temperature)}°C</div><div class="data-note">${esc(d.description)}</div></div><div class="data-box"><div class="data-label">FEELS LIKE</div><div class="data-value">${esc(d.apparent)}°C</div><div class="data-note">WIND ${esc(d.wind)} km/h</div></div><div class="data-box"><div class="data-label">RAIN · LAST 15 MIN</div><div class="data-value">${esc(d.precipitation)} mm</div></div><div class="data-box"><div class="data-label">HUMIDITY</div><div class="data-value">${esc(d.humidity)}%</div></div></div>`}
function bindPostcode(){const form=$("#postcodeForm");if(form)form.addEventListener("submit",e=>{e.preventDefault();const v=$("#postcode").value.trim().toUpperCase();if(v){sessionStorage.setItem("ceefax:postcode",v);openPage("401",true)}})}
function linesMarkup(lines,error){return lines?.length?'<ul class="line-list">'+lines.map(x=>'<li><span class="line-name">'+esc(x.name)+'</span><span class="line-status '+(x.good?"good":"bad")+'">'+esc(x.status)+(x.detail?'<span class="line-detail">'+esc(x.detail)+"</span>":"")+"</span></li>").join("")+"</ul>":'<div class="message error">'+esc(error||"NO LIVE UPDATES.")+"</div>"}
function renderStudio(){const html='<div class="page-heading"><div><h1>777 · 8-BIT SOUND STUDIO</h1><div class="page-kicker">BONUS PAGE · TEXT TO CHIPTUNE</div></div></div><div class="updated">LOCAL SYNTH · NO DATA FEED REQUIRED</div><div class="studio-layout"><div><textarea id="words" maxlength="240">The city hums after midnight</textarea><div class="studio-controls"><button id="play">▶ MAKE A TRACK</button><button id="sample">SAMPLE LONDON DATA</button><select id="mood"><option value="auto">AUTO MOOD</option><option value="upbeat">UPBEAT</option><option value="moody">MOODY</option></select></div><div id="status" class="data-note">READY · PENTATONIC SYNTH</div><canvas id="scope" width="700" height="120"></canvas></div><aside class="cassette"><div><div class="data-label">SIDE A · CEEFAX ORIGINAL</div><div id="trackTitle" class="cassette-title">MIDNIGHT TRANSMISSION</div><div id="trackMeta" class="data-note">128 BPM · PENTATONIC</div></div><div class="tape"><div class="reel paused" id="reel1"></div><span>▶ ▷ ▶</span><div class="reel paused" id="reel2"></div></div><div class="data-note">REC ● · LONDON FM</div></aside></div>';$("#view").innerHTML=html;$("#play").onclick=()=>makeTrack($("#words").value);$("#sample").onclick=sampleTrack}
function drawWave(buffer){const c=$("#scope"),ctx=c.getContext("2d"),data=buffer.getChannelData(0);ctx.clearRect(0,0,c.width,c.height);ctx.strokeStyle="#00ffff";ctx.lineWidth=2;ctx.beginPath();for(let i=0;i<data.length;i++){const x=i/(data.length-1)*c.width,y=(1-data[i])*c.height/2;i?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.stroke()}
async function makeTrack(text){$("#status").textContent="COMPOSING…";try{const query="?text="+encodeURIComponent(text)+"&mood="+$("#mood").value,data=await fetch("/api/song"+query).then(r=>r.json()),audio=await fetch("/api/song.wav"+query).then(r=>r.arrayBuffer());$("#trackTitle").textContent=data.title.toUpperCase();$("#trackMeta").textContent=data.bpm+" BPM · "+data.mood.toUpperCase()+" · "+data.notes+" NOTES";if(!audioContext)audioContext=new AudioContext();if(audioSource)audioSource.stop();const decoded=await audioContext.decodeAudioData(audio);drawWave(decoded);audioSource=audioContext.createBufferSource();audioSource.buffer=decoded;audioSource.connect(audioContext.destination);audioSource.onended=()=>{$("#reel1").classList.add("paused");$("#reel2").classList.add("paused")};await audioContext.resume();audioSource.start();$("#reel1").classList.remove("paused");$("#reel2").classList.remove("paused");$("#status").textContent=data.mood.toUpperCase()+" MODE · "+data.duration+" SEC"}catch{$("#status").textContent="SYNTH ERROR · PLEASE TRY AGAIN"}}
async function sampleTrack(){const button=$("#sample");button.disabled=true;$("#status").textContent="READING LIVE PAGES…";try{const d=await fetch("/api/sample").then(r=>r.json());$("#words").value=d.text;$("#mood").value="auto";await makeTrack(d.text)}catch{$("#status").textContent="LIVE DATA OFFLINE · WRITE YOUR OWN TEXT"}finally{button.disabled=false}}
async function openPage(raw,replace=false){const p=String(raw).trim().padStart(3,"0");if(!(p in pages)){$("#view").innerHTML='<div class="message error">PAGE NOT FOUND · TRY 100, 101, 401, 501, 601, 701 OR 777.</div>';return}currentPage=p;document.title="Ceefax 2026 · Page "+p+" "+pages[p];$("#headerPage").textContent=p;$("#pageInput").value=p;if(!replace)history.pushState({page:p},"","#"+p);else history.replaceState({page:p},"","#"+p);if(p==="100"){indexPage();return}if(p==="777"){renderStudio();return}$("#view").innerHTML='<div class="message">RECEIVING TRANSMISSION…</div>';try{let q=p==="401"?"?postcode="+encodeURIComponent(sessionStorage.getItem("ceefax:postcode")||""):"";const data=await fetch("/api/"+p+q,{cache:"no-store"}).then(r=>r.json());if(p==="101")data.html=data.items?.length?'<ul class="news-list">'+data.items.map((item,i)=>'<li><a href="'+esc(item.url||"#")+'" target="_blank" rel="noopener noreferrer"><span class="story-no">'+String(i+1).padStart(2,"0")+"</span>"+esc(item.title)+"</a>"+(item.date?'<span class="story-date">'+esc(item.date)+"</span>":"")+"</li>").join("")+"</ul>":'<div class="message error">'+esc(data.error||"NO HEADLINES RECEIVED.")+"</div>";if(p==="401")data.html=weatherMarkup(data);if(p==="501"||p==="701")data.html=linesMarkup(data.lines,data.error);if(p==="601")data.html=data.live?'<div class="data-grid"><div class="data-box"><div class="data-label">CARBON INTENSITY</div><div class="data-value">'+esc(data.forecast)+' <span style="font-size:15px">gCO₂/kWh</span></div><div class="data-note">'+esc(data.index)+" · "+esc(data.period)+'</div></div><div class="data-box"><div class="data-label">REGION</div><div class="data-value" style="font-size:22px">GREAT BRITAIN</div><div class="data-note">'+(data.actual===null?"Forecast":"Actual "+esc(data.actual)+" gCO₂/kWh")+"</div></div></div>":'<div class="message error">'+esc(data.error||"GRID DATA UNAVAILABLE.")+"</div>";$("#view").innerHTML=frame(data);if(p==="401")bindPostcode()}catch{$("#view").innerHTML='<div class="message error">SIGNAL LOST · USE REFRESH TO TRY AGAIN.</div>'}}
document.addEventListener("click",e=>{const link=e.target.closest("[data-page]");if(link){e.preventDefault();openPage(link.dataset.page)}});$("#pageForm").addEventListener("submit",e=>{e.preventDefault();openPage($("#pageInput").value)});$("#refresh").onclick=()=>openPage(currentPage,true);window.addEventListener("popstate",()=>openPage(location.hash.slice(1)||"100",true));openPage(location.hash.slice(1)||"100",true);
</script></body></html>""".replace("__CSS__",CSS)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch_bytes(url: str, timeout: int = TIMEOUT) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "Ceefax2026/1.0 (+local information service)", "Accept": "application/json, application/rss+xml, application/xml"})
    with urllib.request.urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
        return response.read()


def fetch_json(url: str) -> dict | list:
    return json.loads(fetch_bytes(url))


def service_error(exc: Exception, fallback: str) -> dict:
    message = "CHECK THE DETAILS AND TRY AGAIN." if isinstance(exc, urllib.error.HTTPError) and exc.code in (400, 404) else fallback
    return {"live": False, "error": message, "updated": now_iso()}


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
        place = fetch_json("https://api.postcodes.io/postcodes/" + urllib.parse.quote(postcode.replace(" ", ""), safe=""))
        result = place.get("result") if isinstance(place, dict) else None
        if not result:
            return {"live": False, "updated": now_iso(), "postcode": postcode, "error": "POSTCODE NOT FOUND. CHECK IT AND TRY AGAIN."}
        params = urllib.parse.urlencode({"latitude": result["latitude"], "longitude": result["longitude"], "current": "temperature_2m,apparent_temperature,relative_humidity_2m,precipitation,weather_code,wind_speed_10m", "timezone": "auto"})
        current = fetch_json("https://api.open-meteo.com/v1/forecast?" + params)["current"]
        descriptions = {0:"CLEAR SKY",1:"MAINLY CLEAR",2:"PARTLY CLOUDY",3:"OVERCAST",45:"FOG",48:"RIME FOG",51:"LIGHT DRIZZLE",53:"DRIZZLE",55:"HEAVY DRIZZLE",61:"LIGHT RAIN",63:"RAIN",65:"HEAVY RAIN",71:"LIGHT SNOW",73:"SNOW",75:"HEAVY SNOW",80:"RAIN SHOWERS",81:"SHOWERS",82:"HEAVY SHOWERS",95:"THUNDERSTORM",96:"THUNDERSTORM + HAIL",99:"THUNDERSTORM + HAIL"}
        return {"live": True, "updated": now_iso(), "postcode": result.get("postcode", postcode), "location": result.get("admin_district") or result.get("region") or "UK LOCATION", "temperature": round(current["temperature_2m"]), "apparent": round(current["apparent_temperature"]), "humidity": current["relative_humidity_2m"], "precipitation": current["precipitation"], "wind": round(current["wind_speed_10m"]), "description": descriptions.get(current.get("weather_code"), "CURRENT CONDITIONS")}
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
        if route.path == "/":
            return self.respond(PAGE.encode(), "text/html; charset=utf-8")
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
