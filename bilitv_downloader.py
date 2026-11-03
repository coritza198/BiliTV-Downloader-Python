#!/usr/bin/env python3
"""Batch downloader for Bili.tv media accessible to the user's session."""
from __future__ import annotations
import argparse
import http.cookiejar
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm

API = 'https://api.bilibili.tv/intl/gateway/web/playurl'
REFERER = 'https://www.bilibili.tv/'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'


def parse_link(url: str) -> dict:
    p = urlparse(url.strip())
    if p.scheme != 'https' or (p.hostname or '').lower() not in ('bilibili.tv', 'www.bilibili.tv') or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Only https://www.bilibili.tv links are accepted')
    parts = p.path.strip('/').split('/')
    if 'video' in parts:
        i = parts.index('video')
        if len(parts) <= i + 1 or not parts[i+1].isdigit():
            raise ValueError('Invalid /video/ID link')
        return dict(aid=parts[i+1], qn=120, s_locale='en_US', platform='web')
    if 'play' in parts:
        i = parts.index('play')
        if len(parts) <= i + 2 or not parts[i+1].isdigit() or not parts[i+2].isdigit():
            raise ValueError('Expected /play/SEASON_ID/EPISODE_ID')
        return dict(ep_id=parts[i+2], device='wap', platform='web', qn=64, tf=0, type=0)
    raise ValueError('Unsupported Bili.tv URL path')


def load_cookies(session: requests.Session, path: str | None):
    if not path:
        return
    f = Path(path)
    if not f.is_file():
        raise ValueError(f'Cookie file not found: {f}')
    raw = f.read_text(encoding='utf-8-sig').strip()
    if raw.startswith('# Netscape HTTP Cookie File') or '\t' in raw and any(line.count('\t') >= 6 for line in raw.splitlines()):
        jar = http.cookiejar.MozillaCookieJar(str(f))
        jar.load(ignore_discard=True, ignore_expires=True)
        for c in jar:
            domain = c.domain.lstrip('.').lower()
            if domain == 'bilibili.tv' or domain.endswith('.bilibili.tv'):
                session.cookies.set(c.name, c.value, domain=c.domain, path=c.path)
        return
    # Cookie: a=b; c=d (raw header format). Keep it on the API request ONLY.
    lines = [x.strip() for x in raw.splitlines() if x.strip() and not x.lstrip().startswith('#')]
    cookie = '; '.join(x.removeprefix('Cookie:').strip() for x in lines)
    if '\r' in cookie or '\n' in cookie or not cookie or '=' not in cookie:
        raise ValueError('Invalid cookie header file')
    session.headers['Cookie'] = cookie


def load_browser_cookies(session: requests.Session, browser: str) -> int:
    """Read only Bilibili cookies from the current user's local Chrome/Edge profile.

    No cookie values are written to disk or logs. Browser encryption may prevent
    reading cookies on some Chrome/Edge versions or locked profiles.
    """
    if browser not in ('chrome', 'edge'):
        raise ValueError('Browser must be chrome or edge')
    try:
        import browser_cookie3
    except ImportError as e:
        raise RuntimeError('Thiếu browser-cookie3. Chạy: pip install -r requirements.txt') from e
    try:
        jar = getattr(browser_cookie3, browser)(domain_name='bilibili.tv')
    except Exception as e:
        raise RuntimeError(f'Không đọc được cookie {browser}. Thử đóng trình duyệt, chạy cùng tài khoản Windows, hoặc chọn File TXT. ({type(e).__name__})') from e
    count = 0
    for cookie in jar:
        domain = cookie.domain.lstrip('.').lower()
        if domain == 'bilibili.tv' or domain.endswith('.bilibili.tv'):
            session.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path, secure=cookie.secure)
            count += 1
    if count == 0:
        raise RuntimeError('Không tìm thấy cookie Bilibili.tv. Hãy đăng nhập Bilibili.tv trên trình duyệt đã chọn.')
    return count


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({'User-Agent': UA, 'Referer': REFERER})
    retry = Retry(total=3, connect=3, read=3, status=3, backoff_factor=0.8,
                  status_forcelist=[429, 500, 502, 503, 504], allowed_methods=['GET'], respect_retry_after_header=True)
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s


def check_media_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.port not in (None, 443):
        raise ValueError('Rejected unsafe or non-HTTPS media URL')
    h = p.hostname.lower()
    if h == 'localhost' or h.endswith(('.localhost', '.local', '.internal')):
        raise ValueError('Rejected local media host')
    return url


