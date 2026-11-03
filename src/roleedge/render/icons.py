"""CareCircle's one icon set: simple line icons on a 24x24 grid (stroke = currentColor, no fill).

Cards and video frames draw them with ``icon_svg``; the demo web app gets the same table from
``/api/demo/icons``, so there is only one copy. The model picks content icons by name from
``models.IconName``; UI-only icons (play, eye, ...) are listed after them.
To add an icon: add its SVG elements here (and its name to ``IconName`` if the model may choose it).
"""

from __future__ import annotations

from markupsafe import Markup

ICONS: dict[str, str] = {
    # ---- content icons (models.IconName)
    "phone": '<path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>',
    "video": '<rect x="2" y="6" width="14" height="12" rx="2"/><path d="m16 10 6-3v10l-6-3"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 10h18"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "document": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
    "bill": '<path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-3 2z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
    "money": '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h.01M18 12h.01"/>',
    "bank": '<path d="M3 21h18M5 21V10M19 21V10M9 21v-8M15 21v-8M2 10l10-6 10 6z"/>',
    "card": '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/>',
    "id": '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="11" r="2"/>'
          '<path d="M6 16c.7-1.5 1.8-2 3-2s2.3.5 3 2M14 9h4M14 13h4"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "warning": '<path d="M10.3 4.3 2.6 18a2 2 0 0 0 1.7 3h15.4a2 2 0 0 0 1.7-3L13.7 4.3a2 2 0 0 0-3.4 0"/>'
               '<path d="M12 9v4M12 17h.01"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
    "check": '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
    "cross": '<circle cx="12" cy="12" r="9"/><path d="m15 9-6 6M9 9l6 6"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/>',
    "question": '<circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 1 1 3.5 2.3c-.6.3-1 .9-1 1.6V14M12 17h.01"/>',
    "person": '<circle cx="12" cy="8" r="4"/><path d="M4 21c1-4 4-6 8-6s7 2 8 6"/>',
    "family": '<circle cx="9" cy="8" r="3.5"/><path d="M2 20c.8-3.5 3.5-5 7-5s6.2 1.5 7 5"/>'
              '<path d="M16 4.5a3.5 3.5 0 0 1 0 7M18 15c2 .7 3.4 2.3 4 5"/>',
    "home": '<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10M10 20v-6h4v6"/>',
    "hospital": '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M12 8v8M8 12h8"/>',
    "medicine": '<path d="M10.5 20.5 3.5 13.5a5 5 0 0 1 7-7l7 7a5 5 0 0 1-7 7"/><path d="m8.5 8.5 7 7"/>',
    "heart": '<path d="M12 20s-7-4.5-9-9a4.5 4.5 0 0 1 9-3 4.5 4.5 0 0 1 9 3c-2 4.5-9 9-9 9"/>',
    "school": '<path d="m2 9 10-5 10 5-10 5z"/><path d="M6 11v5c2 2 10 2 12 0v-5M22 9v6"/>',
    "book": '<path d="M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4z"/><path d="M20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z"/>',
    "chat": '<path d="M4 5h16v11H8l-4 4z"/>',
    "mail": '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
    "location": '<path d="M12 21s7-6.2 7-12a7 7 0 0 0-14 0c0 5.8 7 12 7 12"/><circle cx="12" cy="9" r="2.5"/>',
    "food": '<path d="M7 3v18M4 3v5a3 3 0 0 0 6 0V3M17 21V3c-2 1.5-3 4-3 7v4h3"/>',
    "cart": '<circle cx="9" cy="20" r="1.5"/><circle cx="17" cy="20" r="1.5"/><path d="M2 3h3l2.5 12h11L21 7H6"/>',
    "link": '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1"/>'
            '<path d="M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
    "key": '<circle cx="8" cy="15" r="4"/><path d="m11 12 9-9M16 7l3 3M14 9l2 2"/>',
    "mobile": '<rect x="6" y="2" width="12" height="20" rx="2"/><path d="M11 18h2"/>',
    "checklist": '<rect x="5" y="4" width="14" height="17" rx="2"/><path d="M9 4V3h6v1M9 10l1.5 1.5L13 9M9 15h6"/>',
    # ---- UI-only icons (the web app)
    "play": '<path d="M7 4v16l13-8z"/>',
    "pause": '<path d="M8 5v14M16 5v14"/>',
    "replay": '<path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/>',
    "eye": '<path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12"/><circle cx="12" cy="12" r="3"/>',
    "volume": '<path d="M11 5 6 9H3v6h3l5 4z"/><path d="M15.5 8.5a5 5 0 0 1 0 7M18.5 5.5a9 9 0 0 1 0 13"/>',
    "arrow-right": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 0 1 0 18M12 3a14 14 0 0 0 0 18"/>',
    "send": '<path d="m22 2-11 11M22 2l-7 20-4-9-9-4z"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="m14 6 4 4"/>',
    "shield-alert": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="M12 8v4M12 16h.01"/>',
    "tick": '<path d="M20 6 9 17l-5-5"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "mic": '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>',
    "map": '<path d="m3 6 6-3 6 3 6-3v15l-6 3-6-3-6 3z"/><path d="M9 3v15M15 6v15"/>',
    "printer": '<path d="M6 9V3h12v6"/><rect x="3" y="9" width="18" height="8" rx="2"/><path d="M7 14h10v7H7z"/>',
    "phone-call": '<path d="M5 4h3l2 5-2.5 1.5a11 11 0 0 0 6 6L15 14l5 2v3a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2"/>'
                  '<path d="M15 3a6 6 0 0 1 6 6M15 7a2 2 0 0 1 2 2"/>',
}

FALLBACK = "info"


def icon_svg(name: str | None, size: int = 24, stroke: float = 1.75) -> Markup:
    """An inline <svg> for ``name`` (unknown names fall back to "info"). Safe to put straight into a template."""
    body = ICONS.get(name or "", ICONS[FALLBACK])
    return Markup(f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                  f'stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
                  f'{body}</svg>')
