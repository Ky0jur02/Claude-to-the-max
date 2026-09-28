import pygame
import sys
import math
import serial

from database import (
    create_tables,
    add_student,
    get_students,
    delete_student,
    save_attempt,  # <-- NEW: Imported your save_attempt function
    verify_teacher,
    get_student_dashboard_summary,
    get_performance_status
)

from games.number_block import (
    CountingGame,
    AdditionGame,
    Addition100Game,
    Subtraction100Game
)

from games.money import MoneyGame


# =========================================================
# INITIALIZATION
# =========================================================

pygame.init()

SCREEN_WIDTH = 1024
SCREEN_HEIGHT = 600

screen = pygame.display.set_mode(
    (SCREEN_WIDTH, SCREEN_HEIGHT)
)

pygame.display.set_caption(
    "Capstone 2 - Mathematics Learning System"
)

clock = pygame.time.Clock()

# Updated once per frame in the main loop; used by the world
# background/particle drawing helpers for lightweight animation
# (drifting clouds, rising bubbles, falling snow, etc).
animation_time = 0.0

# World-change fade transition state
WORLD_TRANSITION_SECONDS = 0.45
last_world = "HOME"
world_transition_start = -10.0
fade_surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))


# =========================================================
# COLORS
# =========================================================

WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
BLUE = (50, 100, 200)
LIGHT_BLUE = (220, 235, 255)
GRAY = (180, 180, 180)
GREEN = (70, 160, 90)
RED = (200, 70, 70)
YELLOW = (240, 210, 70)


# =========================================================
# FONTS (Using Arial to support the ₱ symbol)
# =========================================================

title_font = pygame.font.SysFont("arial", 56, bold=True)
large_font = pygame.font.SysFont("arial", 64, bold=True)
button_font = pygame.font.SysFont("arial", 38, bold=True)
small_font = pygame.font.SysFont("arial", 28, bold=True)
input_font = pygame.font.SysFont("arial", 42, bold=True)

# ---------------------------------------------------------
# CHILD-FRIENDLY DISPLAY FONTS (adventure-world chrome only)
#
# These are used ONLY for the new decorative UI: world
# titles, card/button labels, instructions, hints and the
# teacher dashboard. The original Arial fonts above are kept
# completely untouched and are still what renders every
# question, answer and the peso (₱) symbol, so nothing about
# readability or the currency glyph can regress.
#
# SysFont accepts a comma-separated fallback list and always
# resolves to *some* usable system font, so if none of the
# playful names exist on the machine this silently falls back
# to the platform default bold sans-serif - no crash, no
# missing font file to ship.
# ---------------------------------------------------------
PLAYFUL_FONT_STACK = "comicsansms,trebuchetms,verdana,arial"

font_world_title = pygame.font.SysFont(PLAYFUL_FONT_STACK, 52, bold=True)
font_topic_title = pygame.font.SysFont(PLAYFUL_FONT_STACK, 34, bold=True)
font_ui_button = pygame.font.SysFont(PLAYFUL_FONT_STACK, 30, bold=True)
font_instruction = pygame.font.SysFont(PLAYFUL_FONT_STACK, 20, bold=True)
font_hint = pygame.font.SysFont(PLAYFUL_FONT_STACK, 16, bold=True)
font_score_big = pygame.font.SysFont(PLAYFUL_FONT_STACK, 46, bold=True)
font_dashboard = pygame.font.SysFont(PLAYFUL_FONT_STACK, 22, bold=True)
font_dashboard_small = pygame.font.SysFont(PLAYFUL_FONT_STACK, 16, bold=True)


# =========================================================
# IMAGES
# =========================================================

COIN_SIZE = (35, 35)

try:
    coin_images = {
        1: pygame.transform.scale(pygame.image.load("1_peso.png"), COIN_SIZE),
        5: pygame.transform.scale(pygame.image.load("5_peso.png"), COIN_SIZE),
        10: pygame.transform.scale(pygame.image.load("10_peso.png"), COIN_SIZE),
        20: pygame.transform.scale(pygame.image.load("20_peso.png"), COIN_SIZE)
    }
except FileNotFoundError:
    print("WARNING: Coin images not found! Please add 1_peso.png, 5_peso.png, 10_peso.png, 20_peso.png")
    coin_images = {}


# =========================================================
# DATABASE
# =========================================================

create_tables()


# =========================================================
# SCREEN STATES
# =========================================================

HOME = "home"

STUDENT_SELECTION = "student_selection"
REGISTER_STUDENT = "register_student"
DELETE_STUDENT = "delete_student"
VIRTUAL_KEYBOARD = "virtual_keyboard"
CURRENT_PLAYER = "current_player"

GAME_SELECTION = "game_selection"
NUMBER_BLOCK_TOPICS = "number_block_topics"
MONEY_TOPICS = "money_topics"

MONEY_TOTAL_GAME = "money_total_game"
MONEY_CHANGE_GAME = "money_change_game"
MONEY_SAVINGS_GAME = "money_savings_game"
MONEY_MAKE_GAME = "money_make_game"
MONEY_RESULT = "money_result"

CLOCK_GAME = "clock_game"
PIZZA_FRACTION_GAME = "pizza_fraction_game"
MIXED_QUICKSTART = "mixed_quickstart"

TEACHER_LOGIN = "teacher_login"
TEACHER_DASHBOARD = "teacher_dashboard"
TEACHER_STUDENT_DETAIL = "teacher_student_detail"

COUNTING_GAME = "counting_game"
COUNTING_RESULT = "counting_result"

ADDITION_GAME = "addition_game"
ADDITION_RESULT = "addition_result"

ADDITION100_GAME = "addition100_game"
ADDITION100_RESULT = "addition100_result"

SUBTRACTION100_GAME = "subtraction100_game"
SUBTRACTION100_RESULT = "subtraction100_result"

current_screen = HOME

# Home screen now offers two entry points (student LOGIN and the
# teacher-only dashboard); this tracks which one is highlighted.
home_menu_options = ["LOGIN", "TEACHER DASHBOARD"]
selected_home_option = 0

# ---------------------------------------------------------
# TEACHER LOGIN / DASHBOARD STATE
# ---------------------------------------------------------

TEACHER_USERNAME_DEFAULT = "teacher"

teacher_username_input = TEACHER_USERNAME_DEFAULT
teacher_password_input = ""
teacher_login_field = 1          # 0 = username field, 1 = password field
teacher_login_error = ""
teacher_logged_in = False

dashboard_students = []          # [(student_id, name), ...]
dashboard_selected_student = 0
dashboard_scroll_offset = 0

dashboard_detail_student_id = None
dashboard_detail_student_name = ""
dashboard_detail_rows = []       # rows currently listed on the detail screen
dashboard_detail_selected = 0
dashboard_detail_scroll = 0
dashboard_detail_summary = {}    # {game_type: [session dicts oldest->newest]}
dashboard_detail_view = "SUMMARY"    # "SUMMARY" (one card per activity) or "HISTORY"
dashboard_detail_activity = None     # game_type shown in HISTORY view
dashboard_detail_topics = ["ALL"]
dashboard_detail_filter = 0          # index into dashboard_detail_topics

# Clickable regions are rebuilt every frame a dashboard screen is
# drawn, then consulted on MOUSEBUTTONDOWN, so every on-screen
# dashboard control also works with the mouse as required.
dashboard_click_targets = []


# =========================================================
# STUDENTS
# =========================================================

students = []

selected_student_option = 0
student_scroll_offset = 0

current_player = None
current_player_id = None # <-- Tracks the DB ID

student_name_input = ""


# =========================================================
# REGISTER STUDENT FOCUS
# =========================================================

# 0 = name input
# 1 = virtual keyboard button

register_focus = 0


# =========================================================
# DELETE STUDENT
# =========================================================

delete_student_index = 0
delete_scroll_offset = 0


# =========================================================
# VIRTUAL KEYBOARD
# =========================================================

keyboard_rows = [
    ["A", "B", "C", "D", "E", "F", "G"],
    ["H", "I", "J", "K", "L", "M", "N"],
    ["O", "P", "Q", "R", "S", "T", "U"],
    ["V", "W", "X", "Y", "Z", "SPACE", "BACKSPACE"],
    ["CLEAR", "DONE"]
]

keyboard_row = 0
keyboard_col = 0


# =========================================================
# GAME MODULES
# =========================================================

game_modules = [
    "NUMBER BLOCK",
    "MONEY",
    "CLOCK",
    "PIZZA FRACTION",
    "MIXED QUICKSTART"
]

selected_game = 0
selected_game_name = "" # Helper to track game name for DB


# =========================================================
# NUMBER BLOCK TOPICS
# =========================================================

number_block_topics = [
    "COUNTING - FILL IN THE BLANKS",
    "ADDITION UP TO 20",
    "ADDITION UP TO 100",
    "SUBTRACTION - BOTH NUMBERS < 100"
]

selected_number_topic = 0


# =========================================================
# MONEY TOPICS
# =========================================================

money_topics = [
    "FINDING TOTAL SPENT",
    "FINDING CHANGE",
    "CALCULATING SAVINGS",
    "MAKE THE EXACT AMOUNT"
]

selected_money_topic = 0


# =========================================================
# GAME VARIABLES
# =========================================================

counting_game = None
counting_result_message = ""

addition_game = None
addition100_game = None
subtraction100_game = None

money_game = None


# =========================================================
# TEXT FUNCTIONS
# =========================================================

def draw_text(text, font, color, x, y, center=True):
    surface = font.render(str(text), True, color)
    if center:
        rect = surface.get_rect(center=(x, y))
    else:
        rect = surface.get_rect(topleft=(x, y))
    screen.blit(surface, rect)


def draw_multiline_text(text, font, color, center_x, start_y, max_width):
    words = text.split(' ')
    lines = []
    current_line = []
    
    for word in words:
        test_line = ' '.join(current_line + [word])
        width, _ = font.size(test_line)
        if width <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(' '.join(current_line))
            current_line = [word]
            
    if current_line:
        lines.append(' '.join(current_line))
        
    y = start_y
    line_spacing = font.get_linesize()
    
    for line in lines:
        draw_text(line, font, color, center_x, y, center=True)
        y += line_spacing


# =========================================================
# WORLD THEMES
#
# Centralized per-topic look. Adding/adjusting a world only
# means editing its entry here - draw_world_background,
# draw_world_particles, draw_game_button, etc. all read from
# this table instead of hard-coding colors per screen.
# =========================================================

