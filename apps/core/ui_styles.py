"""Interface styles (Profile › Style). Independent of the colour theme: these change
shape, type, spacing and how cards and menus are drawn. Key, name, description, Google font family query."""

STYLES = [
    ("classic", "Classic", "The standard Weststar One look.", ""),
    ("soft", "Soft", "Rounded corners, pill buttons, floating shadows and a friendly font.", "Nunito:wght@400;500;600;700;800"),
    ("compact", "Compact", "Small type and tight rows, so more fits on screen.", "IBM+Plex+Sans:wght@400;500;600;700"),
    ("sharp", "Sharp", "Square corners, bold lines and uppercase headings.", "Archivo:wght@400;500;600;700;800"),
    ("glass", "Glass", "See-through frosted cards over a colour wash, floating menu.", "Plus+Jakarta+Sans:wght@400;500;600;700"),
    ("terminal", "Terminal", "Monospaced type, square corners, dashed lines. Feels like a console.", "JetBrains+Mono:wght@400;500;600;700"),
    ("editorial", "Editorial", "Serif headings, hairline rules and open space, like a magazine.", "Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Source+Sans+3:wght@400;500;600;700"),
    ("bento", "Bento", "Menu and top bar float as separate tiles with big gaps between.", "Manrope:wght@400;500;600;700;800"),
]
BY_KEY = {s[0]: s for s in STYLES}


def font_query(key: str) -> str:
    return BY_KEY.get(key, STYLES[0])[3]
