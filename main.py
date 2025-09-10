
# eco_jump.py
# Endless Doodle-Jump-like game with energy-saving theme.
# Code: English; UI: Russian.
# Run: python eco_jump.py
# Works on PC and Android (touch supported)
# Dependencies: pygame>=2.0

import os
import sys
import math
import random
import json
from typing import List, Optional, Dict, Tuple

import pygame
from pygame import Rect, Surface

# -----------------------------------------------------------------------------
# Initialization
# -----------------------------------------------------------------------------
pygame.init()
pygame.font.init()
try:
    pygame.mixer.init()
except Exception:
    pass

# -----------------------------------------------------------------------------
# Config and constants
# -----------------------------------------------------------------------------
WIDTH, HEIGHT = 460, 720
FPS = 60
TITLE = "Eco Jump — Сохрани энергию!"

# Safe data directory (relative folder "data")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
SCORES_FILE = os.path.join(DATA_DIR, "scores.json")

# Physics and movement
GRAVITY = 0.50
PLAYER_MOVE_SPEED = 6.2
PLAYER_JUMP_VEL = -14.0
PLAYER_W = 50
PLAYER_H = 50
SCROLL_TRIGGER_Y = int(HEIGHT * 0.40)  # keep player around lower-middle

# Energy system
INITIAL_ENERGY = 100.0
PASSIVE_ENERGY_DRAIN = 0.048         # per frame (~2.88/s)
ENEMY_HIT_ENERGY_LOSS = 22.0
FALL_ENERGY_LOSS = 1000.0            # falling off screen drains all
ENERGY_FROM_SOLAR = 14.0
ENERGY_FROM_WIND = 7.0
ENERGY_FROM_HYDRO = 9.0
ENERGY_FROM_CELL = 22.0

# Effects durations (frames @ 60 FPS)
DUR_LED = int(14 * FPS)      # LED effect: reduced drain
DUR_SHIELD = int(12 * FPS)   # insulation shield
DUR_JET = int(2.0 * FPS)     # jetpack continuous upward
DUR_INVINCIBLE = int(2.0 * FPS)

# Platform settings
PLATFORM_W = 104
PLATFORM_H = 16
SPAWN_MIN_GAP = 90
SPAWN_MAX_GAP = 170
SPAWN_X_MARGIN = 24
MAX_PLATFORMS_ON_SCREEN = 22

# Enemy settings (base; scaled by difficulty later)
ENEMY_BASE_SPAWN_CHANCE = 0.06
ENEMY_PATROL_SPEED = 1.3
ENEMY_SINE_SPEED = 0.03
ENEMY_CHASER_SPEED = 2.0

# Bonus spawn chance
BONUS_CHANCE_BASE = 0.22

# States
STATE_MENU = "menu"
STATE_PLAY = "play"
STATE_PAUSE = "pause"
STATE_QUIZ = "quiz"
STATE_GAMEOVER = "gameover"

# Platform types
P_NORMAL = "normal"
P_SOLAR = "solar"
P_WIND = "wind"
P_HYDRO = "hydro"
P_MOVING = "moving"
P_BREAKING = "breaking"
P_DISAPPEARING = "disappearing"
P_SPRING = "spring"  # visual spring on platform (spawns on it)

# Enemy types with patterns
E_BULB = "bulb"       # patrol + sine
E_PIPE = "pipe"       # bobbing vertical
E_SMOKE = "smoke"     # slow rise cloud
E_CHASER = "chaser"   # mild chaser hover (kept fair)

# Bonus types
B_CELL = "cell"       # energy cell
B_LED = "led"         # reduce drain
B_SHIELD = "shield"   # one-hit protection
B_JET = "jetpack"     # sustained upward boost
B_SPRING = "spring"   # instant powerful jump

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY_DARK = (22, 24, 28)
GRAY = (40, 44, 52)
GRAY_LIGHT = (200, 208, 220)
GREEN = (90, 240, 180)
GREEN_SOFT = (120, 255, 200)
YELLOW = (255, 220, 90)
RED = (255, 90, 90)
CYAN = (120, 230, 255)
NEON = (120, 255, 240)
BLUE = (70, 200, 255)
PURPLE = (180, 140, 255)
ORANGE = (255, 160, 80)

# -----------------------------------------------------------------------------
# Utilities and persistence
# -----------------------------------------------------------------------------
def clamp(v, lo, hi):
    return max(lo, min(hi, v))

def lerp(a, b, t):
    return a + (b - a) * t

