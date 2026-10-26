"""Themes each person can pick in Profile. A theme is a light or dark base plus its own colours
(static/core/themes.css). `swatch` = (background, menu, accent) for the little previews."""

THEMES = [
    ("paper", "Weststar One", "light", ("#EEF0F5", "#F8F9FC", "#0070D2"), "The original Weststar One look — the default"),
    ("indigo", "Indigo", "light", ("#F5F7FA", "#FFFFFF", "#4F46E5"), "Clean and bright"),
    ("weststar", "Weststar Blue", "light", ("#F4F7FB", "#0B2A4A", "#0A4B85"), "Company blue with a navy menu"),
    ("slate", "Slate", "light", ("#F6F7F9", "#1E293B", "#334155"), "Quiet greys, dark menu"),
    ("forest", "Forest", "light", ("#F4F8F5", "#FFFFFF", "#15803D"), "Calm greens"),
    ("teal", "Teal", "light", ("#F2F8F8", "#FFFFFF", "#0F766E"), "Fresh teal"),
    ("violet", "Violet", "light", ("#F7F5FC", "#FFFFFF", "#7C3AED"), "Purple accents"),
    ("rose", "Rose", "light", ("#FCF6F7", "#FFFFFF", "#E11D48"), "Warm pink-red accents"),
    ("sunset", "Sunset", "light", ("#FBF7F3", "#FFFFFF", "#EA580C"), "Warm orange, like the old app"),
    ("sand", "Sand", "light", ("#F7F3EC", "#EFE8DC", "#9A5B2E"), "Soft beige paper"),
    ("contrast", "High contrast", "light", ("#FFFFFF", "#000000", "#0047AB"), "Strong contrast, easiest to read"),
    ("graphite", "Graphite", "dark", ("#18181B", "#111113", "#F97316"), "Dark grey with orange"),
    ("midnight", "Midnight", "dark", ("#0B1220", "#070C17", "#60A5FA"), "Deep navy, blue accents"),
    ("nord", "Nord", "dark", ("#2E3440", "#272C36", "#88C0D0"), "Cool arctic blue-grey"),
    ("neon", "Neon", "dark", ("#0A0A0F", "#050508", "#22D3EE"), "Black with bright cyan, like the old neon menu"),
]
BY_KEY = {t[0]: t for t in THEMES}


def mode(key: str) -> str:
    return BY_KEY.get(key, THEMES[0])[2]
