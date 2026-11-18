"""Render a shareable diagram of the current Mage Agents Lab architecture."""

from math import atan2, cos, sin, pi
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "assets" / "linkedin" / "mage-agents-architecture.png"
SCALE = 2
WIDTH, HEIGHT = 1080, 1350

BG_TOP = (9, 17, 32)
BG_BOTTOM = (15, 30, 51)
CARD = "#17273F"
BORDER = "#36506C"
WHITE = "#F7FAFF"
MUTED = "#B6C6D8"
FAINT = "#8297AD"
TEAL = "#3DD6CC"
PURPLE = "#A792FF"
BLUE = "#76B8FF"
AMBER = "#FFC778"
GREEN = "#78E3B1"


def xy(point):
    return tuple(int(value * SCALE) for value in point)


def rect(box):
    return tuple(int(value * SCALE) for value in box)


def font(size, bold=False):
    candidates = [
        Path("C:/Windows/Fonts") / ("segoeuib.ttf" if bold else "segoeui.ttf"),
        Path("/usr/share/fonts/truetype/dejavu") / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
    ]
    selected = next((path for path in candidates if path.exists()), None)
    return ImageFont.truetype(str(selected), int(size * SCALE)) if selected else ImageFont.load_default(size=int(size * SCALE))


image = Image.new("RGB", (WIDTH * SCALE, HEIGHT * SCALE))
pixels = image.load()
for y in range(HEIGHT * SCALE):
    blend = y / (HEIGHT * SCALE - 1)
    color = tuple(round(a * (1 - blend) + b * blend) for a, b in zip(BG_TOP, BG_BOTTOM))
    for x in range(WIDTH * SCALE):
        pixels[x, y] = color

draw = ImageDraw.Draw(image)
for x in range(0, WIDTH + 1, 54):
    draw.line([xy((x, 0)), xy((x, HEIGHT))], fill="#14243A", width=SCALE)
for y in range(0, HEIGHT + 1, 54):
    draw.line([xy((0, y)), xy((WIDTH, y))], fill="#14243A", width=SCALE)


def label(value, x, y, size, color=WHITE, bold=False):
    draw.text(xy((x, y)), value, font=font(size, bold), fill=color, stroke_width=0)


def pill(x, y, w, h, text, stroke, fill="#172A40", size=23):
    draw.rounded_rectangle(rect((x, y, x + w, y + h)), radius=20 * SCALE, fill=fill, outline=stroke, width=2 * SCALE)
    bounds = draw.textbbox((0, 0), text, font=font(size, True))
    text_w = (bounds[2] - bounds[0]) / SCALE
    text_h = (bounds[3] - bounds[1]) / SCALE
    label(text, x + (w - text_w) / 2, y + (h - text_h) / 2 - 5, size, stroke, True)


def icon(kind, cx, cy, color):
    d = 27
    if kind == "mail":
        draw.rounded_rectangle(rect((cx - d, cy - 18, cx + d, cy + 18)), radius=5 * SCALE, outline=color, width=4 * SCALE)
        draw.line([xy((cx - d + 3, cy - 15)), xy((cx, cy + 3)), xy((cx + d - 3, cy - 15))], fill=color, width=4 * SCALE, joint="curve")
    elif kind == "news":
        draw.rounded_rectangle(rect((cx - 25, cy - 24, cx + 25, cy + 24)), radius=5 * SCALE, outline=color, width=4 * SCALE)
        for offset in (-11, 0, 11):
            draw.line([xy((cx - 15, cy + offset)), xy((cx + 15, cy + offset))], fill=color, width=3 * SCALE)
    elif kind == "worker":
        draw.ellipse(rect((cx - 25, cy - 25, cx + 25, cy + 25)), outline=color, width=4 * SCALE)
        draw.ellipse(rect((cx - 9, cy - 9, cx + 9, cy + 9)), fill=color)
        for angle in (0, pi / 2, pi, 3 * pi / 2):
            draw.line([xy((cx + 26 * cos(angle), cy + 26 * sin(angle))), xy((cx + 34 * cos(angle), cy + 34 * sin(angle)))], fill=color, width=4 * SCALE)
    elif kind == "spark":
        pts = [(cx, cy - 29), (cx + 8, cy - 8), (cx + 28, cy), (cx + 8, cy + 8), (cx, cy + 29), (cx - 8, cy + 8), (cx - 28, cy), (cx - 8, cy - 8)]
        draw.polygon([xy(p) for p in pts], fill=color)
    elif kind == "db":
        draw.ellipse(rect((cx - 27, cy - 23, cx + 27, cy - 7)), outline=color, width=4 * SCALE)
        draw.arc(rect((cx - 27, cy - 3, cx + 27, cy + 13)), 0, 180, fill=color, width=4 * SCALE)
        draw.arc(rect((cx - 27, cy + 12, cx + 27, cy + 28)), 0, 180, fill=color, width=4 * SCALE)
        draw.line([xy((cx - 27, cy - 15)), xy((cx - 27, cy + 20))], fill=color, width=4 * SCALE)
        draw.line([xy((cx + 27, cy - 15)), xy((cx + 27, cy + 20))], fill=color, width=4 * SCALE)
    elif kind == "screen":
        draw.rounded_rectangle(rect((cx - 29, cy - 23, cx + 29, cy + 17)), radius=5 * SCALE, outline=color, width=4 * SCALE)
        draw.line([xy((cx, cy + 17)), xy((cx, cy + 27))], fill=color, width=4 * SCALE)
        draw.line([xy((cx - 17, cy + 27)), xy((cx + 17, cy + 27))], fill=color, width=4 * SCALE)


