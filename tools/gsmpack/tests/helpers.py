import io

from PIL import Image


def png(alpha=255, size=512):
    buf = io.BytesIO()
    Image.new("RGBA", (size, size), (200, 100, 50, alpha)).save(buf, format="PNG")
    return buf.getvalue()
