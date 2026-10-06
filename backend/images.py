"""Product photos with a consistent white background.

About half of the catalogue photos sit on a black square or have black side bars, so the
grid looked patchy. The photos themselves are not in the repository (and must not be
changed), so the backend whitens them on the way out:

1. Mark "background-dark" pixels: every channel at or below DARK_LIMIT.
2. Starting from the image border, spread through connected background-dark pixels only.
   Dark pixels inside the garment (a navy shadow, black lettering) are never reached,
   because they are not connected to the border through background.
3. Paint the reached pixels white, plus a soft 1-pixel feather so no black outline remains.

Results are cached on disk next to the photos (data/products_white/, git-ignored with
data/), so each photo is processed once. If anything goes wrong, the original is served.
"""

from collections import deque
from io import BytesIO
from pathlib import Path
from threading import Lock

from PIL import Image, ImageFilter

# The black backgrounds are pure black (every channel 0-3), while the darkest navy garments
# have shadows around 10-30. A limit of 8 takes the background and JPEG noise but not
# the fabric — a limit of 34 leaked into three very dark navy garments.
DARK_LIMIT = 8
CACHE_VERSION = "v2"
_locks: dict[str, Lock] = {}
_locks_guard = Lock()


def _background_mask(img: Image.Image) -> Image.Image:
    """'L' mask: 255 where the pixel is dark background connected to the border."""
    rgb = img.convert("RGB")
    width, height = rgb.size
    dark = rgb.point(lambda v: 255 if v <= DARK_LIMIT else 0).split()
    # dark only if all three channels are dark
    dark_all = Image.eval(dark[0], lambda v: v)
    for channel in dark[1:]:
        dark_all = Image.composite(dark_all, Image.new("L", rgb.size, 0), channel)
    dark_px = dark_all.load()

    reached = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()
    for x in range(width):
        for y in (0, height - 1):
            if dark_px[x, y] and not reached[y * width + x]:
                reached[y * width + x] = 1
                queue.append((x, y))
    for y in range(height):
        for x in (0, width - 1):
            if dark_px[x, y] and not reached[y * width + x]:
                reached[y * width + x] = 1
                queue.append((x, y))
    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < width and 0 <= ny < height:
                i = ny * width + nx
                if not reached[i] and dark_px[nx, ny]:
                    reached[i] = 1
                    queue.append((nx, ny))
    return Image.frombytes("L", (width, height), bytes(255 if r else 0 for r in reached))


def whiten(source: Path) -> bytes:
    """JPEG bytes of the photo with its border-connected black background turned white."""
    img = Image.open(source).convert("RGB")
    mask = _background_mask(img)
    if mask.getbbox() is None:  # already a light background
        out = img
    else:
        # Grow the mask by a pixel and blur it, so the anti-aliased dark rim fades to white.
        soft = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(0.8))
        out = Image.composite(Image.new("RGB", img.size, (255, 255, 255)), img, soft)
    buffer = BytesIO()
    out.save(buffer, format="JPEG", quality=90, optimize=True)
    return buffer.getvalue()


def white_version(source: Path, cache_dir: Path) -> Path:
    """Path of the cached white-background copy of `source`, creating it if needed."""
    target = cache_dir / f"{source.stem}.{CACHE_VERSION}.jpg"
    if target.is_file() and target.stat().st_mtime >= source.stat().st_mtime:
        return target
    with _locks_guard:
        lock = _locks.setdefault(source.name, Lock())
    with lock:  # one worker per photo; others wait for the same file
        if not target.is_file():
            cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = target.with_suffix(".tmp")
            tmp.write_bytes(whiten(source))
            tmp.replace(target)
    return target
