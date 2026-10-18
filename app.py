"""
GrabNest backend (Flask + yt-dlp) - koi RapidAPI / API limit nahi.
Instagram Reel, YouTube Video/Song, Facebook Video: yt-dlp se seedha link track karke download.
Server par ffmpeg zaroori hai (Dockerfile mein already hai).
"""
import os, re, glob, shutil, tempfile, time, threading, base64
from urllib.parse import urlparse

import yt_dlp
from flask import Flask, request, jsonify, send_file, after_this_request
from flask_cors import CORS

app = Flask(__name__)
ORIGIN = os.environ.get("ALLOWED_ORIGIN", "*")  # jaise https://username.github.io
CORS(app, origins="*" if ORIGIN == "*" else [o.strip() for o in ORIGIN.split(",")],
     expose_headers=["Content-Disposition", "Content-Length"])

ALLOWED = ("youtube.com", "youtu.be", "instagram.com", "facebook.com", "fb.watch", "fb.com")
MAX_SECONDS = int(os.environ.get("MAX_MINUTES", "60")) * 60
RATE_LIMIT = 15                                   # ek IP se 1 minute mein max requests
jobs = threading.Semaphore(int(os.environ.get("MAX_JOBS", "2")))   # server ek saath kitne download kare
_hits, _lock = {}, threading.Lock()

COOKIES = os.environ.get("COOKIES_FILE")
if os.environ.get("COOKIES_B64"):                 # cookies.txt ko base64 karke env mein daal sakte ho
    COOKIES = "/tmp/cookies.txt"
    with open(COOKIES, "wb") as f:
        f.write(base64.b64decode(os.environ["COOKIES_B64"]))


class ApiError(Exception):
    def __init__(self, msg, status=422):
        super().__init__(msg)
        self.msg, self.status = msg, status


def host_ok(url):
    try:
        u = urlparse(url)
        h = (u.hostname or "").lower()
    except Exception:
        return False
    return u.scheme in ("http", "https") and any(h == d or h.endswith("." + d) for d in ALLOWED)


def client_ip():
    return (request.headers.get("X-Forwarded-For", request.remote_addr) or "").split(",")[0].strip()


def guard(url):
    if not host_ok(url):
        raise ApiError("Ye link supported nahi hai.", 400)
    now, ip = time.time(), client_ip()
    with _lock:
        hits = [t for t in _hits.get(ip, []) if now - t < 60]
        if len(hits) >= RATE_LIMIT:
            _hits[ip] = hits
            raise ApiError("Bahut zyada requests. 1 minute ruk kar try karo.", 429)
        hits.append(now)
        _hits[ip] = hits


def opts():
    o = {"quiet": True, "no_warnings": True, "noplaylist": True, "socket_timeout": 30}
    if COOKIES and os.path.exists(COOKIES):
        o["cookiefile"] = COOKIES
    return o


def friendly(e):
    t = str(e).lower()
    if "sign in to confirm" in t or "not a bot" in t:
        return "YouTube ne server ko block kiya hai. Server par cookies lagani padengi (README dekho)."
    if "login" in t or "private" in t or "cookies" in t or "rate-limit" in t:
        return "Ye video private hai ya login maang raha hai. Public link try karo."
    if "unsupported url" in t:
        return "Ye link supported nahi hai."
    return "Video nahi mila. Link check karke dobara try karo."


def fmt_time(s):
    if not s:
        return ""
    s = int(s)
    return f"{s // 3600}:{s % 3600 // 60:02d}:{s % 60:02d}" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


@app.errorhandler(ApiError)
def on_err(e):
    return jsonify(error=e.msg), e.status


@app.get("/")
def health():
    return jsonify(ok=True, name="GrabNest API", yt_dlp=yt_dlp.version.__version__)


@app.get("/info")
def info():
    url, kind = request.args.get("url", "").strip(), request.args.get("kind", "video")
    guard(url)
    try:
        with yt_dlp.YoutubeDL({**opts(), "skip_download": True}) as y:
            d = y.extract_info(url, download=False)
    except Exception as e:
        raise ApiError(friendly(e))
    if d.get("_type") == "playlist" and d.get("entries"):
        d = d["entries"][0]
    if (d.get("duration") or 0) > MAX_SECONDS:
        raise ApiError(f"Video bahut lamba hai (max {MAX_SECONDS // 60} minute).")
    if kind == "audio":
        quals = [["320 kbps", "MP3", 320], ["192 kbps", "MP3", 192], ["128 kbps", "MP3", 128]]
    else:
        hs = sorted({f["height"] for f in d.get("formats", []) if f.get("height") and f.get("vcodec") != "none" and f["height"] >= 240}, reverse=True)
        quals = [[f"{h}p", "MP4", h] for h in hs[:5]] or [["Best", "MP4", 4320]]
    t = fmt_time(d.get("duration"))
    meta = (t + " · " if t else "") + ("Audio" if kind == "audio" else "Video")
    return jsonify(title=d.get("title") or "Video", meta=meta, thumb=d.get("thumbnail"), qualities=quals)


@app.get("/download")
def download():
    url, kind = request.args.get("url", "").strip(), request.args.get("kind", "video")
    try:
        q = int(request.args.get("q", "720"))
    except ValueError:
        q = 720
    guard(url)
    if not jobs.acquire(timeout=90):
        raise ApiError("Server abhi busy hai. Thodi der baad try karo.", 503)
    tmp = tempfile.mkdtemp(prefix="sn_")
    try:
        o = {**opts(), "outtmpl": os.path.join(tmp, "%(title).80s.%(ext)s"),
             "match_filter": yt_dlp.utils.match_filter_func(f"duration<={MAX_SECONDS}")}
        if kind == "audio":
            o.update(format="bestaudio/best", postprocessors=[{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": str(q)}])
        else:
            h = f"[height<={q}]"
            o.update(format=f"bestvideo{h}[ext=mp4]+bestaudio[ext=m4a]/best{h}[ext=mp4]/bestvideo{h}+bestaudio/best{h}/best",
                     merge_output_format="mp4")
        with yt_dlp.YoutubeDL(o) as y:
            y.download([url])
        files = glob.glob(os.path.join(tmp, "*"))
        if not files:
            raise RuntimeError("no file")
    except Exception as e:
        shutil.rmtree(tmp, ignore_errors=True)
        raise ApiError(friendly(e), 500)
    finally:
        jobs.release()

    @after_this_request
    def cleanup(resp):
        shutil.rmtree(tmp, ignore_errors=True)
        return resp

    path = files[0]
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