def subtitle_candidates(node):
    """Discover explicit subtitle descriptors; never treat arbitrary URL fields as subtitles."""
    found = []
    def walk(obj, depth=0):
        if depth > 9:
            return
        if isinstance(obj, dict):
            for key, val in obj.items():
                if key.lower() in ('subtitles', 'subtitle', 'subtitle_list', 'subtitle_resource'):
                    entries = val if isinstance(val, list) else [val]
                    for entry in entries:
                        if isinstance(entry, dict):
                            u = entry.get('url') or entry.get('subtitle_url') or entry.get('file_url')
                            if isinstance(u, str) and u.startswith('https://'):
                                label = str(entry.get('lang') or entry.get('language') or entry.get('lan') or entry.get('locale') or 'und')
                                found.append((label, u))
                walk(val, depth + 1)
        elif isinstance(obj, list):
            for x in obj:
                walk(x, depth + 1)
    walk(node)
    return list(dict.fromkeys(found))


def get_streams(session: requests.Session, url: str):
    # No redirects: raw cookies cannot be forwarded to other hosts.
    with session.get(API, params=parse_link(url), timeout=(15, 35), allow_redirects=False) as r:
        if r.is_redirect:
            raise RuntimeError('API redirect rejected to protect cookies')
        r.raise_for_status()
        payload = r.json()
    if payload.get('code') not in (None, 0):
        raise RuntimeError(f"Bili.tv API error: {payload.get('code')} {payload.get('message', '')}")
    data = payload.get('data') or {}
    play = data.get('playurl') or {}
    vids = sorted(play.get('video') or [], key=lambda x: (x.get('stream_info') or {}).get('quality') or 0, reverse=True)
    auds = sorted(play.get('audio_resource') or [], key=lambda x: x.get('quality') or 0, reverse=True)
    video = next((x.get('video_resource', {}).get('url') for x in vids if x.get('video_resource', {}).get('url')), None)
    audio = next((x.get('url') for x in auds if x.get('url')), None)
    if not video or not audio:
        raise RuntimeError('No video/audio streams available; content may be restricted or API changed')
    return check_media_url(video), check_media_url(audio), subtitle_candidates(data)


def fetch_file(session: requests.Session, url: str, dest: Path, label: str, attempts: int, progress_callback=None):
    check_media_url(url)
    # Use a fresh, cookie-free session for each CDN download.
    for attempt in range(1, attempts + 1):
        try:
            with requests.Session() as cdn:
                cdn.trust_env = session.trust_env
                cdn.headers.update({'User-Agent': UA, 'Referer': REFERER})
                with cdn.get(url, stream=True, timeout=(15, 60), allow_redirects=False) as r:
                    if r.is_redirect:
                        raise RuntimeError('CDN redirect rejected')
                    r.raise_for_status()
                    size = int(r.headers.get('Content-Length') or 0)
                    with dest.open('wb') as f, tqdm(total=size or None, unit='B', unit_scale=True, desc=label, leave=False) as bar:
                        for chunk in r.iter_content(chunk_size=256 * 1024):
                            if chunk:
                                f.write(chunk)
                                bar.update(len(chunk))
                                if progress_callback:
                                    progress_callback(label, bar.n, size)
                    if dest.stat().st_size == 0 or (size and dest.stat().st_size != size):
                        raise IOError('Incomplete or empty download')
            return
        except (requests.RequestException, OSError, RuntimeError) as e:
            dest.unlink(missing_ok=True)
            if attempt == attempts:
                raise RuntimeError(f'{label}: failed after {attempts} attempt(s): {e}') from e
            print(f'  Retry {attempt}/{attempts-1} for {label}: {e}', file=sys.stderr)
            time.sleep(min(2 ** (attempt - 1), 8))


def subtitle_extension(raw: bytes) -> str:
    s = raw.lstrip(b'\xef\xbb\xbf \t\r\n')
    if s.startswith(b'WEBVTT'):
        return '.vtt'
    if re.match(rb'\d+\s*\r?\n\d\d:\d\d:\d\d[,\.]\d+', s):
        return '.srt'
    return '.json' if s.startswith((b'{', b'[')) else '.txt'


def safe_lang(s: str) -> str:
    return re.sub(r'[^A-Za-z0-9_-]', '_', s)[:24] or 'und'


def ffmpeg_path() -> str:
    # Can be bundled alongside EXE, or installed in PATH.
    base = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent
    local = base / ('ffmpeg.exe' if sys.platform == 'win32' else 'ffmpeg')
    return str(local) if local.is_file() else (shutil.which('ffmpeg') or '')