def card(x, y, w, h, accent, kind, title, lines, title_size=37):
    draw.rounded_rectangle(rect((x + 7, y + 11, x + w + 7, y + h + 11)), radius=26 * SCALE, fill="#07111F")
    draw.rounded_rectangle(rect((x, y, x + w, y + h)), radius=26 * SCALE, fill=CARD, outline=BORDER, width=2 * SCALE)
    draw.rounded_rectangle(rect((x + 28, y + 27, x + 102, y + 101)), radius=22 * SCALE, fill="#22364F")
    icon(kind, x + 65, y + 64, accent)
    label(title, x + 126, y + 31, title_size, WHITE, True)
    small = h <= 180
    for index, line in enumerate(lines):
        label(line, x + 33, y + (100 if small else 115) + index * (32 if small else 38), 24 if small else 26, MUTED)


def arrow(start, end, color, bend=0):
    x1, y1 = start
    x2, y2 = end
    control1 = (x1 + (x2 - x1) * 0.35 + bend, y1 + (y2 - y1) * 0.12)
    control2 = (x2 - (x2 - x1) * 0.35 + bend, y2 - (y2 - y1) * 0.12)
    points = []
    for n in range(33):
        t = n / 32
        u = 1 - t
        x = u**3 * x1 + 3 * u**2 * t * control1[0] + 3 * u * t**2 * control2[0] + t**3 * x2
        y = u**3 * y1 + 3 * u**2 * t * control1[1] + 3 * u * t**2 * control2[1] + t**3 * y2
        points.append((x, y))
    draw.line([xy(p) for p in points], fill="#0B1728", width=12 * SCALE, joint="curve")
    draw.line([xy(p) for p in points], fill=color, width=5 * SCALE, joint="curve")
    theta = atan2(points[-1][1] - points[-3][1], points[-1][0] - points[-3][0])
    head = [(x2, y2), (x2 - 17 * cos(theta - 0.55), y2 - 17 * sin(theta - 0.55)), (x2 - 17 * cos(theta + 0.55), y2 - 17 * sin(theta + 0.55))]
    draw.polygon([xy(p) for p in head], fill=color)


# Header
draw.rounded_rectangle(rect((80, 80, 148, 148)), radius=18 * SCALE, fill=PURPLE)
label("M", 96, 79, 54, "#0B1323", True)
label("Mage Agents Lab", 171, 73, 60, WHITE, True)
label("A local-first foundation for personal AI agents", 82, 169, 29, MUTED)
pill(80, 231, 230, 51, "CURRENT BUILD", TEAL, size=22)
label("Runs locally with Docker Compose", 602, 239, 24, FAINT)

# Connections behind the cards
arrow((300, 490), (260, 605), TEAL, bend=-35)
arrow((780, 490), (500, 605), TEAL, bend=12)
arrow((680, 712), (740, 712), PURPLE)
arrow((350, 820), (290, 945), AMBER, bend=-30)
arrow((500, 1035), (580, 1035), GREEN)

# Architecture cards
card(80, 310, 440, 180, TEAL, "mail", "2 Gmail accounts", ["Inbox review &", "approved sending"], 35)
card(560, 310, 440, 180, TEAL, "news", "Developer news", ["RSS, releases &", "Hacker News"], 37)
card(80, 605, 600, 215, PURPLE, "worker", "Background worker", ["Email triage  •  News collection", "Daily briefing  •  Scheduled jobs"], 40)
card(740, 625, 260, 170, BLUE, "spark", "OpenAI", ["Ranking &", "summaries"], 34)
card(80, 945, 420, 180, AMBER, "db", "SQLite", ["Summaries, drafts", "and job state"], 40)
card(580, 945, 420, 180, GREEN, "screen", "FastAPI", ["Local dashboard", "and draft approval"], 40)

# Human approval callout and project URL
draw.rounded_rectangle(rect((80, 1180, 1000, 1275)), radius=24 * SCALE, fill="#16342F", outline="#347A67", width=2 * SCALE)
draw.ellipse(rect((111, 1201, 165, 1255)), fill="#245C4D")
draw.line([xy((125, 1226)), xy((136, 1238)), xy((153, 1217))], fill=GREEN, width=5 * SCALE, joint="curve")
label("A person approves every email before it is sent", 184, 1201, 29, WHITE, True)
label("github.com/supervipe/Mage-Agents-Lab", 81, 1300, 23, FAINT)

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS).save(OUTPUT, "PNG", optimize=True)
print(OUTPUT)
