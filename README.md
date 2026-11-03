# BiliTV Downloader — Python CLI

Batch downloader for Bili.tv streams accessible to your account/session. Python 3.10+ and FFmpeg required. **No DRM bypass**. Respect content rights and service terms.

## Windows setup

1. Install Python 3.10+ and FFmpeg. Check `python --version` and `ffmpeg -version`.
2. Open PowerShell in this folder:

```powershell
python -m pip install -r requirements.txt
python bilitv_downloader.py --list links.txt --output "D:\Videos" --prefix "Anime" --subtitle --retry 3
```

Put one URL per line in `links.txt`. Blank lines and `#` comments are ignored. Direct URLs also work:

```powershell
python bilitv_downloader.py "https://www.bilibili.tv/video/1234567890" --output Downloads
```

Output filenames: `Anime_001.mp4`, `Anime_002.mp4`, etc. Existing completed outputs are skipped. Partial video/audio files may be retained after failures for diagnosis, but retry starts those downloads again.

## Cookies

For videos you are authorized to access, optionally supply `--cookies cookies.txt`. Accepted formats:
- Netscape/Mozilla cookies.txt (domain-scoped Bilibili cookies)
- A plain-text `name=value; name2=value2` Cookie header (without the word `Cookie:` is fine)

Cookies are sent only to the Bili.tv API session, never directly to media/subtitle URLs. **Keep cookies private** and never commit them. The tool refuses HTTP redirects rather than forwarding sensitive headers to another host. If the provider uses a CDN redirect, that download will fail safely.

## Subtitles

`--subtitle` downloads subtitles **only when subtitle descriptors are exposed by the current API response**. It saves VTT/SRT when recognized, or raw JSON/TXT otherwise; it does not translate or convert JSON into SRT. Missing subtitles are not a fatal error. Some content requires another subtitle endpoint not implemented here.

## Retry and progress

`--retry 3` means up to three download attempts per video/audio/subtitle file. Progress uses tqdm. API requests have their own automatic retry on transient HTTP errors.

## Build Windows EXE

On Windows run `build_exe.bat`. EXE appears at `dist\BiliTV-Downloader.exe`. Keep FFmpeg installed in PATH or put `ffmpeg.exe` beside the EXE. Example:

```powershell
.\dist\BiliTV-Downloader.exe --list links.txt --output "D:\Videos" --prefix "Anime" --subtitle --retry 3
```

GitHub Actions also builds a Windows EXE artifact on manual dispatch and publishes it as a release asset when pushing a `v*` tag. To publish: `git tag v1.0.0` then `git push origin v1.0.0`. The workflow requires GitHub Actions write permission for releases.

## Testing

```powershell
python -m unittest discover -s tests -v
python bilitv_downloader.py --help
```

## Limitations

Bili.tv API and media response formats may change. This project has static and unit testing, **not a verified live Bili.tv download**. Some protected streams, unsupported subtitle formats, and redirecting CDNs may fail. The tool downloads sequentially to reduce rate-limit risk. It never runs downloaded data as executable code. Media links returned by the API must be HTTPS; for stronger network security use a trusted network/proxy.

## GUI Windows (new)

Run `python bilitv_gui.py` (or double-click `run_gui.bat`) after installing `requirements.txt`. Tkinter ships with standard Windows Python installations.

Paste one Bili.tv URL per line. To name an individual video, use:

```text
https://www.bilibili.tv/video/1234567890 | Tap 01
https://www.bilibili.tv/video/1234567891 | Tap 02
https://www.bilibili.tv/video/1234567892
```

The last URL uses the prefix (`BiliTV_003.mp4` by default). The first two become `Tap 01.mp4` and `Tap 02.mp4`. The interface lets you browse for an output directory, select optional cookies.txt, choose subtitle downloads, set retries, import TXT links, and see progress/logs. Downloads run in a background thread so the window stays responsive. The Stop button stops *after the current video*, not immediately. Existing files are skipped, not overwritten.

Build GUI EXE on Windows by double-clicking `build_gui_exe.bat`; output is `dist/BiliTV-Downloader-GUI.exe`. You still need FFmpeg in PATH or `ffmpeg.exe` alongside the EXE. GitHub Actions builds both CLI and GUI EXEs. This ZIP contains the **build script**, not a precompiled Windows binary (building Windows binaries requires Windows).

**Important:** The backend has not been verified against a live Bili.tv download. Do not use protected content or bypass DRM. Treat cookie files as secrets and do not upload them to GitHub. The GUI currently displays transfer byte progress, not a combined end-to-end percentage including FFmpeg processing.

## GUI v1.2 — custom start number

GUI naming now has two separate fields: **Tên file (tiền tố)** and **Số bắt đầu**. For example `tập_` and `22` produce `tập_22.mp4`, `tập_23.mp4`, `tập_24.mp4` for the first three links. A zero-padded start number such as `0022` preserves padding. Explicit `URL | Custom Name` overrides generated names. Duplicate output names are rejected before downloading. The GUI displays a live filename preview.


## Cookie trực tiếp từ Chrome / Edge (GUI v1.3.1)

1. Đăng nhập `https://www.bilibili.tv/` bằng Chrome hoặc Edge trên chính máy Windows đang chạy tool.
2. Mở GUI và chọn **Nguồn cookie → Chrome** hoặc **Edge**. Không cần xuất `cookies.txt`.
3. Dán link, chọn thư mục, đặt tên và nhấn **Bắt đầu tải**.
4. Nếu trình duyệt chặn đọc cookie (mã hóa hoặc khóa profile), chọn **File TXT** và dùng cookie của chính tài khoản của bạn.

Tool chỉ nạp cookie có domain `bilibili.tv` hoặc subdomain, không lưu giá trị cookie vào file hay log; phiên tải media CDN không mang cookie đăng nhập. Không commit cookie vào GitHub. Chế độ này không vượt DRM hay quyền Premium. Đóng Chrome/Edge có thể giúp xử lý lỗi profile bị khóa, nhưng không đảm bảo tương thích với mọi phiên bản trình duyệt.

**Build EXE:** `build_gui_exe.bat` (trên Windows). Sau khi push mã nguồn, tạo tag mới `v1.3.0` để GitHub Actions build và phát hành phiên bản mới.