def load_scores():
    if not os.path.exists(SCORES_FILE):
        return {"high_score": 0}
    try:
        with open(SCORES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data["high_score"] = int(data.get("high_score", 0))
            return data
    except Exception:
        return {"high_score": 0}

def save_scores(data):
    try:
        high = int(data.get("high_score", 0))
        with open(SCORES_FILE, "w", encoding="utf-8") as f:
            json.dump({"high_score": high}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

def load_font(name, size, bold=False):
    try:
        return pygame.font.SysFont(name, size, bold=bold)
    except Exception:
        return pygame.font.Font(None, size)

FONT_TITLE = load_font("Arial", 52, True)
FONT_UI = load_font("Arial", 26)
FONT_SMALL = load_font("Arial", 20)
FONT_TINY = load_font("Arial", 16)

# -----------------------------------------------------------------------------
# Visual helpers (neon style)
# -----------------------------------------------------------------------------
def neon_rect(surface, rect, color, glow_color, glow_strength=8, border=2, radius=8):
    glow = Surface((rect.width + glow_strength*2, rect.height + glow_strength*2), pygame.SRCALPHA)
    for i in range(glow_strength, 0, -1):
        alpha = int(12 * (i / glow_strength))
        pygame.draw.rect(glow, (*glow_color, alpha),
                         (i, i, rect.width + (glow_strength - i)*2, rect.height + (glow_strength - i)*2),
                         border, border_radius=radius)
    surface.blit(glow, (rect.x - glow_strength, rect.y - glow_strength))
    pygame.draw.rect(surface, color, rect, border, border_radius=radius)

def gradient_bg(surface, top_color, bottom_color):
    h = surface.get_height()
    for y in range(h):
        t = y / (h - 1)
        col = (int(lerp(top_color[0], bottom_color[0], t)),
               int(lerp(top_color[1], bottom_color[1], t)),
               int(lerp(top_color[2], bottom_color[2], t)))
        pygame.draw.line(surface, col, (0, y), (surface.get_width(), y))

class ParallaxLayer:
    def __init__(self, speed, color, density, size_range):
        self.speed = speed
        self.color = color
        self.density = density
        self.size_range = size_range
        self.stars = []
        self.reset()

    def reset(self):
        self.stars.clear()
        for _ in range(self.density):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            s = random.randint(*self.size_range)
            self.stars.append([x, y, s])

    def update(self, dy):
        for st in self.stars:
            st[1] += dy * self.speed
            if st[1] > HEIGHT + 2:
                st[0] = random.randint(0, WIDTH)
                st[1] = random.uniform(-40, -5)
                st[2] = random.randint(*self.size_range)

    def draw(self, surface):
        for st in self.stars:
            pygame.draw.circle(surface, self.color, (int(st[0]), int(st[1])), st[2])

# -----------------------------------------------------------------------------
# Entities
# -----------------------------------------------------------------------------
class Player(pygame.sprite.Sprite):
    def __init__(self, x, y, lives=2):
        super().__init__()
        self.image = Surface((PLAYER_W, PLAYER_H), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.prev_rect = self.rect.copy()
        self.vel = pygame.Vector2(0, 0)

        self.energy = INITIAL_ENERGY
        self.lives = lives
        self.score = 0

        # Effects
        self.drain_slow = 0
        self.shield = 0
        self.jet = 0
        self.invincible = 0

        self.facing = 1
        self.anim_t = 0.0
        self.last_safe_platform: Optional['Platform'] = None

        self.draw()

    def draw(self):
        self.image.fill((0, 0, 0, 0))
        base = Surface((PLAYER_W, PLAYER_H), pygame.SRCALPHA)
        body_rect = Rect(8, 6, PLAYER_W - 16, PLAYER_H - 12)
        pygame.draw.rect(base, (40, 200, 230), body_rect, border_radius=10)
        neon_rect(base, body_rect, (120, 255, 240), (120, 255, 240), glow_strength=6, border=3, radius=10)
        # Eye
        eye_y = 18
        eye_x = 18 if self.facing < 0 else PLAYER_W - 18
        pygame.draw.circle(base, WHITE, (eye_x, eye_y), 5)
        pygame.draw.circle(base, BLACK, (eye_x, eye_y), 2)
        # Energy core
        core_r = 8 + int(2 * math.sin(self.anim_t * 3.0))
        pygame.draw.circle(base, (80, 255, 180), (PLAYER_W//2, PLAYER_H//2 + 6), core_r)
        # Shield overlay
        if self.shield > 0 or self.invincible > 0:
            aura = Surface((PLAYER_W+22, PLAYER_H+22), pygame.SRCALPHA)
            pygame.draw.ellipse(aura, (120, 220, 255, 70), aura.get_rect())
            base.blit(aura, (-11, -11))
        # Jet flame overlay
        if self.jet > 0:
            pygame.draw.polygon(base, ORANGE, [(PLAYER_W//2 - 4, PLAYER_H - 2),
                                               (PLAYER_W//2 + 4, PLAYER_H - 2),
                                               (PLAYER_W//2, PLAYER_H + 10)])
        self.image.blit(base, (0, 0))

    def update(self, keys, touch_x: Optional[int] = None):
        self.prev_rect = self.rect.copy()
        self.anim_t += 1.0 / FPS

        # Horizontal control: touch -> left/right by screen half, else keys
        move_speed = PLAYER_MOVE_SPEED
        if touch_x is not None:
            if touch_x < WIDTH // 2:
                self.vel.x = -move_speed
                self.facing = -1
            else:
                self.vel.x = move_speed
                self.facing = 1
        else:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.vel.x = -move_speed
                self.facing = -1
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.vel.x = move_speed
                self.facing = 1
            else:
                self.vel.x = 0.0

        # Apply horizontal + wrap
        self.rect.x += int(self.vel.x)
        if self.rect.right < 0:
            self.rect.left = WIDTH
        elif self.rect.left > WIDTH:
            self.rect.right = 0

        # Vertical: jet overrides gravity
        if self.jet > 0:
            self.vel.y = -9.5
            self.jet -= 1
        else:
            self.vel.y += GRAVITY

        self.rect.y += int(self.vel.y)

        # Energy drain
        drain = PASSIVE_ENERGY_DRAIN * (0.6 if self.drain_slow > 0 else 1.0)
        self.energy = clamp(self.energy - drain, 0.0, 100.0)

        # Timers
        if self.drain_slow > 0: self.drain_slow -= 1
        if self.shield > 0: self.shield -= 1
        if self.invincible > 0: self.invincible -= 1

        self.draw()

    def bounce(self, power=None, speed_factor: float = 1.0):
        base = PLAYER_JUMP_VEL * speed_factor
        self.vel.y = base if power is None else power

    def take_enemy_hit(self):
        if self.invincible > 0:
            return
        if self.shield > 0:
            self.shield = 0
            return
        self.energy = clamp(self.energy - ENEMY_HIT_ENERGY_LOSS, 0.0, 100.0)
        if self.vel.y < -8:
            self.vel.y = -8

    def mark_safe_platform(self, platform: 'Platform'):
        self.last_safe_platform = platform

    def revive_on_safe(self):
        y = HEIGHT//2
        if self.last_safe_platform and self.last_safe_platform.alive():
            y = self.last_safe_platform.rect.top - PLAYER_H//2 - 2
        self.rect.center = (WIDTH//2, y)
        self.vel.update(0, 0)
        self.energy = max(55.0, self.energy)
        self.invincible = DUR_INVINCIBLE

class Platform(pygame.sprite.Sprite):
    def __init__(self, x, y, kind=P_NORMAL):
        super().__init__()
        self.kind = kind
        self.image = Surface((PLATFORM_W, PLATFORM_H), pygame.SRCALPHA)
        self.rect = self.image.get_rect(topleft=(x, y))
        self.active = True
        self.fade = 1.0
        self.phase = random.random() * 10.0
        self._start_x = x
        self.draw()

    def set_start_x(self, x):
        self._start_x = x

    def draw(self):
        self.image.fill((0, 0, 0, 0))
        color = GREEN
        glow = GREEN_SOFT
        if self.kind == P_NORMAL:
            color, glow = (90, 240, 180), (120, 255, 200)
        elif self.kind == P_SOLAR:
            color, glow = (255, 230, 90), (255, 250, 180)
        elif self.kind == P_WIND:
            color, glow = (140, 230, 255), (200, 245, 255)
        elif self.kind == P_HYDRO:
            color, glow = (80, 180, 255), (160, 220, 255)
        elif self.kind == P_MOVING:
            color, glow = (180, 255, 140), (220, 255, 200)
        elif self.kind == P_BREAKING:
            color, glow = (255, 140, 140), (255, 190, 190)
        elif self.kind == P_DISAPPEARING:
            color, glow = (200, 140, 255), (230, 200, 255)

        a = int(255 * self.fade)
        r = Rect(0, 0, PLATFORM_W, PLATFORM_H)
        pygame.draw.rect(self.image, (*color, a), r, border_radius=8)
        neon_rect(self.image, r, color, glow, glow_strength=5, border=2, radius=8)

        # small icon type
        ic = BLACK
        if self.kind == P_SOLAR:
            pygame.draw.rect(self.image, ic, (8, 4, 22, 8), border_radius=2)
            pygame.draw.line(self.image, ic, (8, 14), (30, 14), 2)
        elif self.kind == P_WIND:
            pygame.draw.line(self.image, ic, (10, 8), (30, 8), 2)
            pygame.draw.circle(self.image, ic, (20, 8), 4, 1)
        elif self.kind == P_HYDRO:
            pygame.draw.circle(self.image, ic, (15, 8), 5, 1)
            pygame.draw.rect(self.image, ic, (12, 5, 6, 6))
        elif self.kind == P_MOVING:
            pygame.draw.polygon(self.image, ic, [(6,8), (12,4), (12,12)])
            pygame.draw.polygon(self.image, ic, [(98,8), (92,4), (92,12)])
        elif self.kind == P_BREAKING:
            pygame.draw.line(self.image, ic, (8, 3), (24, 12), 2)
            pygame.draw.line(self.image, ic, (24, 3), (8, 12), 2)
        elif self.kind == P_DISAPPEARING:
            for i in range(0, PLATFORM_W, 8):
                if (i//8) % 2 == 0:
                    pygame.draw.line(self.image, ic, (i, 14), (i+4, 14), 2)

    def update(self, moving_speed_factor: float = 1.0):
        # Moving platforms oscillate horizontally (scaled with difficulty)
        if self.kind == P_MOVING and self.active:
            self.phase += 0.02 * moving_speed_factor
            offset = int(math.sin(self.phase) * 80)
            self.rect.x = self._start_x + offset

class Enemy(pygame.sprite.Sprite):
    def __init__(self, x, y, kind=E_BULB):
        super().__init__()
        self.kind = kind
        self.image = Surface((36, 36), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.phase = random.random() * 6.28
        self.draw()

    def draw(self):
        self.image.fill((0,0,0,0))
        if self.kind == E_BULB:
            pygame.draw.ellipse(self.image, (255, 230, 150), (4,2,28,24))
            pygame.draw.rect(self.image, (150, 150, 150), (10, 24, 16, 8))
        elif self.kind == E_PIPE:
            pygame.draw.rect(self.image, (140, 200, 240), (6, 8, 24, 10))
            pygame.draw.rect(self.image, (100, 160, 200), (6, 18, 24, 6))
            pygame.draw.circle(self.image, (120, 180, 220), (30, 15), 3)
        elif self.kind == E_SMOKE:
            for i in range(5):
                r = 4 + i*3
                alpha = 170 - i*30
                pygame.draw.circle(self.image, (150,150,150,alpha), (8+i*5, 30-i*5), r)
        elif self.kind == E_CHASER:
            pygame.draw.circle(self.image, (255, 180, 120), (18,18), 16)
            pygame.draw.circle(self.image, (60, 30, 0), (12,14), 4)
            pygame.draw.circle(self.image, (60, 30, 0), (24,14), 4)

    def update(self, player: 'Player', enemy_speed_factor: float = 1.0):
        self.phase += ENEMY_SINE_SPEED * enemy_speed_factor
        if self.kind == E_BULB:
            self.rect.x += int(math.sin(self.phase) * ENEMY_PATROL_SPEED * 1.4 * enemy_speed_factor)
        elif self.kind == E_PIPE:
            self.rect.y += int(math.sin(self.phase*0.9) * 1.0 * enemy_speed_factor)
        elif self.kind == E_SMOKE:
            self.rect.y += int((-0.5 + math.sin(self.phase) * 0.25) * enemy_speed_factor)
        elif self.kind == E_CHASER:
            if abs(player.rect.centerx - self.rect.centerx) > 4:
                direction = 1 if player.rect.centerx > self.rect.centerx else -1
                self.rect.x += int(direction * ENEMY_CHASER_SPEED * enemy_speed_factor)
            self.rect.y += int(math.sin(self.phase) * 0.6 * enemy_speed_factor)

class Bonus(pygame.sprite.Sprite):
    def __init__(self, x, y, kind=B_CELL):
        super().__init__()
        self.kind = kind
        self.image = Surface((28, 28), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.phase = random.random() * 6.28
        self.draw()

    def draw(self):
        self.image.fill((0,0,0,0))
        if self.kind == B_CELL:
            pygame.draw.circle(self.image, (255, 250, 120), (14,14), 12)
            pygame.draw.circle(self.image, (255, 255, 200), (14,14), 8)
        elif self.kind == B_LED:
            pygame.draw.rect(self.image, (200, 255, 180), (5,7,18,12), border_radius=4)
            pygame.draw.rect(self.image, (140, 220, 160), (5, 17, 18, 6), border_radius=2)
        elif self.kind == B_SHIELD:
            pygame.draw.circle(self.image, (160, 220, 255), (14, 14), 12, 2)
        elif self.kind == B_JET:
            pygame.draw.rect(self.image, (140, 100, 240), (6,6,16,16), border_radius=4)
            pygame.draw.polygon(self.image, ORANGE, [(8,22),(20,22),(14,28)])
        elif self.kind == B_SPRING:
            pygame.draw.rect(self.image, (180, 180, 180), (4, 10, 20, 8), border_radius=3)
            for i in range(5):
                pygame.draw.line(self.image, (100,100,100), (6+i*4,10), (6+i*4,18), 2)

    def update(self):
        self.phase += 0.06
        self.rect.y += int(math.sin(self.phase) * 0.5)

# -----------------------------------------------------------------------------
# Quiz (30 questions)
# -----------------------------------------------------------------------------
QUIZ: List[Dict] = [
    {"q":"Какой источник света экономичнее?","opts":["Лампа накаливания","Галогенная","LED-лампа","Неон"],"ans":2,"hint":"LED тратит меньше и служит дольше."},
    {"q":"Что снизит теплопотери дома?","opts":["Щели в окнах","Теплоизоляция стен","Тонкое стекло","Приоткрытая дверь"],"ans":1,"hint":"Утепление — меньше затрат на отопление."},
    {"q":"Как экономнее съездить в ближайший магазин?","opts":["Автомобиль","Такси","Электровелосипед","Самолёт"],"ans":2,"hint":"Короткие поездки — сила велосипеда."},
    {"q":"Что сокращает расход воды?","opts":["Аэратор","Протечка","Полная ванна","Снятый душ"],"ans":0,"hint":"Аэратор смешивает воду с воздухом."},
    {"q":"Что делать с зарядкой после зарядки?","opts":["Оставить в розетке","Вытащить","Спрятать под подушку","Подключить снова"],"ans":1,"hint":"Вынимай — экономия и безопасность."},
    {"q":"Какой режим TV экономичнее?","opts":["Демо","Эко-режим","Макс. яркость","Динамический"],"ans":1,"hint":"Эко-режим снижает яркость и расход."},
    {"q":"Как лучше стирать?","opts":["Маленькие загрузки","Полная загрузка","Всегда горячая вода","По одной вещи"],"ans":1,"hint":"Полная загрузка и низкие температуры — выгодно."},
    {"q":"Ноутбук ночью лучше…","opts":["Оставить включённым","Пауза","Выключить","Макс. яркость"],"ans":2,"hint":"Выключай, если не нужен длительно."},
    {"q":"Как уменьшить углеродный след?","opts":["Больше летать","Меньше есть мяса","Покупать новинки","Игнорировать отходы"],"ans":1,"hint":"Растительная пища экологичнее."},
    {"q":"Что снижает потребление электроэнергии?","opts":["Оставить свет","Выключить свет","Увеличить яркость","Больше ламп"],"ans":1,"hint":"Выключай, когда не нужно."},
    {"q":"Как лучше проветривать комнату?","opts":["Щёлками долго","Широко и недолго","Постоянно открыто","Не проветривать"],"ans":1,"hint":"Кратковременное интенсивное проветривание."},
    {"q":"Как экономить воду в душе?","opts":["Заполнить ванну","Снять насадку","Короткий душ","Долго мыться"],"ans":2,"hint":"Короткий душ экономит воду и энергию."},
    {"q":"Что уменьшает энергопотребление ПК?","opts":["Макс. яркость","Режим сна","Фоновая игра","Скринсейвер"],"ans":1,"hint":"Режим сна экономит больше всего."},
    {"q":"Как продлить срок службы батареи?","opts":["Полная разрядка","Частичные заряды","Перегрев","Не заряжать"],"ans":1,"hint":"Небольшие подзарядки полезнее."},
    {"q":"Что уменьшает шум от техники?","opts":["Подложка","Пыль","Высокая скорость","Перегруз"],"ans":0,"hint":"Амортизация снижает шум и вибрации."},
    {"q":"Как снизить расход топлива в авто?","opts":["Резкие старты","Плавное ускорение","Высокие обороты","Долгая стоянка"],"ans":1,"hint":"Плавное движение экономит топливо."},
    {"q":"Что поможет снизить расход газа для отопления?","opts":["Открытая дверь","Утепление пола","Тонкие шторы","Окна на проветривании"],"ans":1,"hint":"Утепление перекрытий работает."},
    {"q":"Как уменьшить количество мусора?","opts":["Сжигать дома","Рециклинг","Не сортировать","Выбрасывать всё"],"ans":1,"hint":"Сортируй и сдавай отходы."},
    {"q":"Что снижает энергопотребление холодильника?","opts":["Часто открывать","Чистить вентиляцию","Ставить у батареи","Нагружать дверцу"],"ans":1,"hint":"Чистая вентиляция повышает эффективность."},
    {"q":"Как сократить расходы на электроприборы?","opts":["Оставлять в розетке","Всегда включать","Вынимать вилки","Увеличить мощность"],"ans":2,"hint":"Отключай из сети неиспользуемые устройства."},
    {"q":"Что экономит электричество ночью?","opts":["Выключать приборы","Макс. яркость","Оставить зарядки","Включить всё"],"ans":0,"hint":"Выключай полностью."},
    {"q":"Как снизить расход воды при поливе?","opts":["Лить из ведра","Капельный полив","Открытый шланг","Полдень в жару"],"ans":1,"hint":"Капельный полив точный и экономный."},
    {"q":"Что уменьшает тепловые мосты?","opts":["Одно стекло","Двойное остекление","Щели","Без изоляции"],"ans":1,"hint":"Двойные стеклопакеты — тепло."},
    {"q":"Как сократить потребление бумаги?","opts":["Печать обеих сторон","Одна сторона","Цветная печать","Больше страниц"],"ans":0,"hint":"Дуплекс — меньше бумаги."},
    {"q":"Как экономить бензин?","opts":["Резко разгоняться","Плавно тормозить","Дрифтить","Долго греть"],"ans":1,"hint":"Плавность — ключ к экономии."},
    {"q":"Что снизит потребление энергии дома?","opts":["Утечки воздуха","Утеплитель","Снять уплотнители","Не закрывать окна"],"ans":1,"hint":"Утепляй стены и стыки."},
    {"q":"Как продлить срок службы лампы?","opts":["Часто щёлкать","Плавный пуск","Перегрев","Макс. яркость"],"ans":1,"hint":"Плавный пуск снижает нагрузку."},
    {"q":"Что экономит энергию при готовке?","opts":["Готовить под крышкой","Открытая крышка","Маленькая посуда","Макс. нагрев"],"ans":0,"hint":"Крышка сохраняет тепло."},
    {"q":"Как снизить энергозатраты в офисе?","opts":["Оставлять ПК","Таймеры/автовыключение","Макс. подсветка","Работать ночью"],"ans":1,"hint":"Используй автоматизацию выключения."},
    {"q":"Что уменьшает расход стиральной машины?","opts":["Высокая температура","Полупустая загрузка","Частые стирки","Низкая температура"],"ans":3,"hint":"Низкая температура экономит энергию."},
]

class QuizUI:
    def __init__(self):
        self.selected = 0
        self.cur: Optional[Dict] = None
        self.feedback = ""
        self.feedback_timer = 0

    def pick(self):
        self.selected = 0
        self.cur = random.choice(QUIZ)
        self.feedback = ""
        self.feedback_timer = 0

    def handle(self, event):
        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_UP, pygame.K_w):
                self.selected = (self.selected - 1) % 4
            elif event.key in (pygame.K_DOWN, pygame.K_s):
                self.selected = (self.selected + 1) % 4
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE):
                correct = (self.selected == self.cur["ans"])
                self.feedback = "Верно! +1 жизнь" if correct else "Увы, неверно."
                self.feedback_timer = int(0.9 * FPS)
                return True, correct
        return False, False

    def update(self):
        if self.feedback_timer > 0:
            self.feedback_timer -= 1

    def draw(self, screen):
        # Dim background
        overlay = Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 20, 200))
        screen.blit(overlay, (0, 0))
        # Panel
        panel = Surface((int(WIDTH*0.9), int(HEIGHT*0.7)), pygame.SRCALPHA)
        pygame.draw.rect(panel, (22, 24, 30, 235), panel.get_rect(), border_radius=12)
        neon_rect(panel, panel.get_rect(), NEON, NEON, 12, 2, 12)
        px = int(WIDTH*0.05)
        py = int(HEIGHT*0.15)
        screen.blit(panel, (px, py))
        # Title
        t = FONT_TITLE.render("Викторина", True, WHITE)
        screen.blit(t, (px + 24, py + 12))
        # Question
        q = self.cur["q"]
        lines = wrap_text(q, FONT_UI, int(WIDTH*0.8))
        yy = py + 80
        for line in lines:
            txt = FONT_UI.render(line, True, GRAY_LIGHT)
            screen.blit(txt, (px + 24, yy))
            yy += 34
        yy += 10
        # Options
        for i, opt in enumerate(self.cur["opts"]):
            pref = "→ " if i == self.selected else "  "
            col = NEON if i == self.selected else WHITE
            txt = FONT_UI.render(pref + opt, True, col)
            screen.blit(txt, (px + 32, yy))
            yy += 38
        # Hint / Feedback
        if self.feedback_timer > 0:
            fb = FONT_SMALL.render(self.feedback, True, (100,255,140) if "Верно" in self.feedback else RED)
            screen.blit(fb, (px + 24, py + panel.get_height() - 48))
        else:
            hint = FONT_TINY.render("Подсказка: " + self.cur["hint"], True, GRAY_LIGHT)
            screen.blit(hint, (px + 24, py + panel.get_height() - 48))
        info = FONT_SMALL.render("↑/↓ — выбрать, ENTER — подтвердить", True, GRAY_LIGHT)
        screen.blit(info, (WIDTH//2 - info.get_width()//2, int(HEIGHT*0.88)))

def wrap_text(text, font, width):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if font.size(test)[0] <= width:
            cur = test
        else:
            if cur: lines.append(cur)
            cur = w
    if cur: lines.append(cur)
    return lines

# -----------------------------------------------------------------------------
# World Generation (endless) + difficulty progression
# -----------------------------------------------------------------------------
class World:
    def __init__(self):
        self.spawn_y = HEIGHT - 120
        self.rng = random.Random()
        self.rng.seed()
        self.score = 0  # will be synced from Game

    def progress_factor(self) -> float:
        # 0.0 at score=0, 1.0 at score>=4000
        return clamp(self.score / 4000.0, 0.0, 1.0)

    def speed_factor(self) -> float:
        # scales movement/jump/enemy speeds
        return 1.0 + 0.5 * self.progress_factor()

    def choose_platform_type(self) -> str:
        p = self.progress_factor()
        r = self.rng.random()
        # Weighted selection shifting towards tricky with progress
        if r < 0.24 - 0.08*p:
            return P_SOLAR
        elif r < 0.44 - 0.08*p:
            return P_WIND
        elif r < 0.60 - 0.06*p:
            return P_HYDRO
        elif r < 0.78 - 0.08*p:
            return P_NORMAL
        elif r < 0.88:
            return P_MOVING
        elif r < 0.94:
            return P_DISAPPEARING
        else:
            return P_BREAKING

    def enemy_spawn_chance(self) -> float:
        p = self.progress_factor()
        return ENEMY_BASE_SPAWN_CHANCE + p * 0.18

    def choose_enemy(self) -> Optional[str]:
        if self.rng.random() < self.enemy_spawn_chance():
            r = self.rng.random()
            if r < 0.40:
                return E_BULB
            elif r < 0.70:
                return E_PIPE
            elif r < 0.85:
                return E_SMOKE
            else:
                return E_CHASER
        return None

    def choose_bonus(self) -> Optional[str]:
        r = self.rng.random()
        if r < BONUS_CHANCE_BASE:
            # Weighted bonus: early more cells, later more jets/shields
            p = self.progress_factor()
            rr = self.rng.random()
            if rr < 0.40 - 0.15*p: return B_CELL
            if rr < 0.60: return B_LED
            if rr < 0.80: return B_SHIELD
            if rr < 0.93: return B_JET
            return B_SPRING
        return None

# -----------------------------------------------------------------------------
# HUD
# -----------------------------------------------------------------------------
class HUD:
    def draw(self, screen, player: Player, score: int, high: int):
        display_score = int(score)
        display_high = int(high)

        # Top bar
        bar = Rect(0, 0, WIDTH, 76)
        pygame.draw.rect(screen, (15, 18, 24), bar)
        neon_rect(screen, bar, (30, 34, 44), (30, 34, 44), 6, 2, 0)

        # Score and high score
        sc = FONT_UI.render(f"Счёт: {display_score}", True, WHITE)
        screen.blit(sc, (16, 12))
        hs = FONT_SMALL.render(f"Рекорд: {display_high}", True, GRAY_LIGHT)
        screen.blit(hs, (16, 44))

        # Energy bar
        x = WIDTH - 280
        w = 260
        pct = player.energy / 100.0
        col = GREEN if pct > 0.5 else (YELLOW if pct > 0.25 else RED)
        pygame.draw.rect(screen, (40,40,40), (x, 18, w, 18), border_radius=6)
        ww = int(w * clamp(pct, 0.0, 1.0))
        if ww > 0:
            pygame.draw.rect(screen, col, (x, 18, ww, 18), border_radius=6)
        neon_rect(screen, Rect(x, 18, w, 18), col, col, 4, 2, 6)

        # Lives and effects
        lives = FONT_UI.render(f"Жизни: {player.lives}", True, WHITE)
        screen.blit(lives, (x, 44))
        fx_x = x
        if player.drain_slow > 0:
            screen.blit(FONT_SMALL.render("LED", True, (140,255,160)), (fx_x, 66)); fx_x += 60
        if player.shield > 0:
            screen.blit(FONT_SMALL.render("ЩИТ", True, CYAN), (fx_x, 66)); fx_x += 60
        if player.jet > 0:
            screen.blit(FONT_SMALL.render("РАНЕЦ", True, PURPLE), (fx_x, 66))

# -----------------------------------------------------------------------------
# Game core
# -----------------------------------------------------------------------------
class Game:
    def __init__(self):
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT))
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.state = STATE_MENU
        self.hud = HUD()
        self.quiz = QuizUI()
        self.world = World()

        self.bg_top = (15, 20, 35)
        self.bg_bottom = (8, 10, 16)
        self.layers = [
            ParallaxLayer(0.25, (70, 130, 160), 42, (1, 2)),
            ParallaxLayer(0.50, (110, 180, 210), 28, (1, 3)),
            ParallaxLayer(0.80, (160, 220, 240), 18, (2, 3)),
        ]

        # Groups
        self.all_sprites = pygame.sprite.Group()
        self.platforms = pygame.sprite.Group()
        self.enemies = pygame.sprite.Group()
        self.bonuses = pygame.sprite.Group()

        self.player: Optional[Player] = None
        self.high_score = load_scores().get("high_score", 0)
        self.score = 0

        self.menu_t = 0.0
        self.ascended_px = 0
        self._touch_x: Optional[int] = None  # for Android touch
        self.init_run()

    def init_run(self):
        self.all_sprites.empty()
        self.platforms.empty()
        self.enemies.empty()
        self.bonuses.empty()
        self.world = World()
        self.score = 0
        self.ascended_px = 0
        self._touch_x = None

        # Player
        self.player = Player(WIDTH//2, HEIGHT - 140, lives=2)
        self.all_sprites.add(self.player)

        # Initial platforms
        base_y = HEIGHT - 80
        prev_x = self.player.rect.centerx - PLATFORM_W//2
        for i in range(10):
            kind = P_NORMAL if i > 0 else P_SOLAR
            x = clamp(prev_x + random.randint(-90, 90), SPAWN_X_MARGIN, WIDTH - PLATFORM_W - SPAWN_X_MARGIN)
            y = base_y - i * 70
            p = Platform(x, y, kind)
            p.set_start_x(p.rect.x)
            self.platforms.add(p); self.all_sprites.add(p)
            self.world.spawn_y = y
            prev_x = x

        # Safety platform under player
        p = Platform(self.player.rect.centerx - PLATFORM_W//2, self.player.rect.bottom + 60, P_NORMAL)
        p.set_start_x(p.rect.x)
        self.platforms.add(p); self.all_sprites.add(p)

    # ---------------- Events ----------------
    def handle_events(self):
        keys = pygame.key.get_pressed()
        self._touch_x = None
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.quit()

            # Touch/mouse for Android
            if ev.type == pygame.MOUSEBUTTONDOWN:
                self._touch_x = ev.pos[0]
            elif ev.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[0]:
                self._touch_x = ev.pos[0]

            if self.state == STATE_MENU:
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.state = STATE_PLAY
                    elif ev.key == pygame.K_ESCAPE:
                        self.quit()
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    # tap to start on mobile
                    self.state = STATE_PLAY

            elif self.state == STATE_PLAY:
                if ev.type == pygame.KEYDOWN:
                    if ev.key == pygame.K_ESCAPE:
                        self.state = STATE_PAUSE

            elif self.state == STATE_PAUSE:
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_ESCAPE, pygame.K_p, pygame.K_SPACE):
                        self.state = STATE_PLAY
                    elif ev.key == pygame.K_q:
                        self.state = STATE_MENU
                        self.init_run()
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    # tap to unpause
                    self.state = STATE_PLAY

            elif self.state == STATE_QUIZ:
                answered, correct = self.quiz.handle(ev)
                if answered:
                    pass

            elif self.state == STATE_GAMEOVER:
                if ev.type == pygame.KEYDOWN:
                    if ev.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.state = STATE_MENU
                        self.init_run()
                elif ev.type == pygame.MOUSEBUTTONDOWN:
                    self.state = STATE_MENU
                    self.init_run()
        return keys

    # ---------------- Spawning ----------------
    def spawn_next(self):
        # Чем выше счёт, тем меньше расстояние между платформами
        speed_factor = self.world.speed_factor()
        while self.world.spawn_y > -HEIGHT:
            gap = random.randint(
                int(SPAWN_MIN_GAP / speed_factor),
                int(SPAWN_MAX_GAP / speed_factor)
            )
            self.world.spawn_y -= gap
            kind = self.world.choose_platform_type()
            x = random.randint(SPAWN_X_MARGIN, WIDTH - PLATFORM_W - SPAWN_X_MARGIN)

            if self.player:
                px = self.player.rect.centerx - PLATFORM_W // 2
                x = clamp(int(lerp(x, px, 0.35)), SPAWN_X_MARGIN, WIDTH - PLATFORM_W - SPAWN_X_MARGIN)

            p = Platform(x, int(self.world.spawn_y), kind)
            p.set_start_x(p.rect.x)
            self.platforms.add(p)
            self.all_sprites.add(p)

            # Пружина на платформе
            if kind in (P_NORMAL, P_MOVING) and random.random() < 0.10:
                b = Bonus(p.rect.centerx, p.rect.top - 16, B_SPRING)
                self.bonuses.add(b)
                self.all_sprites.add(b)

            # Враг
            ek = self.world.choose_enemy()
            if ek:
                e = Enemy(p.rect.centerx + random.randint(-70, 70), p.rect.top - 28, ek)
                self.enemies.add(e)
                self.all_sprites.add(e)

            # Бонус
            bk = self.world.choose_bonus()
            if bk:
                by = p.rect.top - random.randint(20, 40)
                b = Bonus(p.rect.centerx + random.randint(-28, 28), by, bk)
                self.bonuses.add(b)
                self.all_sprites.add(b)

        # Ограничение количества платформ
        if len(self.platforms) > MAX_PLATFORMS_ON_SCREEN:
            low = sorted(list(self.platforms), key=lambda s: s.rect.top, reverse=True)
            for s in low[MAX_PLATFORMS_ON_SCREEN:]:
                s.kill()

    # ---------------- Collisions ----------------
    def resolve_platform_collisions(self, speed_factor: float):
        # Only land if falling and was above last frame
        if self.player.vel.y <= 0:
            return
        for p in self.platforms:
            if not p.active:
                continue
            if self.player.prev_rect.bottom <= p.rect.top and self.player.rect.colliderect(p.rect):
                # Land
                self.player.rect.bottom = p.rect.top
                self.player.bounce(speed_factor=speed_factor)
                self.player.mark_safe_platform(p)
                self.handle_platform_effect(p)
                break

        # Disappearing platforms fade out
        for p in list(self.platforms):
            if p.kind == P_DISAPPEARING and not p.active:
                p.fade = max(0.0, p.fade - 0.06)
                p.draw()
                if p.fade <= 0.0:
                    p.kill()

    def handle_platform_effect(self, p: Platform):
        if p.kind == P_SOLAR:
            self.player.energy = clamp(self.player.energy + ENERGY_FROM_SOLAR, 0, 100)
        elif p.kind == P_WIND:
            self.player.energy = clamp(self.player.energy + ENERGY_FROM_WIND, 0, 100)
        elif p.kind == P_HYDRO:
            self.player.energy = clamp(self.player.energy + ENERGY_FROM_HYDRO, 0, 100)
            self.player.vel.y = PLAYER_JUMP_VEL * 1.07
        elif p.kind == P_BREAKING:
            p.active = False
            p.fade = 0.0
            p.draw()
        elif p.kind == P_DISAPPEARING:
            p.active = False
            p.fade = 0.85
            p.draw()

    def resolve_enemy_collisions(self, enemy_speed_factor: float):
        for e in list(self.enemies):
            e.update(self.player, enemy_speed_factor=enemy_speed_factor)
            if self.player.rect.colliderect(e.rect):
                self.player.take_enemy_hit()
                e.rect.x += random.choice([-10, 10])  # small separation
                if self.player.energy <= 0:
                    self.trigger_quiz(reason="energy")

    def resolve_bonus_pickups(self):
        for b in list(self.bonuses):
            b.update()
            if self.player.rect.colliderect(b.rect):
                self.apply_bonus(b)
                b.kill()

    def apply_bonus(self, b: Bonus):
        if b.kind == B_CELL:
            self.player.energy = clamp(self.player.energy + ENERGY_FROM_CELL, 0, 100)
        elif b.kind == B_LED:
            self.player.drain_slow = DUR_LED
        elif b.kind == B_SHIELD:
            self.player.shield = DUR_SHIELD
        elif b.kind == B_JET:
            self.player.jet = DUR_JET
        elif b.kind == B_SPRING:
            # emulate spring: strong instant jump
            self.player.vel.y = PLAYER_JUMP_VEL * 1.55

    # ---------------- Quiz / Death / Continue ----------------
    def trigger_quiz(self, reason="fall"):
        self.player.lives -= 1
        if self.player.lives < 0:
            self.game_over()
            return
        self.quiz.pick()
        self.state = STATE_QUIZ

    def resolve_quiz_result(self, correct: bool):
        if correct:
            self.player.lives += 1  # refund +1
            self.player.revive_on_safe()
            self.state = STATE_PLAY
        else:
            self.game_over()

    def game_over(self):
        self.state = STATE_GAMEOVER
        self.score = max(self.score, int(self.ascended_px * 0.06))
        current_score = int(self.score)
        if current_score > self.high_score:
            self.high_score = current_score
            save_scores({"high_score": self.high_score})

    # ---------------- Update ----------------
    def update(self, keys):
        dt = self.clock.get_time() / 1000.0
        for layer in self.layers:
            layer.update(0)

        if self.state == STATE_MENU:
            self.menu_t += dt
            return
        if self.state == STATE_PAUSE:
            return
        if self.state == STATE_QUIZ:
            self.quiz.update()
            if self.quiz.feedback and self.quiz.feedback_timer == 0:
                self.resolve_quiz_result("Верно" in self.quiz.feedback)
            return
        if self.state == STATE_GAMEOVER:
            return

        # --- Ускорение сложности ---
        self.world.score = self.score
        speed_factor = self.world.speed_factor()

        # Увеличиваем скорость игрока и гравитацию
        self.player.vel.y += GRAVITY * (speed_factor - 1.0)
        PLAYER_MOVE_SPEED_CURRENT = PLAYER_MOVE_SPEED * speed_factor

        # Обновляем движущиеся платформы
        for p in self.platforms:
            p.update(moving_speed_factor=speed_factor)

        # Обновляем игрока с учётом ускорения
        self.player.update(keys, touch_x=self._touch_x)
        if self._touch_x is not None:
            if self._touch_x < WIDTH // 2:
                self.player.vel.x = -PLAYER_MOVE_SPEED_CURRENT
            else:
                self.player.vel.x = PLAYER_MOVE_SPEED_CURRENT
        else:
            if keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.player.vel.x = -PLAYER_MOVE_SPEED_CURRENT
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.player.vel.x = PLAYER_MOVE_SPEED_CURRENT

        # Камера
        if self.player.rect.top <= SCROLL_TRIGGER_Y:
            dy = SCROLL_TRIGGER_Y - self.player.rect.top
            self.player.rect.top = SCROLL_TRIGGER_Y
            for g in (self.platforms, self.enemies, self.bonuses):
                for s in g:
                    s.rect.y += dy
            for layer in self.layers:
                layer.update(dy * 0.05)
            self.world.spawn_y += dy
            self.ascended_px += dy

        # Спавн
        self.spawn_next()

        # Коллизии
        self.resolve_platform_collisions(speed_factor=speed_factor)
        self.resolve_enemy_collisions(enemy_speed_factor=speed_factor)
        self.resolve_bonus_pickups()

        # Очистка
        for group in (self.platforms, self.enemies, self.bonuses):
            for s in list(group):
                if s.rect.top > HEIGHT + 120:
                    s.kill()

        # Падение
        if self.player.rect.top > HEIGHT + 60:
            self.player.energy = 0.0
            self.trigger_quiz(reason="fall")

        # Счёт
        self.score = max(self.score, int(self.ascended_px * 0.06))
        self.player.score = self.score
        if self.score > self.high_score:
            self.high_score = self.score
            save_scores({"high_score": self.high_score})

        # Сброс касания
        self._touch_x = None

    # ---------------- Draw ----------------
    def draw(self):
        gradient_bg(self.screen, self.bg_top, self.bg_bottom)
        for layer in self.layers:
            layer.draw(self.screen)

        if self.state == STATE_MENU:
            self.draw_menu()
        else:
            # World
            for p in self.platforms:
                self.screen.blit(p.image, p.rect)
            for b in self.bonuses:
                self.screen.blit(b.image, b.rect)
            for e in self.enemies:
                self.screen.blit(e.image, e.rect)
            # Player
            self.screen.blit(self.player.image, self.player.rect)

            # HUD
            self.hud.draw(self.screen, self.player, self.score, self.high_score)

            if self.state == STATE_PAUSE:
                self.draw_pause()
            elif self.state == STATE_QUIZ:
                self.quiz.draw(self.screen)
            elif self.state == STATE_GAMEOVER:
                self.draw_gameover()

        pygame.display.flip()

    def draw_menu(self):
        title = FONT_TITLE.render("Eco Jump", True, WHITE)
        sub = FONT_UI.render("Сохрани энергию и поднимайся всё выше!", True, GRAY_LIGHT)
        press = FONT_UI.render("Нажми ПРОБЕЛ/ENTER или коснись экрана", True, NEON)
        hs = FONT_SMALL.render(f"Рекорд: {self.high_score}", True, GRAY_LIGHT)

        # Рисуем элементы по центру
        self.screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 180))
        self.screen.blit(sub, (WIDTH // 2 - sub.get_width() // 2, 244))
        self.screen.blit(press, (WIDTH // 2 - press.get_width() // 2, 302))
        self.screen.blit(hs, (WIDTH // 2 - hs.get_width() // 2, 340))

    def draw_pause(self):
        overlay = Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))
        t = FONT_TITLE.render("Пауза", True, WHITE)
        s1 = FONT_UI.render("ESC/P/SPACE — продолжить", True, GRAY_LIGHT)
        s2 = FONT_UI.render("Q — меню", True, GRAY_LIGHT)
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 90))
        self.screen.blit(s1, (WIDTH // 2 - s1.get_width() // 2, HEIGHT // 2))
        self.screen.blit(s2, (WIDTH // 2 - s2.get_width() // 2, HEIGHT // 2 + 36))

    def draw_gameover(self):
        overlay = Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 210))
        self.screen.blit(overlay, (0, 0))
        t = FONT_TITLE.render("Игра окончена", True, WHITE)
        sc = FONT_UI.render(f"Счёт: {self.score}", True, GRAY_LIGHT)
        hs = FONT_UI.render(f"Рекорд: {self.high_score}", True, GRAY_LIGHT)
        prm = FONT_UI.render("ENTER/SPACE — меню", True, NEON)
        self.screen.blit(t, (WIDTH // 2 - t.get_width() // 2, HEIGHT // 2 - 110))
        self.screen.blit(sc, (WIDTH // 2 - sc.get_width() // 2, HEIGHT // 2 - 40))
        self.screen.blit(hs, (WIDTH // 2 - hs.get_width() // 2, HEIGHT // 2 - 4))
        self.screen.blit(prm, (WIDTH // 2 - prm.get_width() // 2, HEIGHT // 2 + 56))

    def run(self):
        while True:
            self.clock.tick(FPS)
            keys = self.handle_events()
            self.update(keys)
            self.draw()

    def quit(self):
        pygame.quit()
        sys.exit()


if __name__ == "__main__":
    # Cooperative async launcher for pygbag without changing game logic/UI.
    if sys.platform == "emscripten":
        import asyncio
        async def web_main():
            game = Game()
            while True:
                game.clock.tick(FPS)
                keys = game.handle_events()
                game.update(keys)
                game.draw()
                await asyncio.sleep(0)
        asyncio.run(web_main())
    else:
        Game().run()