WORLD_THEMES = {
    "HOME": {
        "title": "OVERWORLD",
        "sky_top": (140, 205, 255),
        "sky_bottom": (200, 232, 255),
        "ground": (90, 170, 95),
        "ground_dark": (70, 145, 78),
        "accent": (40, 110, 60),
        "button": (120, 200, 120),
        "button_selected": (255, 221, 89),
        "border": (40, 110, 60),
        "text_on_button": BLACK,
        "particle": "clouds"
    },
    "NUMBER BLOCK": {
        "title": "BLOCK FOREST",
        "sky_top": (150, 210, 255),
        "sky_bottom": (205, 235, 255),
        "ground": (100, 175, 100),
        "ground_dark": (78, 150, 82),
        "accent": (34, 120, 60),
        "button": (255, 196, 90),
        "button_selected": (255, 221, 89),
        "border": (34, 120, 60),
        "text_on_button": BLACK,
        "particle": "clouds"
    },
    "MONEY": {
        "title": "TREASURE REEF",
        "sky_top": (10, 70, 130),
        "sky_bottom": (25, 120, 175),
        "ground": (30, 90, 140),
        "ground_dark": (20, 70, 115),
        "accent": (255, 205, 70),
        "button": (60, 150, 200),
        "button_selected": (255, 205, 70),
        "border": (255, 205, 70),
        "text_on_button": WHITE,
        "particle": "bubbles"
    },
    "CLOCK": {
        "title": "FROZEN KINGDOM",
        "sky_top": (190, 225, 245),
        "sky_bottom": (225, 240, 250),
        "ground": (210, 232, 245),
        "ground_dark": (175, 210, 232),
        "accent": (40, 110, 160),
        "button": (150, 210, 235),
        "button_selected": (255, 255, 255),
        "border": (40, 110, 160),
        "text_on_button": BLACK,
        "particle": "snow"
    },
    "PIZZA FRACTION": {
        "title": "MAGMA CAVERNS",
        "sky_top": (40, 15, 15),
        "sky_bottom": (70, 25, 20),
        "ground": (55, 30, 25),
        "ground_dark": (35, 18, 15),
        "accent": (255, 140, 40),
        "button": (200, 80, 40),
        "button_selected": (255, 150, 50),
        "border": (255, 140, 40),
        "text_on_button": WHITE,
        "particle": "embers"
    },
    "MIXED QUICKSTART": {
        "title": "GALAXY GATE",
        "sky_top": (10, 10, 35),
        "sky_bottom": (30, 20, 60),
        "ground": (25, 20, 50),
        "ground_dark": (15, 12, 35),
        "accent": (170, 140, 255),
        "button": (90, 70, 160),
        "button_selected": (170, 140, 255),
        "border": (170, 140, 255),
        "text_on_button": WHITE,
        "particle": "stars"
    },
    "TEACHER": {
        "title": "TEACHER DASHBOARD",
        "sky_top": (235, 238, 245),
        "sky_bottom": (245, 247, 250),
        "ground": (225, 229, 238),
        "ground_dark": (210, 215, 226),
        "accent": (55, 70, 110),
        "button": (225, 230, 240),
        "button_selected": (60, 110, 200),
        "border": (55, 70, 110),
        "text_on_button": BLACK,
        "particle": "none"
    },
}

STATUS_COLORS = {
    "MASTERED": (60, 160, 90),
    "DEVELOPING": (235, 165, 45),
    "NEEDS SUPPORT": (210, 70, 70)
}


def get_world_for_screen(screen_name):
    if screen_name in (
        NUMBER_BLOCK_TOPICS, COUNTING_GAME, COUNTING_RESULT,
        ADDITION_GAME, ADDITION_RESULT, ADDITION100_GAME, ADDITION100_RESULT,
        SUBTRACTION100_GAME, SUBTRACTION100_RESULT
    ):
        return "NUMBER BLOCK"
    if screen_name in (
        MONEY_TOPICS, MONEY_TOTAL_GAME, MONEY_CHANGE_GAME,
        MONEY_SAVINGS_GAME, MONEY_MAKE_GAME, MONEY_RESULT
    ):
        return "MONEY"
    if screen_name == CLOCK_GAME:
        return "CLOCK"
    if screen_name == PIZZA_FRACTION_GAME:
        return "PIZZA FRACTION"
    if screen_name == MIXED_QUICKSTART:
        return "MIXED QUICKSTART"
    if screen_name in (TEACHER_LOGIN, TEACHER_DASHBOARD, TEACHER_STUDENT_DETAIL):
        return "TEACHER"
    return "HOME"


# =========================================================
# WORLD BACKGROUND / PARTICLES (lightweight - no images,
# only a handful of primitive shapes so this stays smooth
# on a low-spec laptop)
# =========================================================