def run_job(api: requests.Session, url: str, idx: int, count: int, out: Path, prefix: str, attempts: int, subtitles: bool, ffmpeg: str, stem_override=None, progress_callback=None) -> str:
    stem = stem_override if stem_override is not None else f'{prefix}_{idx:03d}'
    final = out / (stem + '.mp4')
    if final.exists() and final.stat().st_size:
        print(f'[{idx}/{count}] SKIP {final.name} (already exists)')
        return 'skip'
    print(f'[{idx}/{count}] {url}', flush=True)
    video, audio, subs = get_streams(api, url)
    vfile = out / (stem + '.video.part')
    afile = out / (stem + '.audio.part')
    mux = out / (stem + '.mux.part.mp4')
    try:
        fetch_file(api, video, vfile, 'Video', attempts, progress_callback)
        fetch_file(api, audio, afile, 'Audio', attempts, progress_callback)
        result = subprocess.run([ffmpeg, '-nostdin', '-hide_banner', '-loglevel', 'error', '-y',
                                 '-i', str(vfile), '-i', str(afile), '-map', '0:v:0', '-map', '1:a:0',
                                 '-c', 'copy', str(mux)], capture_output=True, text=True, timeout=3600, check=False)
        if result.returncode or not mux.exists() or mux.stat().st_size == 0:
            raise RuntimeError('FFmpeg mux failed: ' + result.stderr[-800:])
        mux.replace(final)
        vfile.unlink(missing_ok=True)
        afile.unlink(missing_ok=True)
    finally:
        mux.unlink(missing_ok=True)
    if subtitles:
        if not subs:
            print('  No subtitles advertised by API (not necessarily unavailable).')
        for j, (lang, suburl) in enumerate(subs, 1):
            tmp = out / (stem + f'.sub{j}.part')
            try:
                fetch_file(api, suburl, tmp, 'Subtitle', attempts, progress_callback)
                raw = tmp.read_bytes()
                ext = subtitle_extension(raw)
                name = out / (stem + '.' + safe_lang(lang) + (f'_{j}' if j > 1 else '') + ext)
                tmp.replace(name)
                print(f'  Subtitle: {name.name}')
            except Exception as e:
                print(f'  Subtitle warning: {e}', file=sys.stderr)
            finally:
                tmp.unlink(missing_ok=True)
    print(f'  Saved: {final}')
    return 'ok'


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description='Bili.tv batch downloader (authorized content only)')
    p.add_argument('urls', nargs='*', help='Bili.tv URLs')
    p.add_argument('--list', dest='list_file', help='TXT file with one URL per line')
    p.add_argument('--output', default='Downloads', help='Output folder')
    p.add_argument('--prefix', default='BiliTV', help='Filename prefix')
    p.add_argument('--cookies', help='Cookie header text or Netscape cookies.txt')
    p.add_argument('--subtitle', action='store_true', help='Download subtitles exposed by API')
    p.add_argument('--retry', type=int, default=3, help='Media download attempts, 1-10 (default 3)')
    args = p.parse_args(argv)
    urls = list(args.urls)
    if args.list_file:
        try:
            urls.extend(line.strip() for line in Path(args.list_file).read_text(encoding='utf-8-sig').splitlines() if line.strip() and not line.lstrip().startswith('#'))
        except OSError as e:
            p.error(str(e))
    if not urls:
        p.error('Provide URLs or --list links.txt')
    if not re.fullmatch(r'[\w -]{1,80}', args.prefix, flags=re.UNICODE) or args.prefix.strip() in ('.', '..'):
        p.error('Invalid --prefix')
    if not 1 <= args.retry <= 10:
        p.error('--retry must be between 1 and 10')
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        p.error('FFmpeg missing. Install FFmpeg in PATH or put ffmpeg.exe next to the EXE/script')
    out = Path(args.output).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    api = make_session()
    try:
        load_cookies(api, args.cookies)
    except (ValueError, OSError, http.cookiejar.LoadError) as e:
        p.error(str(e))
    stats = dict(ok=0, skip=0, fail=0)
    for idx, url in enumerate(urls, 1):
        try:
            result = run_job(api, url, idx, len(urls), out, args.prefix, args.retry, args.subtitle, ffmpeg)
            stats[result] += 1
        except (ValueError, RuntimeError, requests.RequestException, OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
            stats['fail'] += 1
            print(f'  FAILED: {e}', file=sys.stderr)
    print(f"Done: {stats['ok']} saved, {stats['skip']} skipped, {stats['fail']} failed. Output: {out}")
    return 1 if stats['fail'] else 0

if __name__ == '__main__':
    sys.exit(main())
