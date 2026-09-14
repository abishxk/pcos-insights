Drop the real fallback display face here as:

    GeistPixel-Circle.woff2

It is referenced by static/landing.css as a swap-display @font-face and is
only a fallback for the primary display family "BubbledotICG-FinePos" (loaded
from OnlineWebFonts). If this file is absent the landing page still renders:
the browser falls back to BubbledotICG-FinePos, then to monospace.