def draw_world_background(theme_key):
    theme = WORLD_THEMES[theme_key]

    # Simple 2-band "sky" gradient approximated with a few
    # horizontal strips (cheap - no per-pixel blending).
    band_count = 6
    band_height = (SCREEN_HEIGHT * 2 // 3) // band_count
    top = theme["sky_top"]
    bottom = theme["sky_bottom"]
    for i in range(band_count):
        ratio = i / max(1, band_count - 1)
        color = (
            int(top[0] + (bottom[0] - top[0]) * ratio),
            int(top[1] + (bottom[1] - top[1]) * ratio),
            int(top[2] + (bottom[2] - top[2]) * ratio),
        )
        pygame.draw.rect(screen, color, (0, i * band_height, SCREEN_WIDTH, band_height + 1))

    ground_y = SCREEN_HEIGHT * 2 // 3
    pygame.draw.rect(screen, theme["ground"], (0, ground_y, SCREEN_WIDTH, SCREEN_HEIGHT - ground_y))
    pygame.draw.rect(screen, theme["ground_dark"], (0, ground_y, SCREEN_WIDTH, 10))

    # A few theme-appropriate silhouettes along the horizon.
    particle_kind = theme["particle"]
    if particle_kind == "clouds":
        for i in range(3):
            hx = 90 + i * 260
            hy = ground_y - 10
            pygame.draw.polygon(screen, theme["ground_dark"], [
                (hx - 70, ground_y), (hx, hy - 55), (hx + 70, ground_y)
            ])
        for i in range(4):
            tx = 50 + i * 240
            pygame.draw.rect(screen, (110, 75, 50), (tx - 6, ground_y - 40, 12, 40))
            pygame.draw.circle(screen, (55, 140, 70), (tx, ground_y - 55), 30)
    elif particle_kind == "bubbles":
        for i in range(5):
            cx = 60 + i * 200
            pygame.draw.ellipse(screen, (20, 60, 50), (cx - 40, ground_y - 20, 90, 35))
        chest_x = SCREEN_WIDTH // 2
        pygame.draw.rect(screen, (120, 80, 40), (chest_x - 45, ground_y - 35, 90, 35), border_radius=6)
        pygame.draw.rect(screen, theme["accent"], (chest_x - 45, ground_y - 35, 90, 35), 3, border_radius=6)
    elif particle_kind == "snow":
        for i in range(4):
            hx = 70 + i * 250
            pygame.draw.polygon(screen, (225, 240, 250), [
                (hx - 60, ground_y), (hx, ground_y - 90), (hx + 60, ground_y)
            ])
            pygame.draw.polygon(screen, WHITE, [
                (hx - 20, ground_y - 55), (hx, ground_y - 90), (hx + 20, ground_y - 55)
            ])
    elif particle_kind == "embers":
        for i in range(4):
            hx = 80 + i * 250
            pygame.draw.polygon(screen, (30, 15, 12), [
                (hx - 65, ground_y), (hx, ground_y - 70), (hx + 65, ground_y)
            ])
        glow_rect = pygame.Rect(0, ground_y - 6, SCREEN_WIDTH, 14)
        pygame.draw.rect(screen, (255, 120, 30), glow_rect)
    elif particle_kind == "stars":
        pygame.draw.circle(screen, (180, 150, 255), (SCREEN_WIDTH // 2, ground_y - 40), 55)
        pygame.draw.circle(screen, theme["sky_bottom"], (SCREEN_WIDTH // 2, ground_y - 40), 40)


def draw_world_particles(theme_key, t):
    theme = WORLD_THEMES[theme_key]
    kind = theme["particle"]
    ground_y = SCREEN_HEIGHT * 2 // 3

    draw_world_decor(theme_key, t)

    if kind == "clouds":
        for i in range(3):
            x = (i * 300 + int(t * 12)) % (SCREEN_WIDTH + 160) - 80
            y = 60 + i * 45
            for dx, dy, r in [(-25, 6, 18), (0, -8, 24), (25, 6, 18), (45, 8, 14)]:
                pygame.draw.circle(screen, WHITE, (int(x + dx), int(y + dy)), r)
    elif kind == "bubbles":
        for i in range(8):
            seed = i * 37
            x = 40 + (seed * 53) % (SCREEN_WIDTH - 80)
            y = ground_y - ((int(t * 40) + seed * 17) % (ground_y - 20))
            r = 4 + (seed % 4)
            pygame.draw.circle(screen, (210, 240, 255), (x, y), r, 1)
    elif kind == "snow":
        for i in range(24):
            seed = i * 53
            x = (seed * 7) % SCREEN_WIDTH
            y = int((t * 60 + seed * 4) % (ground_y + 20))
            pygame.draw.circle(screen, WHITE, (x, y), 2)
    elif kind == "embers":
        for i in range(14):
            seed = i * 41
            x = (seed * 5) % SCREEN_WIDTH
            y = ground_y - int((t * 55 + seed * 6) % ground_y)
            pygame.draw.circle(screen, (255, 170, 60), (x, y), 2)
    elif kind == "stars":
        for i in range(30):
            seed = i * 91
            x = (seed * 7) % SCREEN_WIDTH
            y = (seed * 13) % ground_y
            twinkle = 1 if (int(t * 2) + i) % 3 else 2
            pygame.draw.circle(screen, WHITE, (x, y), twinkle)


def draw_world_decor(theme_key, t):
    """Small themed objects that bob/drift at the screen edges so the
    world feels alive without covering questions or buttons."""
    ground_y = SCREEN_HEIGHT * 2 // 3
    bob = lambda speed, amp, phase=0.0: int(math.sin(t * speed + phase) * amp)

    if theme_key == "NUMBER BLOCK":
        colors = [(255, 120, 90), (90, 170, 255), (255, 210, 80), (120, 210, 120)]
        spots = [(45, 250, "1"), (985, 300, "2"), (60, 420, "3"), (960, 140, "4")]
        for i, (x, y, digit) in enumerate(spots):
            r = pygame.Rect(0, 0, 38, 38)
            r.center = (x, y + bob(2.0, 8, i))
            pygame.draw.rect(screen, colors[i], r, border_radius=6)
            pygame.draw.rect(screen, (60, 60, 60), r, 3, border_radius=6)
            draw_text(digit, font_hint, BLACK, r.centerx, r.centery)
    elif theme_key == "MONEY":
        for i in range(2):  # fish swimming across
            x = int((t * (40 + i * 25) + i * 500) % (SCREEN_WIDTH + 120)) - 60
            y = 130 + i * 150 + bob(2.0, 6, i)
            pygame.draw.ellipse(screen, (255, 150, 60), (x - 18, y - 9, 36, 18))
            pygame.draw.polygon(screen, (255, 150, 60), [(x - 16, y), (x - 30, y - 9), (x - 30, y + 9)])
            pygame.draw.circle(screen, WHITE, (x + 8, y - 2), 3)
        for i, x in enumerate((70, 950)):  # bobbing coins
            pygame.draw.circle(screen, (255, 205, 70), (x, 430 + bob(2.5, 6, i)), 14)
            pygame.draw.circle(screen, (200, 150, 30), (x, 430 + bob(2.5, 6, i)), 14, 3)
        for x in (25, 995):  # seaweed
            for k in range(4):
                pygame.draw.line(screen, (40, 160, 90), (x, ground_y + 30), (x + bob(1.5, 6, k), ground_y - 40 + k * 8), 5)
    elif theme_key == "CLOCK":
        cx, cy = 90, 300 + bob(1.0, 5)
        pygame.draw.circle(screen, (235, 248, 255), (cx, cy), 42)
        pygame.draw.circle(screen, (60, 120, 170), (cx, cy), 42, 4)
        pygame.draw.line(screen, (60, 120, 170), (cx, cy), (cx, cy - 26), 3)
        pygame.draw.line(screen, (60, 120, 170), (cx, cy), (cx + 18, cy + 8), 3)
    elif theme_key == "PIZZA FRACTION":
        cx, cy = 935, 300 + bob(1.5, 8)
        pygame.draw.circle(screen, (240, 190, 90), (cx, cy), 44)
        pygame.draw.circle(screen, (200, 60, 40), (cx, cy), 36)
        pygame.draw.circle(screen, (255, 225, 120), (cx, cy), 32)
        for angle in range(0, 360, 90):
            a = math.radians(angle + 45)
            pygame.draw.line(screen, (170, 110, 40), (cx, cy), (cx + int(44 * math.cos(a)), cy + int(44 * math.sin(a))), 3)
        for x in (60, 260, 760):  # lava bubbles
            pygame.draw.circle(screen, (255, 130, 40), (x, ground_y + 20 + bob(2.0, 5, x)), 9)
    elif theme_key == "MIXED QUICKSTART":
        pygame.draw.circle(screen, (230, 140, 90), (90, 170 + bob(0.8, 6)), 34)
        pygame.draw.circle(screen, (190, 100, 60), (90, 170 + bob(0.8, 6)), 34, 3)
        rx = int((t * 30) % (SCREEN_WIDTH + 100)) - 50
        pygame.draw.polygon(screen, (230, 230, 240), [(rx, 470), (rx - 30, 462), (rx - 30, 478)])
        pygame.draw.polygon(screen, (255, 150, 60), [(rx - 30, 470), (rx - 46, 462), (rx - 46, 478)])
    elif theme_key == "HOME":
        for i, x in enumerate(range(40, SCREEN_WIDTH, 95)):
            fy = ground_y + 26 + (i % 3) * 22
            pygame.draw.line(screen, (50, 130, 60), (x, fy), (x, fy + 10), 2)
            pygame.draw.circle(screen, [(255, 110, 140), (255, 215, 80), (255, 255, 255)][i % 3], (x, fy), 5)


# =========================================================
# REUSABLE PIXEL-STYLE UI COMPONENTS
# =========================================================

def draw_game_button(rect, text, theme_key, selected, font=None, disabled=False):
    """Rounded, bordered game-style button. Returns the rect actually
    drawn (slightly inflated when selected) so callers can reuse it
    for mouse hit-testing."""
    theme = WORLD_THEMES[theme_key]
    font = font or font_ui_button

    draw_rect = rect.copy()
    if selected and not disabled:
        draw_rect.inflate_ip(8, 6)

    shadow_rect = draw_rect.move(0, 4)
    pygame.draw.rect(screen, (0, 0, 0, 60), shadow_rect, border_radius=14)

    fill = theme["button_selected"] if (selected and not disabled) else theme["button"]
    if disabled:
        fill = GRAY
    pygame.draw.rect(screen, fill, draw_rect, border_radius=14)

    border_color = theme["border"] if not disabled else GRAY
    pygame.draw.rect(screen, border_color, draw_rect, 4 if selected else 3, border_radius=14)

    text_color = theme["text_on_button"] if not disabled else (110, 110, 110)
    # Shrink long labels so text never spills out of the button.
    label_font = fit_font(text, [font, font_dashboard, font_dashboard_small], rect.width - 24)
    draw_text(text, label_font, text_color, draw_rect.centerx, draw_rect.centery)

    return draw_rect


def draw_topic_card(rect, text, theme_key, selected):
    return draw_game_button(rect, text, theme_key, selected, font=font_topic_title)


def fit_font(text, fonts, max_width):
    """Returns the first font (largest first) whose rendering of text
    fits max_width; falls back to the smallest one."""
    for f in fonts:
        if f.size(text)[0] <= max_width:
            return f
    return fonts[-1]


def draw_text_fit(text, fonts, color, x, y, max_width):
    draw_text(text, fit_font(text, fonts, max_width), color, x, y)


def draw_world_title(text, theme_key, y):
    theme = WORLD_THEMES[theme_key]
    font = fit_font(text, [font_world_title, font_topic_title, font_ui_button], SCREEN_WIDTH - 80)
    draw_text(text, font, (0, 0, 0), SCREEN_WIDTH // 2 + 3, y + 3)
    draw_text(text, font, theme["accent"], SCREEN_WIDTH // 2, y)


def draw_status_badge(status, x, y):
    color = STATUS_COLORS.get(status, GRAY)
    label = font_dashboard_small.render(status, True, WHITE)
    rect = label.get_rect(center=(x, y))
    rect.inflate_ip(20, 10)
    pygame.draw.rect(screen, color, rect, border_radius=8)
    screen.blit(label, label.get_rect(center=(x, y)))
    return rect


def draw_progress_bar(x, y, width, height, fraction, color):
    fraction = max(0.0, min(1.0, fraction))
    back_rect = pygame.Rect(x, y, width, height)
    pygame.draw.rect(screen, (215, 218, 224), back_rect, border_radius=height // 2)
    fill_rect = pygame.Rect(x, y, int(width * fraction), height)
    if fill_rect.width > 0:
        pygame.draw.rect(screen, color, fill_rect, border_radius=height // 2)
    pygame.draw.rect(screen, (170, 174, 182), back_rect, 2, border_radius=height // 2)


def draw_content_panel(rect, theme_key, fill=(255, 255, 255, 235)):
    """A soft, near-white panel dropped behind gameplay text so every
    original draw_text() call (question, answer, ₱ amounts, score...)
    stays exactly as readable as before no matter how colorful/dark
    the themed world behind it is. Purely a backdrop - it changes
    nothing about what text is drawn, only what's behind it."""
    theme = WORLD_THEMES[theme_key]
    panel_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel_surface, fill, panel_surface.get_rect(), border_radius=22)
    screen.blit(panel_surface, rect.topleft)
    pygame.draw.rect(screen, theme["border"], rect, 4, border_radius=22)


# =========================================================
# LOAD STUDENTS
# =========================================================

def load_students():
    global students
    students = get_students()


# =========================================================
# HOME SCREEN
# =========================================================

def draw_home():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("MATHEMATICS ADVENTURE", "HOME", 70)
    draw_text("CAPSTONE 2 - MATHEMATICS LEARNING SYSTEM", font_instruction, BLACK, SCREEN_WIDTH // 2, 118)

    start_y = 230
    for index, option in enumerate(home_menu_options):
        rect = pygame.Rect(0, 0, 340, 65)
        rect.centerx = SCREEN_WIDTH // 2
        rect.y = start_y + index * 90
        draw_game_button(rect, option, "HOME", index == selected_home_option)

    draw_text(
        "UP / DOWN = Select   |   ENTER = Confirm",
        font_instruction,
        BLACK,
        SCREEN_WIDTH // 2,
        start_y + len(home_menu_options) * 90 + 20
    )


# =========================================================
# STUDENT SELECTION
# =========================================================

def draw_student_selection():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("SELECT STUDENT", "HOME", 50)

    global student_scroll_offset
    
    total_options = len(students) + 2
    visible_items = 5

    if selected_student_option < student_scroll_offset:
        student_scroll_offset = selected_student_option
    elif selected_student_option >= student_scroll_offset + visible_items:
        student_scroll_offset = selected_student_option - visible_items + 1

    start_y = 130

    for i in range(student_scroll_offset, min(total_options, student_scroll_offset + visible_items)):

        display_index = i - student_scroll_offset
        current_y = start_y + display_index * 55 # Increased spacing slightly for better look
        
        # ---------------------------------------------
        # FIXED: Centered Student List Options
        # ---------------------------------------------
        rect = pygame.Rect(0, 0, 500, 45)
        rect.centerx = SCREEN_WIDTH // 2
        rect.y = current_y

        if i < len(students):
            student_name = students[i][1]
            draw_game_button(rect, student_name, "HOME", i == selected_student_option, font=font_dashboard)

        elif i == len(students):
            draw_game_button(rect, "REGISTER NEW STUDENT", "HOME", i == selected_student_option, font=font_dashboard)

        elif i == len(students) + 1:
            draw_game_button(rect, "DELETE STUDENT", "HOME", i == selected_student_option, font=font_dashboard)


    # Instructions moved to the center bottom of list
    instruction_y = start_y + (visible_items * 55) + 30
    draw_text(
        "UP / DOWN = Select   |   ENTER = Confirm",
        font_instruction,
        BLACK,
        SCREEN_WIDTH // 2,
        instruction_y
    )


# =========================================================
# REGISTER STUDENT
# =========================================================

def draw_register_student():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("REGISTER NEW STUDENT", "HOME", 55)

    draw_text(
        "Student Name:",
        font_topic_title,
        BLACK,
        SCREEN_WIDTH // 2,
        130
    )

    # ---------------------------------------------
    # FIXED: Grouped and Centered Input + Keyboard Button
    # ---------------------------------------------
    box_width = 400
    btn_width = 210
    gap = 20
    total_width = box_width + gap + btn_width
    
    start_x = (SCREEN_WIDTH - total_width) // 2

    input_box = pygame.Rect(start_x, 170, box_width, 65)
    keyboard_button = pygame.Rect(start_x + box_width + gap, 170, btn_width, 65)

    pygame.draw.rect(screen, WHITE, input_box, border_radius=10)

    if register_focus == 0:
        pygame.draw.rect(screen, WORLD_THEMES["HOME"]["border"], input_box, 4, border_radius=10)
    else:
        pygame.draw.rect(screen, GRAY, input_box, 3, border_radius=10)

    display_name = student_name_input
    if display_name == "":
        display_name = "ENTER NAME"

    draw_text(
        display_name,
        input_font,
        BLACK if student_name_input else GRAY,
        input_box.centerx,
        input_box.centery
    )

    draw_game_button(keyboard_button, "KEYBOARD", "HOME", register_focus == 1, font=font_ui_button)

    draw_text("LEFT / RIGHT = Select", font_instruction, BLACK, SCREEN_WIDTH // 2, 300)
    draw_text("ENTER = Open Keyboard", font_instruction, (40, 140, 60), SCREEN_WIDTH // 2, 340)
    draw_text("ESC = Cancel", font_instruction, RED, SCREEN_WIDTH // 2, 380)
    draw_text("Keyboard input is also available", font_hint, GRAY, SCREEN_WIDTH // 2, 425)


# =========================================================
# DELETE STUDENT SCREEN
# =========================================================

def draw_delete_student():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("DELETE STUDENT", "HOME", 60)

    if len(students) == 0:
        draw_text("NO STUDENTS TO DELETE", large_font, GRAY, SCREEN_WIDTH // 2, 220)
        draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 400)
        return

    global delete_scroll_offset
    visible_items = 5

    if delete_student_index < delete_scroll_offset:
        delete_scroll_offset = delete_student_index
    elif delete_student_index >= delete_scroll_offset + visible_items:
        delete_scroll_offset = delete_student_index - visible_items + 1

    start_y = 130

    for i in range(delete_scroll_offset, min(len(students), delete_scroll_offset + visible_items)):

        display_index = i - delete_scroll_offset
        student = students[i]
        name = student[1]

        # ---------------------------------------------
        # FIXED: Centered Delete List
        # ---------------------------------------------
        student_rect = pygame.Rect(0, 0, 440, 45)
        student_rect.centerx = SCREEN_WIDTH // 2
        student_rect.y = start_y + display_index * 55

        draw_game_button(student_rect, name, "HOME", i == delete_student_index, font=font_dashboard)

    draw_text("ENTER = Delete Selected Student", font_instruction, RED, SCREEN_WIDTH // 2, 430)
    draw_text("ESC = Cancel", font_instruction, BLACK, SCREEN_WIDTH // 2, 465)


# =========================================================
# VIRTUAL KEYBOARD
# =========================================================

def draw_virtual_keyboard():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("VIRTUAL KEYBOARD", "HOME", 40)

    name_box = pygame.Rect(0, 0, 600, 55)
    name_box.centerx = SCREEN_WIDTH // 2
    name_box.y = 100

    pygame.draw.rect(screen, WHITE, name_box, border_radius=10)
    pygame.draw.rect(screen, WORLD_THEMES["HOME"]["border"], name_box, 3, border_radius=10)

    display_name = student_name_input
    if display_name == "":
        display_name = "TYPE STUDENT NAME"

    draw_text(display_name, input_font, BLACK if student_name_input else GRAY, name_box.centerx, name_box.centery)

    key_width = 70
    key_height = 48
    gap = 6
    keyboard_start_y = 180

    for row_index, row in enumerate(keyboard_rows):
        row_width = (len(row) * key_width) + (len(row) - 1) * gap
        start_x = (SCREEN_WIDTH - row_width) // 2

        for col_index, key in enumerate(row):
            x = start_x + col_index * (key_width + gap)
            y = keyboard_start_y + row_index * (key_height + gap)

            rect = pygame.Rect(x, y, key_width, key_height)

            selected = (row_index == keyboard_row and col_index == keyboard_col)

            fill = WORLD_THEMES["HOME"]["button_selected"] if selected else WHITE
            pygame.draw.rect(screen, fill, rect, border_radius=8)
            pygame.draw.rect(screen, WORLD_THEMES["HOME"]["border"] if selected else GRAY, rect,
                              3 if selected else 2, border_radius=8)

            font = small_font
            if key in ["SPACE", "BACKSPACE", "CLEAR", "DONE"]:
                font = pygame.font.Font(None, 20)

            draw_text(key, font, BLACK, rect.centerx, rect.centery)

    instructions_y = keyboard_start_y + (len(keyboard_rows) * (key_height + gap)) + 30
    draw_text("UP / DOWN / LEFT / RIGHT = Move", font_instruction, WORLD_THEMES["HOME"]["accent"], SCREEN_WIDTH // 2, instructions_y)
    draw_text("ENTER = Select/Submit   |   ESC = Cancel", font_instruction, (40, 140, 60), SCREEN_WIDTH // 2, instructions_y + 40)


# =========================================================
# VIRTUAL KEYBOARD MOVEMENT
# =========================================================

def move_keyboard_up():
    global keyboard_row, keyboard_col
    keyboard_row -= 1
    if keyboard_row < 0:
        keyboard_row = len(keyboard_rows) - 1
    if keyboard_col >= len(keyboard_rows[keyboard_row]):
        keyboard_col = len(keyboard_rows[keyboard_row]) - 1

def move_keyboard_down():
    global keyboard_row, keyboard_col
    keyboard_row += 1
    if keyboard_row >= len(keyboard_rows):
        keyboard_row = 0
    if keyboard_col >= len(keyboard_rows[keyboard_row]):
        keyboard_col = len(keyboard_rows[keyboard_row]) - 1

def move_keyboard_left():
    global keyboard_col
    keyboard_col -= 1
    if keyboard_col < 0:
        keyboard_col = len(keyboard_rows[keyboard_row]) - 1

def move_keyboard_right():
    global keyboard_col
    keyboard_col += 1
    if keyboard_col >= len(keyboard_rows[keyboard_row]):
        keyboard_col = 0


# =========================================================
# SELECT VIRTUAL KEYBOARD KEY
# =========================================================

def select_keyboard_key():
    global student_name_input
    key = keyboard_rows[keyboard_row][keyboard_col]

    if key == "SPACE":
        if len(student_name_input) < 30:
            student_name_input += " "
        return False
    elif key == "BACKSPACE":
        student_name_input = student_name_input[:-1]
        return False
    elif key == "CLEAR":
        student_name_input = ""
        return False
    elif key == "DONE":
        return True
    else:
        if len(student_name_input) < 30:
            student_name_input += key
        return False


# =========================================================
# SAVE NEW STUDENT
# =========================================================

def save_new_student():
    global current_player, current_player_id, current_screen, selected_student_option
    name = student_name_input.strip().upper()

    if not name:
        print("Student name cannot be empty.")
        return

    add_student(name)
    load_students()

    for index, student in enumerate(students):
        if student[1] == name:
            selected_student_option = index
            current_player_id = student[0]
            break

    current_player = name
    print("STUDENT REGISTERED:", name)
    current_screen = CURRENT_PLAYER


# =========================================================
# CURRENT PLAYER
# =========================================================

def draw_current_player():
    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)
    draw_world_title("CURRENT PLAYER", "HOME", 90)
    draw_text(current_player, large_font, (40, 140, 60), SCREEN_WIDTH // 2, 220)
    draw_text("Press ENTER to continue", font_topic_title, BLACK, SCREEN_WIDTH // 2, 330)
    draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 420)


# =========================================================
# GAME SELECTION
# =========================================================

def draw_game_selection():

    draw_world_background("HOME")
    draw_world_particles("HOME", animation_time)

    draw_world_title("SELECT GAME", "HOME", 55)
    draw_text("PLAYER: " + current_player, font_instruction, BLACK, SCREEN_WIDTH // 2, 95)

    start_y = 150

    for index, game in enumerate(game_modules):
        # ---------------------------------------------
        # FIXED: Centered Game List
        # ---------------------------------------------
        game_rect = pygame.Rect(0, 0, 450, 50)
        game_rect.centerx = SCREEN_WIDTH // 2
        game_rect.y = start_y + index * 60

        draw_game_button(game_rect, game, "HOME", index == selected_game, font=font_topic_title)

    draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, start_y + (len(game_modules)*60) + 40)


# =========================================================
# NUMBER BLOCK TOPICS
# =========================================================

def draw_number_block_topics():

    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    draw_world_title("NUMBER BLOCK", "NUMBER BLOCK", 55)
    draw_text("SELECT TOPIC", font_instruction, WORLD_THEMES["NUMBER BLOCK"]["accent"], SCREEN_WIDTH // 2, 95)

    start_y = 150

    for index, topic in enumerate(number_block_topics):
        # ---------------------------------------------
        # FIXED: Centered Topic List
        # ---------------------------------------------
        topic_rect = pygame.Rect(0, 0, 600, 50)
        topic_rect.centerx = SCREEN_WIDTH // 2
        topic_rect.y = start_y + index * 65

        draw_topic_card(topic_rect, topic, "NUMBER BLOCK", index == selected_number_topic)

    draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, start_y + (len(number_block_topics)*65) + 40)


# =========================================================
# MONEY TOPICS
# =========================================================

def draw_money_topics():

    draw_world_background("MONEY")
    draw_world_particles("MONEY", animation_time)

    draw_world_title("MONEY", "MONEY", 55)
    draw_text("SELECT TOPIC", font_instruction, WHITE, SCREEN_WIDTH // 2, 95)

    start_y = 150

    for index, topic in enumerate(money_topics):
        # ---------------------------------------------
        # FIXED: Centered Money Topic List
        # ---------------------------------------------
        topic_rect = pygame.Rect(0, 0, 550, 50)
        topic_rect.centerx = SCREEN_WIDTH // 2
        topic_rect.y = start_y + index * 65

        draw_topic_card(topic_rect, topic, "MONEY", index == selected_money_topic)

    draw_text("UP / DOWN = Select   |   ENTER = Confirm   |   ESC = Back", font_instruction, WHITE, SCREEN_WIDTH // 2, start_y + (len(money_topics)*65) + 40)


# =========================================================
# MONEY GAME
# =========================================================

def draw_money_game():

    draw_world_background("MONEY")
    draw_world_particles("MONEY", animation_time)

    panel = pygame.Rect(0, 0, 860, 470)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 25
    draw_content_panel(panel, "MONEY")

    if money_game.mode == "total":
        title = "MONEY - FINDING TOTAL SPENT"
    elif money_game.mode == "change":
        title = "MONEY - FINDING CHANGE"
    elif money_game.mode == "savings":
        title = "MONEY - CALCULATING SAVINGS"
    else:
        title = "MONEY - MAKE THE EXACT AMOUNT"

    draw_text(title, title_font, BLUE, SCREEN_WIDTH // 2, 45)
    draw_text(f"Question {money_game.question_number} / {money_game.total_questions}", small_font, BLACK, SCREEN_WIDTH // 2, 90)

    draw_multiline_text(money_game.question, small_font, BLACK, SCREEN_WIDTH // 2, 135, 700)

    draw_text("YOUR ANSWER", small_font, BLUE, SCREEN_WIDTH // 2, 230)
    draw_text(f"₱{money_game.user_answer}", large_font, BLACK, SCREEN_WIDTH // 2, 280)

    if not money_game.selected_money:
        draw_text("No money selected", small_font, BLACK, SCREEN_WIDTH // 2, 340)
    else:
        plus_surface = small_font.render(" + ", True, BLACK)
        plus_width = plus_surface.get_width()
        
        total_width = 0
        drawn_items = []
        
        for i, value in enumerate(money_game.selected_money):
            text_surf = small_font.render(f"₱{value}", True, BLACK)
            img = coin_images.get(value)
            
            img_width = img.get_width() + 5 if img else 0
            segment_width = img_width + text_surf.get_width()
            
            if i < len(money_game.selected_money) - 1:
                segment_width += plus_width
                
            total_width += segment_width
            drawn_items.append((img, text_surf))
            
        start_x = (SCREEN_WIDTH - total_width) // 2
        current_x = start_x
        center_y = 340
        
        for i, (img, text_surf) in enumerate(drawn_items):
            if img:
                img_y = center_y - (img.get_height() // 2)
                screen.blit(img, (current_x, img_y))
                current_x += img.get_width() + 5
            
            text_y = center_y - (text_surf.get_height() // 2)
            screen.blit(text_surf, (current_x, text_y))
            current_x += text_surf.get_width()
            
            if i < len(drawn_items) - 1:
                plus_y = center_y - (plus_surface.get_height() // 2)
                screen.blit(plus_surface, (current_x, plus_y))
                current_x += plus_width

    draw_text("Maximum answer: ₱50", small_font, GRAY, SCREEN_WIDTH // 2, 390)
    draw_text("Use ₱1, ₱5, ₱10, ₱20 buttons", small_font, BLACK, SCREEN_WIDTH // 2, 430)
    draw_text("ENTER = Submit", small_font, BLUE, SCREEN_WIDTH // 2, 470)


# =========================================================
# MONEY RESULT
# =========================================================

def draw_money_result():
    draw_world_background("MONEY")
    draw_world_particles("MONEY", animation_time)

    panel = pygame.Rect(0, 0, 700, 380)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 90
    draw_content_panel(panel, "MONEY")

    draw_text("MONEY GAME RESULT", title_font, BLUE, SCREEN_WIDTH // 2, 140)

    if money_game.score >= 8: message = "WELL DONE!"
    elif money_game.score >= 4: message = "GOOD JOB! KEEP PRACTICING!"
    else: message = "KEEP PRACTICING!"

    draw_text(message, large_font, BLUE, SCREEN_WIDTH // 2, 210)
    draw_text(f"SCORE: {money_game.score} / {money_game.total_questions}", large_font, BLACK, SCREEN_WIDTH // 2, 300)
    draw_text("Great job!", button_font, (40, 140, 60), SCREEN_WIDTH // 2, 370)
    draw_text("PRESS ENTER TO RETURN TO GAME SELECTION", small_font, BLACK, SCREEN_WIDTH // 2, 430)


# =========================================================
# TEACHER DASHBOARD
# =========================================================

def topic_of(game_type):
    """'NUMBER BLOCK - COUNTING' -> 'NUMBER BLOCK'."""
    return game_type.split(" - ")[0].strip() if " - " in game_type else "OTHER"


MONEY_ACTIVITY_NAMES = {
    "TOTAL": "FINDING TOTAL SPENT",
    "CHANGE": "FINDING CHANGE",
    "SAVINGS": "CALCULATING SAVINGS",
    "MAKE": "MAKE THE EXACT AMOUNT",
}


def activity_of(game_type):
    """'NUMBER BLOCK - COUNTING' -> 'COUNTING'; MONEY modes get their
    full on-screen activity names."""
    name = game_type.split(" - ", 1)[1].strip() if " - " in game_type else game_type
    if topic_of(game_type) == "MONEY":
        return MONEY_ACTIVITY_NAMES.get(name, name)
    return name


def build_activity_summary(game_type, sessions):
    """Aggregates real saved sessions for one activity. Nothing invented:
    every number is derived from the attempts table."""
    total_questions = sum(x["total_questions"] for x in sessions)
    total_correct = sum(x["score"] for x in sessions)
    weighted_time = sum(x["average_time"] * x["total_questions"] for x in sessions)
    best = max(sessions, key=lambda x: (x["score"], -x["average_time"]))
    latest = sessions[-1]
    return {
        "game_type": game_type,
        "attempts": len(sessions),
        "best_score": best["score"],
        "best_total": best["total_questions"],
        "average_time": weighted_time / total_questions if total_questions else 0.0,
        "accuracy": (100.0 * total_correct / total_questions) if total_questions else 0.0,
        "status": latest["status"],
        "last_timestamp": latest.get("last_timestamp") or ""
    }


def refresh_detail_rows():
    """Rebuilds dashboard_detail_rows for the current view/filter."""
    global dashboard_detail_rows, dashboard_detail_selected, dashboard_detail_scroll

    if dashboard_detail_view == "SUMMARY":
        wanted = dashboard_detail_topics[dashboard_detail_filter]
        rows = [
            build_activity_summary(gt, sessions)
            for gt, sessions in dashboard_detail_summary.items()
            if sessions and (wanted == "ALL" or topic_of(gt) == wanted)
        ]
        rows.sort(key=lambda r: r["game_type"])
    else:
        sessions = dashboard_detail_summary.get(dashboard_detail_activity, [])
        rows = []
        count = len(sessions)
        for number, session in enumerate(reversed(sessions)):   # newest first
            rows.append({"attempt_number": count - number, **session})

    dashboard_detail_rows = rows
    dashboard_detail_selected = min(dashboard_detail_selected, max(0, len(rows) - 1))
    dashboard_detail_scroll = 0


def open_student_detail(student_id, student_name):
    """Loads the student's real saved attempts (grouped into sessions
    by get_student_dashboard_summary) and shows the SUMMARY view."""
    global dashboard_detail_student_id, dashboard_detail_student_name
    global dashboard_detail_summary, dashboard_detail_view, dashboard_detail_activity
    global dashboard_detail_topics, dashboard_detail_filter, dashboard_detail_selected

    dashboard_detail_student_id = student_id
    dashboard_detail_student_name = student_name
    dashboard_detail_summary = get_student_dashboard_summary(student_id)
    dashboard_detail_view = "SUMMARY"
    dashboard_detail_activity = None
    dashboard_detail_topics = ["ALL"] + sorted({topic_of(gt) for gt in dashboard_detail_summary})
    dashboard_detail_filter = 0
    dashboard_detail_selected = 0
    refresh_detail_rows()


def detail_open_selected():
    global dashboard_detail_view, dashboard_detail_activity, dashboard_detail_selected
    if dashboard_detail_view == "SUMMARY" and dashboard_detail_rows:
        dashboard_detail_activity = dashboard_detail_rows[dashboard_detail_selected]["game_type"]
        dashboard_detail_view = "HISTORY"
        dashboard_detail_selected = 0
        refresh_detail_rows()


def detail_go_back():
    """HISTORY -> SUMMARY -> student list."""
    global dashboard_detail_view, dashboard_detail_selected, current_screen
    if dashboard_detail_view == "HISTORY":
        dashboard_detail_view = "SUMMARY"
        dashboard_detail_selected = 0
        refresh_detail_rows()
    else:
        current_screen = TEACHER_DASHBOARD


def detail_cycle_filter(step):
    global dashboard_detail_filter, dashboard_detail_selected
    if dashboard_detail_view != "SUMMARY":
        return
    dashboard_detail_filter = (dashboard_detail_filter + step) % len(dashboard_detail_topics)
    dashboard_detail_selected = 0
    refresh_detail_rows()


def draw_teacher_login():
    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]

    draw_world_title("TEACHER LOGIN", "TEACHER", 70)

    box_width, box_height = 420, 60
    username_box = pygame.Rect(0, 0, box_width, box_height)
    username_box.centerx = SCREEN_WIDTH // 2
    username_box.y = 190

    password_box = pygame.Rect(0, 0, box_width, box_height)
    password_box.centerx = SCREEN_WIDTH // 2
    password_box.y = 270

    draw_text("USERNAME", font_instruction, theme["accent"], username_box.centerx, username_box.top - 18)
    pygame.draw.rect(screen, WHITE, username_box, border_radius=10)
    pygame.draw.rect(screen, theme["border"] if teacher_login_field == 0 else GRAY, username_box,
                      4 if teacher_login_field == 0 else 2, border_radius=10)
    draw_text(teacher_username_input or "teacher", button_font, BLACK, username_box.centerx, username_box.centery)

    draw_text("PASSWORD", font_instruction, theme["accent"], password_box.centerx, password_box.top - 18)
    pygame.draw.rect(screen, WHITE, password_box, border_radius=10)
    pygame.draw.rect(screen, theme["border"] if teacher_login_field == 1 else GRAY, password_box,
                      4 if teacher_login_field == 1 else 2, border_radius=10)
    masked = "*" * len(teacher_password_input)
    draw_text(masked if masked else "ENTER PASSWORD", button_font,
              BLACK if masked else GRAY, password_box.centerx, password_box.centery)

    if teacher_login_error:
        draw_text(teacher_login_error, font_instruction, RED, SCREEN_WIDTH // 2, 350)

    draw_text("UP / DOWN = Switch Field   |   ENTER = Login   |   ESC = Back",
              font_instruction, BLACK, SCREEN_WIDTH // 2, 470)


def draw_teacher_dashboard():
    global dashboard_scroll_offset, dashboard_click_targets

    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]
    draw_world_title("TEACHER DASHBOARD", "TEACHER", 55)
    draw_text("STUDENT PERFORMANCE", font_topic_title, theme["accent"], SCREEN_WIDTH // 2, 100)

    if not dashboard_students:
        draw_text("NO STUDENTS REGISTERED YET", button_font, GRAY, SCREEN_WIDTH // 2, 260)
        draw_text("ESC = Back to Home", font_instruction, BLACK, SCREEN_WIDTH // 2, 430)
        return

    visible_items = 6
    total = len(dashboard_students)

    if dashboard_selected_student < dashboard_scroll_offset:
        dashboard_scroll_offset = dashboard_selected_student
    elif dashboard_selected_student >= dashboard_scroll_offset + visible_items:
        dashboard_scroll_offset = dashboard_selected_student - visible_items + 1

    start_y = 140
    for i in range(dashboard_scroll_offset, min(total, dashboard_scroll_offset + visible_items)):
        student_id, name = dashboard_students[i]
        row_y = start_y + (i - dashboard_scroll_offset) * 60

        card = pygame.Rect(0, 0, 560, 48)
        card.centerx = SCREEN_WIDTH // 2
        card.y = row_y

        drawn_rect = draw_game_button(card, name, "TEACHER", i == dashboard_selected_student,
                                       font=font_dashboard)

        def make_action(sid=student_id, sname=name):
            def action():
                global current_screen
                open_student_detail(sid, sname)
                current_screen = TEACHER_STUDENT_DETAIL
            return action

        dashboard_click_targets.append((drawn_rect, make_action()))

    draw_text("UP / DOWN = Select   |   ENTER = View Performance   |   ESC = Back",
              font_instruction, BLACK, SCREEN_WIDTH // 2, start_y + visible_items * 60 + 25)


def dashboard_scroll_clamped(total, visible_items):
    """Keeps the selected card in view."""
    global dashboard_detail_scroll
    if dashboard_detail_selected < dashboard_detail_scroll:
        dashboard_detail_scroll = dashboard_detail_selected
    elif dashboard_detail_selected >= dashboard_detail_scroll + visible_items:
        dashboard_detail_scroll = dashboard_detail_selected - visible_items + 1
    dashboard_detail_scroll = max(0, min(dashboard_detail_scroll, max(0, total - visible_items)))
    return dashboard_detail_scroll


def draw_teacher_student_detail():
    global dashboard_click_targets, dashboard_detail_selected

    draw_world_background("TEACHER")
    theme = WORLD_THEMES["TEACHER"]
    draw_world_title(dashboard_detail_student_name, "TEACHER", 45)

    # ---- back button (mouse + same action as ESC)
    drawn_back = draw_game_button(pygame.Rect(20, 20, 100, 40), "< BACK", "TEACHER", False, font=font_dashboard_small)
    dashboard_click_targets.append((drawn_back, detail_go_back))

    in_summary = (dashboard_detail_view == "SUMMARY")

    if in_summary:
        draw_text("ACTIVITY SUMMARY", font_instruction, theme["accent"], SCREEN_WIDTH // 2, 88)
        # ---- topic filter chips (LEFT / RIGHT or click)
        chip_w, chip_h, gap = 190, 32, 12
        total_w = len(dashboard_detail_topics) * chip_w + (len(dashboard_detail_topics) - 1) * gap
        x = (SCREEN_WIDTH - total_w) // 2
        for index, topic in enumerate(dashboard_detail_topics):
            chip = pygame.Rect(x, 104, chip_w, chip_h)
            drawn = draw_game_button(chip, topic, "TEACHER", index == dashboard_detail_filter, font=font_dashboard_small)
            def make_filter(i=index):
                def action():
                    global dashboard_detail_filter, dashboard_detail_selected
                    dashboard_detail_filter = i
                    dashboard_detail_selected = 0
                    refresh_detail_rows()
                return action
            dashboard_click_targets.append((drawn, make_filter()))
            x += chip_w + gap
    else:
        draw_text(f"{activity_of(dashboard_detail_activity)}  -  PREVIOUS ATTEMPTS (newest first)",
                  font_instruction, theme["accent"], SCREEN_WIDTH // 2, 100)

    if not dashboard_detail_rows:
        message = "NO SAVED ATTEMPTS YET" if not dashboard_detail_summary else "NO ACTIVITIES IN THIS TOPIC"
        draw_text(message, button_font, GRAY, SCREEN_WIDTH // 2, 280)
        draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 430)
        return

    visible_items = 4
    total = len(dashboard_detail_rows)
    card_height = 88
    start_y = 150
    scroll = dashboard_scroll_clamped(total, visible_items)

    for i in range(scroll, min(total, scroll + visible_items)):
        row = dashboard_detail_rows[i]
        card = pygame.Rect(0, 0, 880, card_height - 10)
        card.centerx = SCREEN_WIDTH // 2
        card.y = start_y + (i - scroll) * card_height
        selected = (i == dashboard_detail_selected)

        pygame.draw.rect(screen, WHITE, card, border_radius=12)
        pygame.draw.rect(screen, theme["button_selected"] if selected else (200, 204, 214), card,
                          4 if selected else 2, border_radius=12)

        if in_summary:
            best_fraction = row["best_score"] / row["best_total"] if row["best_total"] else 0
            draw_text(topic_of(row["game_type"]), font_dashboard_small, GRAY, card.left + 150, card.top + 18)
            draw_text_fit(activity_of(row["game_type"]), [font_dashboard, font_dashboard_small], theme["accent"], card.left + 150, card.top + 42, 290)
            draw_text(f"ATTEMPTS: {row['attempts']}", font_dashboard_small, BLACK, card.left + 150, card.top + 64)
            draw_progress_bar(card.left + 305, card.top + 18, 190, 16, best_fraction, STATUS_COLORS.get(row["status"], GRAY))
            draw_text(f"BEST SCORE: {row['best_score']} / {row['best_total']}", font_dashboard_small, BLACK, card.left + 400, card.top + 50)
            draw_text(f"AVG TIME: {row['average_time']:.2f} sec", font_dashboard_small, BLACK, card.left + 615, card.top + 24)
            draw_text(f"ACCURACY: {row['accuracy']:.0f}%", font_dashboard_small, BLACK, card.left + 615, card.top + 50)
            draw_status_badge(row["status"], card.left + 800, card.top + 34)
            draw_text("LATEST", font_hint, GRAY, card.left + 800, card.top + 58)

            def make_open(i=i):
                def action():
                    global dashboard_detail_selected
                    dashboard_detail_selected = i
                    detail_open_selected()
                return action
            dashboard_click_targets.append((card.copy(), make_open()))
        else:
            fraction = row["score"] / row["total_questions"] if row["total_questions"] else 0
            accuracy = 100.0 * fraction
            draw_text(f"ATTEMPT #{row['attempt_number']}", font_dashboard, theme["accent"], card.left + 130, card.top + 26)
            draw_text((row.get("last_timestamp") or "")[:16], font_dashboard_small, GRAY, card.left + 130, card.top + 52)
            draw_progress_bar(card.left + 265, card.top + 18, 190, 16, fraction, STATUS_COLORS.get(row["status"], GRAY))
            draw_text(f"SCORE: {row['score']} / {row['total_questions']}", font_dashboard_small, BLACK, card.left + 360, card.top + 50)
            draw_text(f"AVG TIME: {row['average_time']:.2f} sec", font_dashboard_small, BLACK, card.left + 615, card.top + 24)
            draw_text(f"ACCURACY: {accuracy:.0f}%", font_dashboard_small, BLACK, card.left + 615, card.top + 50)
            draw_status_badge(row["status"], card.left + 800, card.top + 38)

            def make_select(i=i):
                def action():
                    global dashboard_detail_selected
                    dashboard_detail_selected = i
                return action
            dashboard_click_targets.append((card.copy(), make_select()))

    if total > visible_items:
        draw_text(f"{scroll + 1}-{min(total, scroll + visible_items)} of {total}", font_hint, GRAY, SCREEN_WIDTH - 70, 88)

    hint = ("UP / DOWN = Select   |   LEFT / RIGHT = Topic Filter   |   ENTER = Previous Attempts   |   ESC = Back"
            if in_summary else "UP / DOWN = Scroll   |   ESC = Back to Summary")
    draw_text(hint, font_hint, BLACK, SCREEN_WIDTH // 2, start_y + visible_items * card_height + 20)


# =========================================================
# PLACEHOLDER GAME SCREENS
# =========================================================

def draw_placeholder(title, description):
    theme_key = title if title in WORLD_THEMES else "HOME"
    draw_world_background(theme_key)
    draw_world_particles(theme_key, animation_time)

    theme = WORLD_THEMES[theme_key]
    draw_world_title(title, theme_key, 80)
    draw_text(theme["title"], font_topic_title, theme["accent"], SCREEN_WIDTH // 2, 135)

    panel = pygame.Rect(0, 0, 640, 140)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 190
    pygame.draw.rect(screen, (255, 255, 255), panel, border_radius=16)
    pygame.draw.rect(screen, theme["border"], panel, 4, border_radius=16)

    draw_text(description, button_font, BLACK, panel.centerx, panel.top + 45)
    draw_text("THIS ACTIVITY IS COMING SOON", small_font, theme["accent"], panel.centerx, panel.top + 95)

    draw_text("ESC = Back", font_instruction, BLACK, SCREEN_WIDTH // 2, 420)


# =========================================================
# COUNTING GAME
# =========================================================

def draw_counting_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 820, 400)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 35
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("COUNTING - FILL IN THE BLANKS", title_font, BLUE, SCREEN_WIDTH // 2, 50)
    draw_text(f"Question {counting_game.current_question + 1} / {counting_game.total_questions}", small_font, BLACK, SCREEN_WIDTH // 2, 90)

    numbers = counting_game.question
    total_sequence_width = (len(numbers) - 1) * 110
    start_x = (SCREEN_WIDTH - total_sequence_width) // 2

    for index, number in enumerate(numbers):
        x = start_x + index * 110
        if number is None:
            draw_text("__", large_font, BLUE, x, 190)
        else:
            draw_text(str(number), large_font, BLACK, x, 190)

    draw_text("YOUR ANSWER", button_font, BLACK, SCREEN_WIDTH // 2, 275)

    answer_box = pygame.Rect(0, 0, 200, 65)
    answer_box.centerx = SCREEN_WIDTH // 2
    answer_box.y = 310

    pygame.draw.rect(screen, WHITE, answer_box)
    pygame.draw.rect(screen, BLUE, answer_box, 4)

    draw_text(counting_game.user_answer, large_font, BLACK, answer_box.centerx, answer_box.centery)
    draw_text("Type your answer", small_font, BLACK, SCREEN_WIDTH // 2, 400)
    draw_text("ENTER = Submit   |   BACKSPACE = Delete", small_font, GREEN, SCREEN_WIDTH // 2, 435)


# =========================================================
# COUNTING RESULT
# =========================================================

def draw_counting_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 620, 300)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 90
    draw_content_panel(panel, "NUMBER BLOCK")

    score = counting_game.score
    total = counting_game.total_questions

    draw_text("WELL DONE!", title_font, (40, 140, 60), SCREEN_WIDTH // 2, 150)
    draw_text(f"SCORE: {score} / {total}", large_font, BLUE, SCREEN_WIDTH // 2, 230)
    draw_text("Great job!", button_font, (40, 140, 60), SCREEN_WIDTH // 2, 300)
    draw_text("Press ENTER to return to Game Selection", small_font, BLACK, SCREEN_WIDTH // 2, 355)


# =========================================================
# ADDITION UP TO 20
# =========================================================

def draw_addition_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 620, 320)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 55
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("ADDITION UP TO 20", title_font, BLUE, SCREEN_WIDTH // 2, 70)
    draw_text(f"Question {addition_game.current_question + 1} / {addition_game.total_questions}", small_font, BLACK, SCREEN_WIDTH // 2, 120)
    draw_text(f"{addition_game.num1} + {addition_game.num2} = ?", large_font, BLACK, SCREEN_WIDTH // 2, 190)

    answer_box = pygame.Rect(0, 0, 200, 70)
    answer_box.centerx = SCREEN_WIDTH // 2
    answer_box.y = 250

    pygame.draw.rect(screen, WHITE, answer_box)
    pygame.draw.rect(screen, BLUE, answer_box, 4)

    draw_text(addition_game.user_answer, large_font, BLACK, answer_box.centerx, answer_box.centery)
    draw_text("ENTER = Submit   |   BACKSPACE = Delete", small_font, BLACK, SCREEN_WIDTH // 2, 380)


# =========================================================
# ADDITION RESULT
# =========================================================

def draw_addition_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 640, 300)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 100
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("ADDITION UP TO 20", title_font, BLUE, SCREEN_WIDTH // 2, 140)

    message = "WELL DONE!" if addition_game.score >= 8 else "GOOD JOB! KEEP PRACTICING!" if addition_game.score >= 4 else "KEEP PRACTICING!"
    draw_text(message, large_font, BLUE, SCREEN_WIDTH // 2, 215)
    draw_text(f"SCORE: {addition_game.score} / {addition_game.total_questions}", large_font, BLACK, SCREEN_WIDTH // 2, 300)
    draw_text("PRESS ENTER TO RETURN TO GAME SELECTION", small_font, BLACK, SCREEN_WIDTH // 2, 365)


# =========================================================
# ADDITION UP TO 100
# =========================================================

def draw_addition100_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 620, 320)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 55
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("ADDITION UP TO 100", title_font, BLUE, SCREEN_WIDTH // 2, 70)
    draw_text(f"Question {addition100_game.current_question + 1} / {addition100_game.total_questions}", small_font, BLACK, SCREEN_WIDTH // 2, 120)
    draw_text(f"{addition100_game.num1} + {addition100_game.num2} = ?", large_font, BLACK, SCREEN_WIDTH // 2, 190)

    answer_box = pygame.Rect(0, 0, 200, 70)
    answer_box.centerx = SCREEN_WIDTH // 2
    answer_box.y = 250

    pygame.draw.rect(screen, WHITE, answer_box)
    pygame.draw.rect(screen, BLUE, answer_box, 4)

    draw_text(addition100_game.user_answer, large_font, BLACK, answer_box.centerx, answer_box.centery)
    draw_text("ENTER = Submit   |   BACKSPACE = Delete", small_font, BLACK, SCREEN_WIDTH // 2, 380)


# =========================================================
# ADDITION 100 RESULT
# =========================================================

def draw_addition100_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 640, 300)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 90
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("ADDITION UP TO 100", title_font, BLUE, SCREEN_WIDTH // 2, 130)

    message = "WELL DONE!" if addition100_game.score >= 8 else "GOOD JOB! KEEP PRACTICING!" if addition100_game.score >= 4 else "KEEP PRACTICING!"
    draw_text(message, large_font, BLUE, SCREEN_WIDTH // 2, 205)
    draw_text(f"SCORE: {addition100_game.score} / {addition100_game.total_questions}", large_font, BLACK, SCREEN_WIDTH // 2, 290)
    draw_text("PRESS ENTER TO RETURN TO GAME SELECTION", small_font, BLACK, SCREEN_WIDTH // 2, 355)


# =========================================================
# SUBTRACTION UP TO 100
# =========================================================

def draw_subtraction100_game():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 720, 320)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 55
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("SUBTRACTION UP TO 100", title_font, BLUE, SCREEN_WIDTH // 2, 70)
    draw_text(f"Question {subtraction100_game.current_question + 1} / {subtraction100_game.total_questions}", small_font, BLACK, SCREEN_WIDTH // 2, 120)
    draw_text(f"{subtraction100_game.num1} - {subtraction100_game.num2} = ?", large_font, BLACK, SCREEN_WIDTH // 2, 190)

    answer_box = pygame.Rect(0, 0, 200, 70)
    answer_box.centerx = SCREEN_WIDTH // 2
    answer_box.y = 250

    pygame.draw.rect(screen, WHITE, answer_box)
    pygame.draw.rect(screen, BLUE, answer_box, 4)

    draw_text(subtraction100_game.user_answer, large_font, BLACK, answer_box.centerx, answer_box.centery)
    draw_text("ENTER = Submit   |   BACKSPACE = Delete", small_font, BLACK, SCREEN_WIDTH // 2, 380)


# =========================================================
# SUBTRACTION RESULT
# =========================================================

def draw_subtraction100_result():
    draw_world_background("NUMBER BLOCK")
    draw_world_particles("NUMBER BLOCK", animation_time)

    panel = pygame.Rect(0, 0, 700, 300)
    panel.centerx = SCREEN_WIDTH // 2
    panel.y = 90
    draw_content_panel(panel, "NUMBER BLOCK")

    draw_text("SUBTRACTION UP TO 100", title_font, BLUE, SCREEN_WIDTH // 2, 130)

    message = "WELL DONE!" if subtraction100_game.score >= 8 else "GOOD JOB! KEEP PRACTICING!" if subtraction100_game.score >= 4 else "KEEP PRACTICING!"
    draw_text(message, large_font, BLUE, SCREEN_WIDTH // 2, 205)
    draw_text(f"SCORE: {subtraction100_game.score} / {subtraction100_game.total_questions}", large_font, BLACK, SCREEN_WIDTH // 2, 290)
    draw_text("PRESS ENTER TO RETURN TO GAME SELECTION", small_font, BLACK, SCREEN_WIDTH // 2, 355)


# =========================================================
# ESP32 SERIAL INPUT
# =========================================================

try:
    esp32_serial = serial.Serial(
        "/dev/ttyACM0" if sys.platform.startswith("linux") else "COM6",
        115200,
        timeout=0
    )
    print("ESP32 SERIAL CONNECTED: " + ("/dev/ttyACM0" if sys.platform.startswith("linux") else "COM6"))
except:
    esp32_serial = None
    print("WARNING: ESP32 not connected. Hardware inputs disabled.")

# =========================================================
# ESP32 NUMBER STATE
# =========================================================

esp32_ones = None
esp32_tens = None


# =========================================================
# READ ESP32 INPUT
# =========================================================

def read_esp32_input():
    if esp32_serial is None or esp32_serial.in_waiting <= 0:
        return None
    line = esp32_serial.readline().decode("utf-8", errors="ignore").strip()
    if not line: return None
    print("ESP32 RAW:", line)
    
    if line.startswith("---") or line.startswith("==="): return None
    if line == "UP": return ("BUTTON_UP", None)
    if line == "DOWN": return ("BUTTON_DOWN", None)
    if line == "LEFT": return ("BUTTON_LEFT", None)
    if line == "RIGHT": return ("BUTTON_RIGHT", None)
    if line == "BACK": return ("BUTTON_BACK", None) 
    if line == "SUBMIT PRESSED": return ("BUTTON_SUBMIT", None)

    if line.startswith("MONEY TOTAL:"):
        try: return ("MONEY_TOTAL", int(line.split(":", 1)[1].strip()))
        except ValueError: return None
    if line.startswith("SUBMITTED MONEY INPUT:"):
        try: return ("MONEY_SUBMIT", int(line.split(":", 1)[1].strip()))
        except ValueError: return None
    if line.startswith("NFC TENS:"):
        val = line.split(":", 1)[1].strip()
        if val == "BLANK": return ("TENS_REMOVED", None)
        try: return ("TENS", int(val))
        except ValueError: return None
    if line.startswith("NFC ONES:"):
        val = line.split(":", 1)[1].strip()
        if val == "BLANK": return ("ONES_REMOVED", None)
        try: return ("ONES", int(val))
        except ValueError: return None
    if line.startswith("SUBMITTED NFC INPUT:"):
        try: return ("SUBMITTED", int(line.split(":", 1)[1].strip()))
        except ValueError: return None
    if line == "NO ANSWER INPUT": return ("NO_NUMBER", None)
    return None

def update_nfc_answer(game):
    global esp32_ones, esp32_tens
    if esp32_tens is not None:
        if esp32_ones is not None: game.user_answer = str(esp32_tens) + str(esp32_ones)
        else: game.user_answer = str(esp32_tens)
    elif esp32_ones is not None:
        game.user_answer = str(esp32_ones)
    else:
        game.user_answer = ""

def reset_nfc_input():
    global esp32_ones, esp32_tens
    esp32_ones, esp32_tens = None, None

def post_esp32_key(key):
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, {"key": key, "unicode": ""}))

# =========================================================
# MAIN LOOP
# =========================================================

running = True

while running:

    esp32_input = read_esp32_input()
    if esp32_input is not None:
        input_type, number = esp32_input
        if input_type == "BUTTON_UP": post_esp32_key(pygame.K_UP)
        elif input_type == "BUTTON_DOWN": post_esp32_key(pygame.K_DOWN)
        elif input_type == "BUTTON_LEFT": post_esp32_key(pygame.K_LEFT)
        elif input_type == "BUTTON_RIGHT": post_esp32_key(pygame.K_RIGHT)
        elif input_type == "BUTTON_BACK": post_esp32_key(pygame.K_ESCAPE)
        elif input_type == "BUTTON_SUBMIT": post_esp32_key(pygame.K_RETURN)
        elif input_type == "ONES":
            esp32_ones = number
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "TENS":
            esp32_tens = number
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "ONES_REMOVED":
            esp32_ones = None
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "TENS_REMOVED":
            esp32_tens = None
            if current_screen == COUNTING_GAME: update_nfc_answer(counting_game)
            elif current_screen == ADDITION_GAME: update_nfc_answer(addition_game)
            elif current_screen == ADDITION100_GAME: update_nfc_answer(addition100_game)
            elif current_screen == SUBTRACTION100_GAME: update_nfc_answer(subtraction100_game)
        elif input_type == "NUMBER_CLEARED":
            reset_nfc_input()
            if current_screen == COUNTING_GAME: counting_game.user_answer = ""
            elif current_screen == ADDITION_GAME: addition_game.user_answer = ""
            elif current_screen == ADDITION100_GAME: addition100_game.user_answer = ""
            elif current_screen == SUBTRACTION100_GAME: subtraction100_game.user_answer = ""
        elif input_type == "MONEY_TOTAL":
            if current_screen in [MONEY_TOTAL_GAME, MONEY_CHANGE_GAME, MONEY_SAVINGS_GAME, MONEY_MAKE_GAME]:
                diff = number - money_game.user_answer
                if diff > 0 and diff in money_game.denominations: money_game.add_money(diff)
                elif number == 0: money_game.clear_answer()
                else: money_game.user_answer = number

    # =====================================================
    # PYGAME EVENTS
    # =====================================================

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:

            if current_screen == HOME:
                if event.key == pygame.K_UP:
                    selected_home_option -= 1
                    if selected_home_option < 0: selected_home_option = len(home_menu_options) - 1
                elif event.key == pygame.K_DOWN:
                    selected_home_option += 1
                    if selected_home_option >= len(home_menu_options): selected_home_option = 0
                elif event.key == pygame.K_RETURN:
                    if selected_home_option == 0:
                        load_students()
                        selected_student_option, student_scroll_offset = 0, 0
                        current_screen = STUDENT_SELECTION
                    else:
                        teacher_username_input = TEACHER_USERNAME_DEFAULT
                        teacher_password_input = ""
                        teacher_login_field = 1
                        teacher_login_error = ""
                        current_screen = TEACHER_LOGIN

            elif current_screen == STUDENT_SELECTION:
                total_options = len(students) + 2
                if event.key == pygame.K_UP:
                    selected_student_option -= 1
                    if selected_student_option < 0: selected_student_option = total_options - 1
                elif event.key == pygame.K_DOWN:
                    selected_student_option += 1
                    if selected_student_option >= total_options: selected_student_option = 0
                elif event.key == pygame.K_RETURN:
                    register_index = len(students)
                    delete_index = len(students) + 1
                    if selected_student_option < len(students):
                        current_player_id = students[selected_student_option][0]
                        current_player = students[selected_student_option][1]
                        current_screen = CURRENT_PLAYER
                    elif selected_student_option == register_index:
                        student_name_input, register_focus = "", 0
                        current_screen = REGISTER_STUDENT
                    elif selected_student_option == delete_index:
                        if students:
                            delete_student_index, delete_scroll_offset = 0, 0
                            current_screen = DELETE_STUDENT
                        else: print("NO STUDENTS TO DELETE")
                elif event.key == pygame.K_ESCAPE:
                    current_screen = HOME

            elif current_screen == REGISTER_STUDENT:
                if event.key == pygame.K_ESCAPE:
                    student_name_input = ""
                    current_screen = STUDENT_SELECTION
                elif event.key == pygame.K_LEFT:
                    if register_focus == 1: register_focus = 0
                    else: current_screen = STUDENT_SELECTION
                elif event.key == pygame.K_RIGHT:
                    if register_focus == 0: register_focus = 1
                    else:
                        keyboard_row, keyboard_col = 0, 0
                        current_screen = VIRTUAL_KEYBOARD
                elif event.key == pygame.K_RETURN:
                    if register_focus == 1:
                        keyboard_row, keyboard_col = 0, 0
                        current_screen = VIRTUAL_KEYBOARD
                    else:
                        keyboard_row, keyboard_col = 0, 0
                        current_screen = VIRTUAL_KEYBOARD
                elif event.key == pygame.K_BACKSPACE:
                    student_name_input = student_name_input[:-1]
                else:
                    if event.unicode.isalpha():
                        if len(student_name_input) < 30: student_name_input += event.unicode.upper()

            elif current_screen == VIRTUAL_KEYBOARD:
                if event.key == pygame.K_UP: move_keyboard_up()
                elif event.key == pygame.K_DOWN: move_keyboard_down()
                elif event.key == pygame.K_LEFT: move_keyboard_left()
                elif event.key == pygame.K_RIGHT: move_keyboard_right()
                elif event.key == pygame.K_RETURN:
                    done = select_keyboard_key()
                    if done:
                        if student_name_input.strip(): save_new_student()
                        else: print("Student name cannot be empty.")
                elif event.key == pygame.K_ESCAPE:
                    current_screen = REGISTER_STUDENT

            elif current_screen == DELETE_STUDENT:
                if not students:
                    if event.key == pygame.K_ESCAPE: current_screen = STUDENT_SELECTION
                else:
                    if event.key == pygame.K_UP:
                        delete_student_index -= 1
                        if delete_student_index < 0: delete_student_index = len(students) - 1
                    elif event.key == pygame.K_DOWN:
                        delete_student_index += 1
                        if delete_student_index >= len(students): delete_student_index = 0
                    elif event.key == pygame.K_RETURN:
                        student = students[delete_student_index]
                        deleted = delete_student(student[0])
                        load_students()
                        selected_student_option, delete_scroll_offset = 0, 0
                        current_screen = STUDENT_SELECTION
                    elif event.key == pygame.K_ESCAPE:
                        current_screen = STUDENT_SELECTION

            elif current_screen == CURRENT_PLAYER:
                if event.key == pygame.K_RETURN:
                    selected_game = 0
                    current_screen = GAME_SELECTION
                elif event.key == pygame.K_ESCAPE:
                    current_screen = STUDENT_SELECTION

            elif current_screen == GAME_SELECTION:
                if event.key == pygame.K_UP:
                    selected_game -= 1
                    if selected_game < 0: selected_game = len(game_modules) - 1
                elif event.key == pygame.K_DOWN:
                    selected_game += 1
                    if selected_game >= len(game_modules): selected_game = 0
                elif event.key == pygame.K_RETURN:
                    selected_game_name = game_modules[selected_game]
                    if selected_game_name == "NUMBER BLOCK":
                        selected_number_topic = 0
                        current_screen = NUMBER_BLOCK_TOPICS
                    elif selected_game_name == "MONEY":
                        selected_money_topic = 0
                        current_screen = MONEY_TOPICS
                    elif selected_game_name == "CLOCK":
                        current_screen = CLOCK_GAME
                    elif selected_game_name == "PIZZA FRACTION":
                        current_screen = PIZZA_FRACTION_GAME
                    elif selected_game_name == "MIXED QUICKSTART":
                        current_screen = MIXED_QUICKSTART
                elif event.key == pygame.K_ESCAPE:
                    current_screen = CURRENT_PLAYER

            elif current_screen == NUMBER_BLOCK_TOPICS:
                if event.key == pygame.K_UP:
                    selected_number_topic -= 1
                    if selected_number_topic < 0: selected_number_topic = len(number_block_topics) - 1
                elif event.key == pygame.K_DOWN:
                    selected_number_topic += 1
                    if selected_number_topic >= len(number_block_topics): selected_number_topic = 0
                elif event.key == pygame.K_RETURN:
                    if selected_number_topic == 0:
                        counting_game = CountingGame()
                        reset_nfc_input()
                        current_screen = COUNTING_GAME
                    elif selected_number_topic == 1:
                        addition_game = AdditionGame()
                        reset_nfc_input()
                        current_screen = ADDITION_GAME
                    elif selected_number_topic == 2:
                        addition100_game = Addition100Game()
                        reset_nfc_input()
                        current_screen = ADDITION100_GAME
                    elif selected_number_topic == 3:
                        subtraction100_game = Subtraction100Game()
                        reset_nfc_input()
                        current_screen = SUBTRACTION100_GAME
                elif event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen == COUNTING_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: counting_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = counting_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - COUNTING",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=counting_game.session_id
                        )
                        if counting_game.is_finished(): current_screen = COUNTING_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): counting_game.add_digit(event.unicode)

            elif current_screen == ADDITION_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: addition_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = addition_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - ADDITION UP TO 20",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=addition_game.session_id
                        )
                        if addition_game.is_finished(): current_screen = ADDITION_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): addition_game.add_digit(event.unicode)

            elif current_screen == ADDITION100_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: addition100_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = addition100_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - ADDITION UP TO 100",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=addition100_game.session_id
                        )
                        if addition100_game.is_finished(): current_screen = ADDITION100_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): addition100_game.add_digit(event.unicode)

            elif current_screen == SUBTRACTION100_GAME:
                if event.key == pygame.K_ESCAPE:
                    current_screen = NUMBER_BLOCK_TOPICS
                    reset_nfc_input()
                elif event.key == pygame.K_BACKSPACE: subtraction100_game.remove_digit()
                elif event.key == pygame.K_RETURN:
                    result = subtraction100_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type="NUMBER BLOCK - SUBTRACTION UP TO 100",
                            question=result["question"], student_answer=result["user_answer"] if result["user_answer"] is not None else -1,
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", "System adaptation"),
                            session_id=subtraction100_game.session_id
                        )
                        if subtraction100_game.is_finished(): current_screen = SUBTRACTION100_RESULT
                        reset_nfc_input()
                elif event.unicode.isdigit(): subtraction100_game.add_digit(event.unicode)

            elif current_screen in [COUNTING_RESULT, ADDITION_RESULT, ADDITION100_RESULT, SUBTRACTION100_RESULT, MONEY_RESULT]:
                if event.key in [pygame.K_RETURN, pygame.K_ESCAPE]:
                    current_screen = GAME_SELECTION
                    reset_nfc_input()

            elif current_screen == MONEY_TOPICS:
                if event.key == pygame.K_UP:
                    selected_money_topic -= 1
                    if selected_money_topic < 0: selected_money_topic = len(money_topics) - 1
                elif event.key == pygame.K_DOWN:
                    selected_money_topic += 1
                    if selected_money_topic >= len(money_topics): selected_money_topic = 0
                elif event.key == pygame.K_RETURN:
                    if selected_money_topic == 0: money_game = MoneyGame("total"); current_screen = MONEY_TOTAL_GAME
                    elif selected_money_topic == 1: money_game = MoneyGame("change"); current_screen = MONEY_CHANGE_GAME
                    elif selected_money_topic == 2: money_game = MoneyGame("savings"); current_screen = MONEY_SAVINGS_GAME
                    elif selected_money_topic == 3: money_game = MoneyGame("make"); current_screen = MONEY_MAKE_GAME
                elif event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen in [MONEY_TOTAL_GAME, MONEY_CHANGE_GAME, MONEY_SAVINGS_GAME, MONEY_MAKE_GAME]:
                if event.key == pygame.K_RETURN:
                    result = money_game.submit_answer()
                    if result:
                        save_attempt(
                            student_id=current_player_id, game_type=f"MONEY - {money_game.mode.upper()}",
                            question=result["question"], student_answer=result["user_answer"],
                            correct_answer=result["correct_answer"], is_correct=result["correct"],
                            response_time=result["time"], difficulty_before=result["difficulty"],
                            difficulty_after=result["next_difficulty"], decision=result["adaptation"],
                            decision_reason=result.get("decision_reason", ""),
                            session_id=money_game.session_id
                        )
                        if money_game.finished: current_screen = MONEY_RESULT
                elif event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            elif current_screen in [CLOCK_GAME, PIZZA_FRACTION_GAME, MIXED_QUICKSTART]:
                if event.key == pygame.K_ESCAPE:
                    current_screen = GAME_SELECTION

            # =================================================
            # TEACHER LOGIN
            # =================================================
            elif current_screen == TEACHER_LOGIN:
                if event.key == pygame.K_ESCAPE:
                    current_screen = HOME
                elif event.key in (pygame.K_UP, pygame.K_DOWN, pygame.K_TAB):
                    teacher_login_field = 1 - teacher_login_field
                elif event.key == pygame.K_BACKSPACE:
                    if teacher_login_field == 0:
                        teacher_username_input = teacher_username_input[:-1]
                    else:
                        teacher_password_input = teacher_password_input[:-1]
                elif event.key == pygame.K_RETURN:
                    if verify_teacher(teacher_username_input, teacher_password_input):
                        teacher_login_error = ""
                        teacher_logged_in = True
                        dashboard_students = get_students()
                        dashboard_selected_student = 0
                        dashboard_scroll_offset = 0
                        current_screen = TEACHER_DASHBOARD
                    else:
                        teacher_login_error = "INCORRECT USERNAME OR PASSWORD"
                        teacher_password_input = ""
                else:
                    if event.unicode and event.unicode.isprintable():
                        if teacher_login_field == 0:
                            if len(teacher_username_input) < 24:
                                teacher_username_input += event.unicode
                        else:
                            if len(teacher_password_input) < 24:
                                teacher_password_input += event.unicode

            # =================================================
            # TEACHER DASHBOARD - STUDENT LIST
            # =================================================
            elif current_screen == TEACHER_DASHBOARD:
                total_rows = len(dashboard_students)
                if event.key == pygame.K_ESCAPE:
                    teacher_logged_in = False
                    current_screen = HOME
                elif total_rows > 0:
                    if event.key == pygame.K_UP:
                        dashboard_selected_student -= 1
                        if dashboard_selected_student < 0: dashboard_selected_student = total_rows - 1
                    elif event.key == pygame.K_DOWN:
                        dashboard_selected_student += 1
                        if dashboard_selected_student >= total_rows: dashboard_selected_student = 0
                    elif event.key == pygame.K_RETURN:
                        student_id, student_name = dashboard_students[dashboard_selected_student]
                        open_student_detail(student_id, student_name)
                        current_screen = TEACHER_STUDENT_DETAIL

            # =================================================
            # TEACHER DASHBOARD - STUDENT DETAIL
            # =================================================
            elif current_screen == TEACHER_STUDENT_DETAIL:
                if event.key in (pygame.K_ESCAPE, pygame.K_BACKSPACE):
                    detail_go_back()
                elif event.key == pygame.K_LEFT:
                    detail_cycle_filter(-1)
                elif event.key == pygame.K_RIGHT:
                    detail_cycle_filter(1)
                elif dashboard_detail_rows:
                    if event.key == pygame.K_UP:
                        dashboard_detail_selected -= 1
                        if dashboard_detail_selected < 0: dashboard_detail_selected = len(dashboard_detail_rows) - 1
                    elif event.key == pygame.K_DOWN:
                        dashboard_detail_selected += 1
                        if dashboard_detail_selected >= len(dashboard_detail_rows): dashboard_detail_selected = 0
                    elif event.key == pygame.K_RETURN:
                        detail_open_selected()

        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # Dashboard controls are also mouse-clickable, as required.
            # dashboard_click_targets is rebuilt every time a dashboard
            # screen is drawn (see draw_teacher_login / draw_teacher_dashboard
            # / draw_teacher_student_detail below).
            for target_rect, action in dashboard_click_targets:
                if target_rect.collidepoint(event.pos):
                    action()
                    break

    # =====================================================
    # DRAW CURRENT SCREEN
    # =====================================================
    animation_time = pygame.time.get_ticks() / 1000.0
    dashboard_click_targets = []

    if current_screen == HOME: draw_home()
    elif current_screen == STUDENT_SELECTION: 
        draw_student_selection()
    elif current_screen == REGISTER_STUDENT: 
        draw_register_student()
    elif current_screen == DELETE_STUDENT: 
        draw_delete_student()
    elif current_screen == VIRTUAL_KEYBOARD: 
        draw_virtual_keyboard()
    elif current_screen == CURRENT_PLAYER: 
        draw_current_player()
    elif current_screen == GAME_SELECTION: 
        draw_game_selection()
    elif current_screen == NUMBER_BLOCK_TOPICS: 
        draw_number_block_topics()
    elif current_screen == COUNTING_GAME: 
        draw_counting_game()
    elif current_screen == COUNTING_RESULT: 
        draw_counting_result()
    elif current_screen == ADDITION_GAME: 
        draw_addition_game()
    elif current_screen == ADDITION_RESULT: 
        draw_addition_result()
    elif current_screen == ADDITION100_GAME: 
        draw_addition100_game()
    elif current_screen == ADDITION100_RESULT: 
        draw_addition100_result()
    elif current_screen == SUBTRACTION100_GAME: 
        draw_subtraction100_game()
    elif current_screen == SUBTRACTION100_RESULT: 
        draw_subtraction100_result()
    elif current_screen == MONEY_TOPICS: 
        draw_money_topics()
    elif current_screen in [MONEY_TOTAL_GAME, MONEY_CHANGE_GAME, MONEY_SAVINGS_GAME, MONEY_MAKE_GAME]: 
        draw_money_game()
    elif current_screen == MONEY_RESULT: 
        draw_money_result()
    elif current_screen == CLOCK_GAME: 
        draw_placeholder("CLOCK", "Joystick-Controlled Clock Game")
    elif current_screen == PIZZA_FRACTION_GAME: 
        draw_placeholder("PIZZA FRACTION", "½ and ¼ Fraction Game")
    elif current_screen == MIXED_QUICKSTART: 
        draw_placeholder("MIXED QUICKSTART", "Mixed Mathematics Questions")
    elif current_screen == TEACHER_LOGIN:
        draw_teacher_login()
    elif current_screen == TEACHER_DASHBOARD:
        draw_teacher_dashboard()
    elif current_screen == TEACHER_STUDENT_DETAIL:
        draw_teacher_student_detail()

    # -----------------------------------------------------
    # WORLD TRANSITION: short fade-in whenever the player
    # enters a different world (cheap single alpha overlay).
    # -----------------------------------------------------
    current_world = get_world_for_screen(current_screen)
    if current_world != last_world:
        last_world = current_world
        world_transition_start = animation_time
    fade_progress = (animation_time - world_transition_start) / WORLD_TRANSITION_SECONDS
    if fade_progress < 1.0:
        fade_surface.set_alpha(int(255 * (1.0 - fade_progress)))
        fade_surface.fill(WORLD_THEMES[current_world]["sky_top"])
        screen.blit(fade_surface, (0, 0))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()