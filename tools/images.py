"""All sips interaction lives here.

sips can read HEIC and JFIF but cannot write WebP, so every output is JPEG.
Sizes and qualities below were measured against a real 5472x3648 Canon
original from the archive: 1400px/q68 lands at ~267 KB, 480px/q70 at ~60 KB.
"""
import os
import subprocess

WEB_MAX_PX = 1400
WEB_QUALITY = 68
THUMB_MAX_PX = 480
THUMB_QUALITY = 70

# Extensions allowed to reach assets/. HEIC, JFIF, TIF, DNG, MOV and ZIP
# all appear in the archive and none of them belong on the web.
PUBLISHABLE = ("jpg", "jpeg", "png")


class SipsError(RuntimeError):
    pass


def _sips(args):
    proc = subprocess.Popen(
        ["sips"] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise SipsError("sips %s failed: %s" % (" ".join(args), err.decode("utf-8", "replace").strip()))
    return out.decode("utf-8", "replace")


def dimensions(path):
    """Return (width, height). Raises SipsError if the file is not an image."""
    out = _sips(["-g", "pixelWidth", "-g", "pixelHeight", path])
    found = {}
    for line in out.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in ("pixelWidth", "pixelHeight"):
            value = value.strip()
            if value == "<nil>":
                raise SipsError("no pixel dimensions in sips output for %s" % path)
            try:
                # sips may report dimensions as floats (e.g., PDF pages: 959.760)
                # Parse as float first, then round to int to avoid truncation.
                found[key] = int(round(float(value)))
            except ValueError:
                raise SipsError("unparseable dimension '%s' in sips output for %s" % (value, path))
    if "pixelWidth" not in found or "pixelHeight" not in found:
        raise SipsError("no pixel dimensions in sips output for %s" % path)
    return (found["pixelWidth"], found["pixelHeight"])


def to_jpeg(src, dst, max_px, quality):
    """Convert src to a JPEG at dst, fitting the long edge within max_px.

    Measured on sips-316: `-Z` UPSCALES a smaller source -- a 64x48 image
    at `-Z 4000` comes back 4000x3000 and 190 KB. That is pure waste, and
    the archive does contain small screenshots and JFIF captures alongside
    the 5472x3648 Canon originals. So clamp the target to the source's own
    long edge and let small images through untouched.

    Returns {"w", "h", "bytes"}.
    """
    parent = os.path.dirname(dst)
    if parent:
        os.makedirs(parent, exist_ok=True)
    src_w, src_h = dimensions(src)
    target = min(max_px, max(src_w, src_h))
    _sips(["-s", "format", "jpeg",
           "-s", "formatOptions", str(quality),
           "-Z", str(target),
           src, "--out", dst])
    w, h = dimensions(dst)
    return {"w": w, "h": h, "bytes": os.path.getsize(dst)}


def web(src, dst):
    return to_jpeg(src, dst, WEB_MAX_PX, WEB_QUALITY)


def thumb(src, dst):
    return to_jpeg(src, dst, THUMB_MAX_PX, THUMB_QUALITY)
