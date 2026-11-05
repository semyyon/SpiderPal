# -*- coding: utf-8 -*-
"""
Паучок на паутине — настольная игрушка для Windows.

Паук (чиби с большой головой или человеческого телосложения) живёт поверх экрана рядом с курсором:
в пределах монитора — ползёт, на другой монитор — летит махами на паутине с трюками, при паузе садится
на кромку активного окна, в покое висит на паутине; 5 с — спит, 20 с — заматывает курсор в кокон,
10 мин — мем «трое пауков». Плюс время суток (пижама, кофе по утрам), праздники, головокружение от тряски,
двойник раз в 5 минут, реплики в пузырях, головные уборы.
Фан-арт: персонаж целиком нарисован кодом (art.py), чужих картинок нет.

Запуск:  pythonw spider.py                — обычный режим (значок в трее)
         python  spider.py --selftest DIR  [--time "2026-12-15 09:00"]
"""
import sys
import os
import math
import random
import json
import time
import datetime
import ctypes
from collections import deque
from ctypes import wintypes

from PySide6.QtCore import Qt, QTimer, QPointF, QRectF, QRect, QPoint
from PySide6.QtGui import (QPainter, QColor, QPen, QIcon, QPixmap, QCursor, QFont, QFontMetrics, QAction,
                           QActionGroup, QTransform, QGuiApplication, QPolygonF, QPainterPath)
from PySide6.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QMenu

from art import (COSTUMES, COSTUME_BY_KEY, HATS, STYLES, crawl_targets, crawl_joints, get_pose, pose_hang, pose_crawl,
                 pose_point, fk, joint_bends, draw_web_rope,
                 lerp, lerp_pose, draw_head, draw_spider, draw_web_line, draw_splat, draw_smoke)

APP_NAME = "SpiderPal"
REG_NAME = "SpiderPal"
IDLE_SIT = 3.0            # с без движения мыши -> садится на кромку активного окна
IDLE_SLEEP = 5.0          # -> засыпает (днём)
IDLE_SLEEP_NIGHT = 3.0    # -> засыпает (ночью)
IDLE_MEME = 600.0         # -> мем с тремя пауками (10 минут простоя)
DOUBLE_EVERY = 300.0      # двойник прилетает раз в 5 минут
DOUBLE_ENABLED = False    # двойник пока убран по просьбе пользователя (05.11); True — вернуть меню и прилёты
DESCENT = 2.4             # с: гости (мем, гитарист) медленно спускаются на паутине, держась за неё рукой
NOIR_BAND_AFTER = 1.0     # режим Noir: через сколько секунд сидения прилетает гитарист; номер идёт, пока не прервут
SONG_LINE_EVERY = 6.5     # с: смена фразы песни в облачке
LONG_PRESS = 0.6          # с: долгое нажатие — паутина цепляется за точку нажатия, паук летит к ней
LYRICS_FILE = "noir_lyrics_ru.txt"
SWING_PX = (170, 240)     # длина одного маха по горизонтали
CRAWL_SPEED = 300         # px/с, предел скорости ползания — спокойно добирается, не «телепортируется»
CRAWL_ACCEL = 1800        # px/с², плавный разгон и торможение
BASE_BOX = QRectF(-62, -40, 124, 152)   # рамка кэша неподвижной части фигуры мема (в ед. модели)
TRICKS = ("flip", "star", "tuck", "reach", "corkscrew", "backflip")   # по очереди
SWINGS = ("hang", "swing_tuck", "swing_reach", "swing_kick")           # позы махов по очереди
NIGHT = (18, 8)           # ночь с 18:00 до 08:00
MORNING = (8, 12)         # утро с кофе

JOKES = ["The web is the internet too.", "Don't forget to save!", "Coffee? Black, no sugar.",
         "Just keeping an eye on the cursor.", "Ctrl+S - an engineer's best friend.",
         "I can crawl on walls, you know.", "Nice work!", "A break is part of the work too.",
         "Who touched my web?", "Cursor locked in.", "Great day for drafting.", "Did you drink water?"]

# Spider-Noir: старый усталый детектив (реплики на английском, в духе сериала)
NOIR_JOKES = ["The city never sleeps. Neither do my knees.", "Rain again. It was always raining in this town.",
              "I'm too old for this web.", "Coffee. Black. Like my suit, like my soul.",
              "My back is killing me. Climbing walls was easier in '37.", "Another night, another cigarette.",
              "Kids these days swing from a phone. I swung from a rope.",
              "Dames, dough and deadlines. Mostly deadlines.", "Keep your head down and your hat on.",
              "They don't make webs like they used to.", "Nothing good happens after midnight. Except jazz.",
              "Everybody's got a secret. Mine's a bad hip."]
NOIR_COUGH = ["*cough* ...these things'll kill me.", "*cough cough* ...worth it.", "*hrrm* ...smoke gets in your lungs."]
LYRICS_TEMPLATE = """# Текст песни для режима Noir mode (SpiderPal): Т. Муцураев — «В сигаретном дыму».
# В программе текста песни нет — впишите строки сами, ниже этих комментариев, по одной в строке.
# Кодировка UTF-8. Строки, начинающиеся с #, и пустые строки не читаются.
# В режиме Noir строки идут по очереди в облачке над поющим, по одной на такт пения (~6 с).
# Можно вставить текст целиком, даже одной строкой: программа сама делит его на фразы (новая фраза — с заглавной буквы).
# Пока строк нет, он поёт молча. Файл перечитывается при каждом прилёте гитариста — перезапуск не нужен.
"""

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
dwmapi = ctypes.windll.dwmapi
user32.GetForegroundWindow.restype = ctypes.c_void_p
for _fn, _args in ((user32.IsIconic, [ctypes.c_void_p]), (user32.IsWindow, [ctypes.c_void_p]), (user32.IsWindowVisible, [ctypes.c_void_p]),
                   (user32.GetClassNameW, [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_int]),
                   (user32.GetWindowThreadProcessId, [ctypes.c_void_p, ctypes.POINTER(wintypes.DWORD)]),
                   (user32.GetWindowRect, [ctypes.c_void_p, ctypes.POINTER(wintypes.RECT)]),
                   (dwmapi.DwmGetWindowAttribute, [ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD])):
    _fn.argtypes = _args
SKIP_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd", "NotifyIconOverflowWindow",
                "Windows.UI.Core.CoreWindow", "TopLevelWindowForOverflowXamlIsland"}


def native_to_logical(r):
    """Win32 RECT (физические px) -> логические px Qt. Экран берётся тот, на чьём мониторе центр окна:
    у каждого QScreen геометрия в логических px и свой devicePixelRatio (смешанный DPI)."""
    screens = QGuiApplication.screens()
    if not screens:
        return None
    cx, cy = (r.left + r.right) / 2, (r.top + r.bottom) / 2
    best = None
    for s in screens:
        g = s.geometry()
        d = s.devicePixelRatio() or 1.0
        nx, ny = g.x() * d, g.y() * d                         # левый верх монитора в физических px
        nw, nh = g.width() * d, g.height() * d
        inside = nx <= cx < nx + nw and ny <= cy < ny + nh
        if inside or best is None:
            best = (s, g, d, nx, ny)
            if inside:
                break
    s, g, d, nx, ny = best
    return (g.x() + (r.left - nx) / d, g.y() + (r.top - ny) / d,
            g.x() + (r.right - nx) / d, g.y() + (r.bottom - ny) / d)


def foreground_window():
    """(hwnd, (left, top, right, bottom)) активного окна в логических px или (None, None)."""
    h = user32.GetForegroundWindow()
    if not h or user32.IsIconic(h) or not user32.IsWindowVisible(h):
        return None, None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(pid))
    if pid.value == os.getpid():
        return None, None
    buf = ctypes.create_unicode_buffer(64)
    user32.GetClassNameW(h, buf, 64)
    if buf.value in SKIP_CLASSES:
        return None, None
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:   # DWMWA_EXTENDED_FRAME_BOUNDS
        user32.GetWindowRect(h, ctypes.byref(r))
    lg = native_to_logical(r)
    return (h, lg) if lg else (None, None)


def window_rect(h):
    """Рамка окна h в логических px или None, если окно закрыто, свёрнуто или скрыто."""
    if not h or not user32.IsWindow(h) or user32.IsIconic(h) or not user32.IsWindowVisible(h):
        return None
    r = wintypes.RECT()
    if dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        user32.GetWindowRect(h, ctypes.byref(r))
    return native_to_logical(r)


def wrap180(a):
    return (a + 180.0) % 360.0 - 180.0


def sign(x):
    return 1.0 if x >= 0 else -1.0


def smooth(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def app_dir():
    return os.path.dirname(sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__))


# ----------------------------------------------------------------------------- окно-оверлей
class Overlay(QWidget):
    """Прозрачное окно на весь экран: поверх всех, без рамки, клики проходят насквозь, не в панели задач."""

    def __init__(self, buddy, screen):
        super().__init__(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool |
                         Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus |
                         Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.buddy = buddy
        g = screen.geometry()
        # на 1 px ниже экрана, чтобы Windows не считал окно «полноэкранным» и не прятал панель задач
        self.geo = QRect(g.x(), g.y(), g.width(), g.height() - 1)
        self.setScreen(screen)
        self.setGeometry(self.geo)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(-self.geo.x(), -self.geo.y())
        self.buddy.paint(p)
        p.end()


# ----------------------------------------------------------------------------- настройки
def settings_path():
    base = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), REG_NAME)
    os.makedirs(base, exist_ok=True)
    return os.path.join(base, "settings.json")


DEFAULTS = dict(costume="classic", size=1.0, hat="auto", clickweb=True, sleep=True, meme=True,
                windows=True, seasonal=True, bubbles=True, double=True, hidden=False, noir_mode=False)


def autostart_cmd():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    return f'"{pyw}" "{os.path.abspath(__file__)}"'


def autostart_get():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as k:
            winreg.QueryValueEx(k, REG_NAME)
            return True
    except OSError:
        return False


def autostart_set(on):
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run",
                        0, winreg.KEY_SET_VALUE) as k:
        if on:
            winreg.SetValueEx(k, REG_NAME, 0, winreg.REG_SZ, autostart_cmd())
        else:
            try:
                winreg.DeleteValue(k, REG_NAME)
            except OSError:
                pass


# ----------------------------------------------------------------------------- нить паутины
class Rope:
    """Нить паутины — цепочка точек (интегрирование Верле): концы держат крепление и рука, середина
    провисает под тяжестью и изгибается по инерции, когда паук качается или летит. Нить не тянется,
    но может провисать (ограничение только на растяжение звена)."""
    N = 14

    def __init__(self, a, b):
        self.reset(a, b)

    def reset(self, a, b):
        n = self.N
        self.p = [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
        self.q = list(self.p)
        self.dt0 = 1 / 120
        self.t = None

    def step(self, a, b, length, dt, g, now=None):
        if now is not None:                 # один шаг на кадр, даже если кадр рисуют два монитора
            if self.t == now:
                return
            self.t = now
        n = self.N
        p, q = self.p, self.q
        dt = max(1e-3, min(dt, 1 / 30))
        r = max(0.5, min(2.0, dt / self.dt0))    # переменный шаг: скорость пересчитываем на новый dt
        self.dt0 = dt
        damp = 0.982 ** (dt * 120)
        gy = g * dt * dt
        for i in range(1, n):
            x, y = p[i]
            px, py = q[i]
            q[i] = (x, y)
            p[i] = (x + (x - px) * damp * r, y + (y - py) * damp * r + gy)
        p[0] = q[0] = (a[0], a[1])
        p[n] = q[n] = (b[0], b[1])
        length = max(length, math.hypot(b[0] - a[0], b[1] - a[1]))
        seg = length / n
        for _ in range(6):
            for i in range(n):
                x1, y1 = p[i]
                x2, y2 = p[i + 1]
                dx, dy = x2 - x1, y2 - y1
                d = math.hypot(dx, dy)
                if d > seg:
                    f = (d - seg) / d
                    if i == 0:
                        p[1] = (x2 - dx * f, y2 - dy * f)
                    elif i + 1 == n:
                        p[i] = (x1 + dx * f, y1 + dy * f)
                    else:
                        f *= 0.5
                        p[i] = (x1 + dx * f, y1 + dy * f)
                        p[i + 1] = (x2 - dx * f, y2 - dy * f)


def split_phrases(lines):
    """Текст песни -> фразы для облачка. Каждая строка — фраза; длинная строка (текст, вставленный одним
    куском) делится там, где после строчной буквы или конца предложения начинается заглавная."""
    out = []
    for ln in lines:
        if len(ln) <= 60:                # короткая строка — одна фраза целиком
            out.append(ln.strip())
            continue
        cur = ""
        for ch in ln:
            last = cur.rstrip()[-1:]
            if ch.isalpha() and ch.isupper() and last and (last.islower() or last in ".!?…"):
                out.append(cur.strip())
                cur = ""
            cur += ch
        if cur.strip():
            out.append(cur.strip())
    return [x for x in out if x]


# ----------------------------------------------------------------------------- логика
class Buddy:
    """Режимы героя:
    hang  — висит на паутине около курсора (ось — кисть), отсюда сон вниз головой;
    crawl — ползёт по экрану к курсору (ось — центр тела);
    sit   — сидит на верхней кромке активного окна, свесив ноги (ось — сиденье);
    swing — мах на паутине при перелёте на другой монитор (ось — кисть);
    air   — свободный полёт между махами с трюком (ось — центр тела).
    В crawl/air может лететь выстрел паутины (shooting) — при попадании переход в hang/swing."""

    def __init__(self, app, selftest=False, overrides=None, fake_time=None):
        self.app = app
        self.selftest = selftest
        self.s = dict(DEFAULTS)
        if not selftest:
            try:
                with open(settings_path(), encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    self.s.update(loaded)
            except Exception:
                pass
        self.s.update(overrides or {})
        if self.s.get("size") not in (0.7, 1.0, 1.5, 2.0):
            self.s["size"] = 1.0
        for key, val in DEFAULTS.items():
            if isinstance(val, bool) and not isinstance(self.s.get(key), bool):
                self.s[key] = val
        if self.s["costume"] not in COSTUME_BY_KEY:
            self.s["costume"] = "classic"
        self.fake_time = fake_time
        self.cursor_fn = self.real_cursor
        vk = 0x02 if user32.GetSystemMetrics(23) else 0x01       # SM_SWAPBUTTON: у левши «левая» — правая
        self.mouse_fn = lambda: bool(user32.GetAsyncKeyState(vk) & 0x8000)
        self.t_start = time.perf_counter()
        self.last = self.t_start
        self.frames = 0
        self.mode_log = deque(maxlen=400)
        self.events = deque(maxlen=400)

        cur = self.cursor_fn()
        self.prev_cur = cur
        k = self.k
        gx, gy = cur[0] + 26 * k, cur[1] + 16 * k
        self.P = [gx, gy]
        self.V = [0.0, 0.0]
        self.A = [gx, gy - 150 * k]
        self.L = 150 * k
        self.mode = "hang"
        self.shooting = False
        self.final = False
        self.tip = [gx, gy]
        self.A_new = [gx, gy]
        self.retracts = []
        self.dir = 1.0
        self.trick = "reach"
        self.trick_i = -1
        self.swing_i = 0
        self.t_air = 0.0
        self.t_swing = 0.0
        self.crawl_phase = 0.0
        self.band = None                 # гитарист рядом с сидящим Нуаром
        self.next_band = 0.0
        self.cough_until = 0.0
        self.next_cough = self.t_start + random.uniform(120, 240)     # реплики — редко
        self.next_quip = self.t_start + random.uniform(180, 300)
        self.rope = None                 # физическая нить, на которой висит/качается герой
        self.zip = False                 # долгое нажатие: подтягивается к точке крепления
        self.press = None                # текущее нажатие левой кнопки
        self.song = self.load_lyrics()
        self.roost = None                # место сна: dict(A, goal, arrived) — вис на кромке окна
        self.vs = [0.0, 0.0]             # сглаженная скорость — для плавного разворота корпуса
        self.flip = 1.0
        self.flip_target = 1.0
        self.rot = 0.0
        self.trail = 0.0
        self.sleep_f = 0.0
        self.calm = False
        self.att = (0.0, 0.0)
        self.last_move = self.t_start
        self.meme = None
        self.meme_shown = False
        self.meme_started_idle = None
        self.splats = []
        self.mouse_down = False
        self.T = QTransform()
        self.pose = get_pose("hang", self.style)
        self.J = fk(self.style, self.pose)
        self.eyes = "open"
        self.prev_rects = []
        self.font = QFont("Segoe UI")
        self.font.setBold(True)
        self.bfont = QFont("Segoe UI")
        # новые фишки
        self.sit = None                  # dict(hwnd, rect, x) — на каком окне сидит
        self.sit_target = None           # куда ползёт, чтобы сесть
        self.dozing = False
        self.last_win_check = 0.0
        self.dizzy_until = 0.0
        self.reversals = []
        self.prev_vx = 0.0
        self.stroke_max = 0.0
        self.double = None
        self.double_i = 0
        self.next_double = self.t_start + DOUBLE_EVERY
        self.parts = []                  # перья, звёздочки
        self.bubble = None
        self.bubble_rect = None
        self.next_joke = self.t_start + random.uniform(1500, 2400)
        self.active_since = self.t_start
        self.period = self.period_of(self.clock())
        self.pending_stretch = False
        self.stretch_until = 0.0
        self.jokes = list(JOKES)
        try:
            with open(os.path.join(app_dir(), "phrases.txt"), encoding="utf-8") as f:
                self.jokes += [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        except OSError:
            pass

        self.overlays = []
        self.build_overlays()
        QGuiApplication.instance().screenAdded.connect(lambda *_: self.build_overlays())
        QGuiApplication.instance().screenRemoved.connect(lambda *_: self.build_overlays())

        self.timer = QTimer()
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self.tick)
        self.timer.start(8)

        self.build_tray()
        self.apply_hidden()

    # --- свойства
    @property
    def k(self):
        return float(self.s["size"])

    @property
    def style(self):
        return "chibi"

    @property
    def st(self):
        return STYLES[self.style]

    @property
    def scale(self):
        return self.st["px"] * self.k

    def clock(self):
        if self.fake_time:
            return self.fake_time + datetime.timedelta(seconds=time.perf_counter() - self.t_start)
        return datetime.datetime.now()

    @staticmethod
    def period_of(dt):
        h = dt.hour
        if h >= NIGHT[0] or h < NIGHT[1]:
            return "night"
        return "morning" if MORNING[0] <= h < MORNING[1] else "day"

    @property
    def noir(self):
        """Режим Noir (меню «Noir mode»): своё поведение — старый детектив садится и поёт с гитаристом."""
        return bool(self.s.get("noir_mode"))

    @property
    def noir_look(self):
        """Вид Нуара (федора, сигарета, дым): в режиме Noir или просто костюм Spider-Noir."""
        return self.noir or self.s["costume"] == "noir"

    @staticmethod
    def lyrics_path():
        return os.path.join(app_dir(), LYRICS_FILE)

    def load_lyrics(self):
        """Строки песни из пользовательского файла рядом с exe (UTF-8, строка на строку)."""
        for enc in ("utf-8-sig", "cp1251"):
            try:
                with open(self.lyrics_path(), encoding=enc) as f:
                    return split_phrases([ln.strip() for ln in f if ln.strip() and not ln.lstrip().startswith("#")])
            except UnicodeDecodeError:
                continue
            except OSError:
                return []
        return []

    def open_lyrics(self):
        path = self.lyrics_path()
        if not os.path.exists(path):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(LYRICS_TEMPLATE)
            except OSError:
                return
        os.startfile(path)

    @property
    def costume(self):
        """Костюм с учётом праздников и времени суток (если включено в меню)."""
        if self.noir:
            return COSTUME_BY_KEY["noir"]
        if self.s["seasonal"] and not self.noir_look:
            d = self.clock()
            if d.month == 12:
                return COSTUME_BY_KEY["newyear"]
            if d.month == 10 and d.day == 31:
                return COSTUME_BY_KEY["halloween"]
            if self.period == "night":
                return COSTUME_BY_KEY["pajama"]
        return COSTUME_BY_KEY[self.s["costume"]]

    @property
    def hat(self):
        h = self.s["hat"]
        if h == "auto" and self.noir_look:
            return "fedora"
        if h == "auto":
            d = self.clock()
            if d.month == 12:
                return "santa"
            if d.month == 10 and d.day == 31:
                return "pumpkin"
            return "nightcap" if self.period == "night" else None
        return None if h == "none" else h

    def save(self):
        if self.selftest:
            return
        try:
            with open(settings_path(), "w", encoding="utf-8") as f:
                json.dump(self.s, f, ensure_ascii=False, indent=1)
        except OSError:
            pass

    def real_cursor(self):
        c = QCursor.pos()
        return (float(c.x()), float(c.y()))

    def screen_at(self, x, y):
        return QGuiApplication.screenAt(QPoint(int(x), int(y)))

    def world(self, pt, T=None):
        w = (T or self.T).map(QPointF(*pt))
        return [w.x(), w.y()]

    def hand_world(self):
        return self.world(self.J["rh"])

    def set_mode(self, mode):
        if mode != self.mode:
            self.mode = mode
            self.mode_log.append((round(time.perf_counter() - self.t_start, 2),
                                  f"air:{self.trick}" if mode == "air" else mode))

    def log(self, what):
        self.events.append((round(time.perf_counter() - self.t_start, 2), what))

    def set_pivot(self, att):
        """Сменить точку модели, которая привязана к self.P, без скачка картинки."""
        self.P = self.world(att)
        self.att = att

    def say(self, text, now=None):
        if not self.s["bubbles"]:
            return
        self.bubble = dict(text=text, t0=now or time.perf_counter(), dur=3.6)
        self.log("say: " + text)

    # --- окна
    def build_overlays(self):
        for o in self.overlays:
            o.close()
            o.deleteLater()
        self.overlays = [Overlay(self, s) for s in QGuiApplication.screens()]
        for s in QGuiApplication.screens():
            if not getattr(s, "_spider_hooked", False):
                s._spider_hooked = True
                s.geometryChanged.connect(lambda *_: self.build_overlays())
        r = QRect()
        for s in QGuiApplication.screens():
            r = r.united(s.geometry())
        self.vrect = r
        for o in self.overlays:
            if not self.s.get("hidden"):
                o.show()

    def apply_hidden(self):
        hidden = self.s.get("hidden")
        for o in self.overlays:
            o.setVisible(not hidden)
        if hidden:
            self.timer.stop()
            self.meme = None
            self.double = None
            self.band = None
        elif not self.timer.isActive():
            self.last = time.perf_counter()
            self.timer.start(8)

    # --- трей
    def make_icon(self, c=None):
        c = c or COSTUME_BY_KEY["noir" if self.noir else self.s["costume"]]
        pm = QPixmap(64, 64)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(32, 9 if "mohawk" in c else 4)
        p.scale(0.88, 0.88)
        draw_head(p, c)
        p.end()
        return QIcon(pm)

    def _radio(self, menu, items, key, cb=None):
        grp = QActionGroup(menu)
        acts = {}
        for name, val in items:
            if name is None:
                menu.addSection(val)
                continue
            a = QAction(name, menu)
            a.setCheckable(True)
            a.setChecked(self.s[key] == val)
            a.triggered.connect(lambda _=False, v=val: (self.set_opt(key, v), cb and cb()))
            grp.addAction(a)
            menu.addAction(a)
            acts[val] = a
        return acts

    def build_tray(self):
        self.tray = QSystemTrayIcon(self.make_icon(), self.app)
        self.tray.setToolTip(f"{APP_NAME} — {COSTUME_BY_KEY[self.s['costume']]['name']}")
        m = QMenu()
        sub = m.addMenu("Costume")
        grp = QActionGroup(sub)
        self.costume_actions = {}
        for c in COSTUMES:
            a = QAction(self.make_icon(c), c["name"], sub)
            a.setCheckable(True)
            a.setChecked(c["key"] == self.s["costume"])
            a.triggered.connect(lambda _=False, key=c["key"]: self.set_costume(key))
            grp.addAction(a)
            sub.addAction(a)
            self.costume_actions[c["key"]] = a
        sub.addSeparator()
        sub.addAction("Next (double-click the tray icon)").triggered.connect(self.next_costume)

        hats = m.addMenu("Hat")
        items = [("Auto (nightcap at night, Santa in December, pumpkin on Oct 31)", "auto"), ("No hat", "none")]
        group = None
        for key, name, grp_name in HATS:
            if grp_name != group:
                items.append((None, grp_name))
                group = grp_name
            items.append((name, key))
        self._radio(hats, items, "hat")

        sz = m.addMenu("Size")
        self._radio(sz, [("Mini", 0.7), ("Normal", 1.0), ("Large", 1.5), ("Huge", 2.0)], "size")

        m.addSeparator()
        a = m.addAction("Noir mode (sings with a guitarist)")
        a.setCheckable(True)
        a.setChecked(self.noir)
        a.toggled.connect(self.set_noir_mode)
        m.addAction("Open lyrics file… (" + LYRICS_FILE + ")").triggered.connect(self.open_lyrics)
        m.addSeparator()
        toggles = [("Web on mouse click", "clickweb"),
                          ("Sit on the active window edge (3 s idle)", "windows"),
                          ("Fall asleep (5 s, 3 s at night)", "sleep"),
                          ("Three-spiders meme (10 min idle)", "meme"),
                          ("Double every 5 minutes", "double"),
                          ("Speech bubbles", "bubbles"),
                          ("Holidays and time of day (pajamas, coffee)", "seasonal")]
        if not DOUBLE_ENABLED:
            toggles = [t for t in toggles if t[1] != "double"]
        for text, key in toggles:
            a = m.addAction(text)
            a.setCheckable(True)
            a.setChecked(bool(self.s[key]))
            a.toggled.connect(lambda v, key=key: self.set_opt(key, v))
        m.addAction("Show the meme now").triggered.connect(lambda: self.start_meme(time.perf_counter()))
        if DOUBLE_ENABLED:
            m.addAction("Call the double").triggered.connect(lambda: self.start_double(time.perf_counter(), True))
        m.addSeparator()
        a = m.addAction("Hide the spider")
        a.setCheckable(True)
        a.setChecked(bool(self.s["hidden"]))
        a.toggled.connect(lambda v: (self.set_opt("hidden", v), self.apply_hidden()))
        a = m.addAction("Run with Windows")
        a.setCheckable(True)
        a.setChecked(autostart_get())
        a.toggled.connect(autostart_set)
        m.addSeparator()
        m.addAction("Quit").triggered.connect(self.app.quit)
        self.menu = m
        self.tray.setContextMenu(m)
        self.tray.activated.connect(self.on_tray)
        self.tray.show()

    def on_tray(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.next_costume()

    def set_costume(self, key):
        self.s["costume"] = key
        self.costume_actions[key].setChecked(True)
        self.tray.setIcon(self.make_icon())
        self.tray.setToolTip(f"{APP_NAME} — {COSTUME_BY_KEY[key]['name']}")
        self.save()

    def next_costume(self):
        keys = [c["key"] for c in COSTUMES]
        self.set_costume(keys[(keys.index(self.s["costume"]) + 1) % len(keys)])

    def set_opt(self, key, val):
        self.s[key] = val
        self.save()

    def set_noir_mode(self, on):
        """Режим Noir: вид Spider-Noir и его поведение; гитарист прилетает, когда он сядет."""
        now = time.perf_counter()
        self.set_opt("noir_mode", bool(on))
        self.tray.setIcon(self.make_icon())
        if on:
            self.next_band = 0.0
            self.say("Noir mode. Grab a chair, kid.", now)
        else:
            self.end_band(now)

    # --- мем
    def start_meme(self, now):
        """Трое спускаются на паутинах и встают треугольником, как в меме."""
        cur = self.cursor_fn()
        scr = self.screen_at(*cur) or QGuiApplication.primaryScreen()
        if scr is None:
            return
        av = scr.availableGeometry()
        H = max(150.0, min(av.height() * 0.30, 300.0))
        mine = self.costume["key"]
        others = [c["key"] for c in COSTUMES if c["key"] != mine]
        k_mid, k_right = random.sample(others, 2)
        cx, cy = av.center().x(), av.center().y()
        base = cy + H * 0.55
        figs = [  # порядок — порядок отрисовки: средний дальше всех
            dict(x=cx, floor=base - H * 0.3, sc=0.82, key=k_mid, mirror=1, view="front", var="mid", delay=0.0),
            dict(x=cx - H * 0.78, floor=base, sc=1.0, key=mine, mirror=1, view="front", var="left", delay=0.2),
            dict(x=cx + H * 0.78, floor=base, sc=1.0, key=k_right, mirror=-1, view="front", var="back", delay=0.4),
        ]
        for f in figs:
            f.update(ph=random.uniform(0, 6), feet=-1e9, hold=1.0, web_u=0.0)
        self.meme = dict(t0=now, phase="in", tout=0.0, top=float(scr.geometry().top()), H=H, figs=figs)
        self.meme_shown = True
        self.meme_started_idle = now - self.last_move
        self.log("meme")

    def update_meme(self, now):
        """Каждый медленно спускается на паутине, держась за неё рукой (DESCENT с), встаёт, паутина отлипает и
        втягивается вверх. На выходе — паутина вниз к руке, хватается и уходит вверх."""
        m = self.meme
        if not m:
            return
        top = m["top"]
        done_in, gone = True, True
        for i, f in enumerate(m["figs"]):
            floor = f["floor"]
            if m["phase"] in ("in", "idle"):
                lt = now - m["t0"] - f["delay"]
                if lt < 0:
                    f["feet"], f["hold"], f["web_u"] = top - 30, 1.0, 0.0
                    done_in = False
                    continue
                pr = min(lt / DESCENT, 1.0)
                f["feet"] = lerp(top - 10, floor, 1 - (1 - pr) ** 3)
                if lt < DESCENT:
                    f["hold"], f["web_u"] = 1.0, 1.0
                    done_in = False
                elif lt < DESCENT + 0.5:
                    u = (lt - DESCENT) / 0.5
                    f["hold"], f["web_u"] = 1.0 - smooth(u), 1.0 - u
                    done_in = False
                else:
                    f["hold"], f["web_u"] = 0.0, 0.0
            else:  # out
                lt = now - m["tout"] - i * 0.08
                if lt < 0:
                    gone = False
                    continue
                grab = min(1.0, lt / 0.35)
                f["hold"], f["web_u"] = smooth(grab), grab
                if lt < 0.35:
                    f["feet"] = floor
                else:
                    u = lt - 0.35
                    f["feet"] = floor - 0.5 * 2500 * u * u
                if f["feet"] > top - 10:
                    gone = False
        if m["phase"] == "in" and done_in:
            m["phase"] = "idle"
        if m["phase"] == "out" and gone:
            self.meme = None

    # --- гитарист рядом с Нуаром (режим песни: только клик или закрытие окна прерывают)
    def start_band(self, now):
        k = self.k
        st = self.sit
        r = st["rect"]
        gap = 70 * k
        right_room = r[2] - st["x"] if st["hwnd"] else 1e9
        left_room = st["x"] - r[0] if st["hwnd"] else 1e9
        side = 1.0 if right_room >= left_room else -1.0
        if st["hwnd"]:
            side = side if (right_room if side > 0 else left_room) > gap + 30 * k else -side
        key = random.choice([c["key"] for c in COSTUMES if c["key"] not in ("noir", self.s["costume"])])
        scr = self.screen_at(*self.P) or QGuiApplication.primaryScreen()
        self.band = dict(key=key, side=side, x=self.P[0] + side * gap, ty=self.P[1], y=float(scr.geometry().top()) - 80,
                         top=float(scr.geometry().top()), phase="in", t0=now, T=QTransform(), J=None,
                         pose=get_pose("guitar", self.style), line_i=0, next_line=now + DESCENT + 1.0, hold=1.0,
                         web=None)
        self.song = self.load_lyrics()          # файл перечитывается при каждом номере — перезапуск не нужен
        self.log("band")

    def end_band(self, now):
        b = self.band
        if b and b["phase"] != "out":
            b["phase"], b["t_out"] = "out", now
            self.next_band = now + 1.0

    def update_band(self, now, dt):
        """Гитарист медленно спускается на паутине, держась за неё правой рукой (DESCENT с), садится, паутина
        отлипает и втягивается; играет; улетает — снова хватается за паутину и уходит вверх."""
        b = self.band
        if not b:
            return
        k = self.k
        hang = pose_hang(self.style)
        play = get_pose("guitar", self.style)
        web_u = 1.0                      # 1 — паутина до руки, 0..1 — отлипла и втягивается вверх
        if b["phase"] == "in":
            u = min(1.0, (now - b["t0"]) / DESCENT)
            b["y"] = lerp(b["top"] - 60 * k, b["ty"], 1 - (1 - u) ** 3)
            b["hold"] = 1.0
            if u >= 1:
                b["phase"], b["t_land"] = "land", now
        elif b["phase"] == "land":       # сел: отпускает паутину, берёт гитару
            u = min(1.0, (now - b["t_land"]) / 0.5)
            b["hold"] = 1.0 - smooth(u)
            web_u = 1.0 - u
            if u >= 1:
                b["phase"] = "play"
        elif b["phase"] == "play":
            b["hold"], web_u = 0.0, 0.0
            if self.mode != "sit":
                self.end_band(now)
            elif now >= b["next_line"]:
                # пение: строки из файла пользователя по очереди; пока файла нет — подпись песни
                if self.song:
                    self.say(self.song[b["line_i"] % len(self.song)], now)
                    if self.bubble:
                        self.bubble["dur"] = SONG_LINE_EVERY - 0.5
                elif b["line_i"] == 0:        # файла со словами нет — одна подсказка, дальше молча
                    self.say("Paste the lyrics into " + LYRICS_FILE + " (tray menu: Open lyrics file)", now)
                b["line_i"] += 1
                b["next_line"] = now + SONG_LINE_EVERY
        else:                            # out: паутина вниз к руке, хватается и уходит вверх
            u = now - b["t_out"]
            grab = min(1.0, u / 0.35)
            b["hold"], web_u = smooth(grab), grab
            if u > 0.35:
                v = u - 0.35
                b["y"] = b["ty"] - 0.5 * 2500 * k * v * v
            if b["y"] < b["top"] - 200 * k:
                self.band = None
                return
        if b["phase"] == "play":
            play["la"] = (-20, -35 + 10 * math.sin(now * 9.5))      # бой по струнам
        pose = lerp_pose(play, hang, b["hold"]) if b["hold"] > 0 else play
        if b["hold"] <= 0.5:
            pose["item"] = "guitar"      # пока держится за паутину — гитара за спиной, не видна
        else:
            pose.pop("item", None)
        seat = (0.0, self.st["hip"][1] + 4 * self.st["hs"])
        b["pose"] = pose
        b["J"] = fk(self.style, pose)
        sway = 3.0 * math.sin(now * 2.2) if b["phase"] == "play" else 0.0
        b["T"] = (QTransform().translate(b["x"], b["y"]).rotate(sway).scale(self.scale * b["side"], self.scale)
                  .translate(-seat[0], -seat[1]))
        hand = b["T"].map(QPointF(*b["J"]["rh"]))
        if b["phase"] == "in" or "wx" not in b:
            b["wx"] = hand.x()           # точка крепления — над рукой; дальше не двигается
        if b["phase"] == "in" and "rope" not in b:
            b["rope"] = Rope((b["wx"], b["top"]), (hand.x(), hand.y()))
        b["web"] = None if web_u <= 0 else (hand.x(), lerp(b["top"], hand.y(), web_u))

    def paint_band(self, p, now):
        b = self.band
        if not b or b["J"] is None:
            return
        wl = max(1.0, self.k * 0.85)
        if b["web"]:
            a, e = (b["wx"], b["top"]), b["web"]
            if b["phase"] == "in" and b.get("rope"):
                b["rope"].step(a, e, math.hypot(e[0] - a[0], e[1] - a[1]) * 1.012, 1 / 60, 2400 * self.k, now)
                draw_web_rope(p, b["rope"].p, wl, cone=12 * self.k, phase=now * 0.7)
            else:
                draw_web_line(p, QPointF(*a), QPointF(*e), wl, cone=12 * self.k)
        p.save()
        p.setTransform(b["T"], True)
        draw_spider(p, COSTUME_BY_KEY[b["key"]], b["pose"], "open", "front", style=self.style, t=now, J=b["J"])
        p.restore()

    # --- двойник
    def start_double(self, now, force=False):
        if self.double or self.meme or (not force and self.mode != "hang"):
            return False
        if self.mode != "hang":           # из меню — паук сначала повиснет, двойник подождёт
            self.next_double = now + 3
            return False
        k = self.k
        scr = self.screen_at(*self.P) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        side = 1.0 if self.P[0] < g.center().x() else -1.0
        mine = self.costume["key"]
        key = random.choice([c["key"] for c in COSTUMES if c["key"] != mine])
        act = ("five", "pillow")[self.double_i % 2]
        self.double_i += 1
        gap = 100     # тела рядом, свободные руки навстречу
        self.double = dict(key=key, act=act, side=side, t0=now, phase="in", x=self.P[0] + side * gap * k,
                           ty=self.P[1], y=float(g.top()) - 60, top=float(g.top()), T=QTransform(), J=None,
                           pose=get_pose("hang", self.style), last_cycle=-1)
        self.next_double = now + DOUBLE_EVERY
        self.say("High five, double!" if act == "five" else "Pillow fight!", now)
        self.log("double: " + act)
        return True

    def double_arm(self, act, u, active=True):
        """Угол свободной руки в игре: five — хлопок в середине цикла, pillow — замах и удар."""
        if act == "five":
            b = math.sin(math.pi * u) ** 4
            return (118 - 28 * b, 135 - 30 * b)
        sw = math.sin(math.pi * u) if active else 0.0
        return (lerp(140, 70, sw), lerp(160, 85, sw))

    def update_double(self, now, dt):
        d = self.double
        if not d:
            return
        k = self.k
        if d["phase"] == "in":
            u = min(1.0, (now - d["t0"]) / 0.8)
            d["y"] = lerp(d["top"] - 60, d["ty"], 1 + 2.5 * (u - 1) ** 3 + 1.5 * (u - 1) ** 2)
            if u >= 1:
                d["phase"], d["t_act"] = "act", now
        elif d["phase"] == "act":
            if self.mode != "hang" or now - d["t_act"] > 8.0:
                d["phase"], d["t_out"] = "out", now
                if self.mode != "hang":
                    self.say("Bye-bye!", now)
        else:
            u = now - d["t_out"]
            d["y"] = d["ty"] - 0.5 * 4000 * k * u * u
            if d["y"] < d["top"] - 200 * k:
                self.double = None
                return
        pose = get_pose("hang", self.style)
        if d["phase"] == "act":
            T = 1.6 if d["act"] == "five" else 1.2
            ph = (now - d["t_act"]) / T
            u = ph % 1.0
            name = d["act"]
            pose = get_pose(name, self.style)
            if name == "five":
                pose["la"] = self.double_arm("five", u)
            else:
                pose["la"] = self.double_arm("pillow", (u - 0.5) * 2 if u >= 0.5 else 0, u >= 0.5)
            cyc = int(ph * 2)          # два события на цикл: хлопок/удар
            if cyc != d["last_cycle"]:
                d["last_cycle"] = cyc
                if name == "five" and cyc % 2 == 1 and d["J"]:          # хлопок ладонями
                    a, b = self.world(self.J["lh"]), self.world(d["J"]["lh"], d["T"])
                    self.burst((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, now)
                elif name == "pillow" and d["J"] and cyc > 0:
                    # конец первой половины цикла — наш попал по двойнику, конец второй — двойник по нашему
                    hc = self.head_center()
                    tgt = self.world(hc, d["T"]) if cyc % 2 == 1 else self.world(hc)
                    self.feathers(tgt[0], tgt[1], now)
        d["pose"] = lerp_pose(d["pose"], pose, min(1.0, dt * 14))
        d["J"] = fk(self.style, d["pose"])
        s = self.scale
        mirror = d["side"]
        sway = 3 * math.sin(now * 2)
        hx, hy = d["x"], d["y"]
        d["T"] = (QTransform().translate(hx, hy).rotate(sway).scale(s * mirror, s)
                  .translate(-d["J"]["rh"][0], -d["J"]["rh"][1]))

    def hero_double_pose(self, now):
        d = self.double
        T = 1.6 if d["act"] == "five" else 1.2
        u = ((now - d["t_act"]) / T) % 1.0
        pose = get_pose(d["act"], self.style)
        if d["act"] == "five":
            pose["la"] = self.double_arm("five", u)
        else:
            pose["la"] = self.double_arm("pillow", u * 2 if u < 0.5 else 0, u < 0.5)
        return pose

    # --- частицы
    def burst(self, x, y, now):
        self.parts.append(dict(kind="burst", x=x, y=y, t0=now, life=0.45))

    def feathers(self, x, y, now):
        for _ in range(7):
            self.parts.append(dict(kind="feather", x=x, y=y, vx=random.uniform(-140, 140),
                                   vy=random.uniform(-170, -40), t0=now, life=1.6,
                                   rot=random.uniform(0, 360), vr=random.uniform(-200, 200)))

    def update_parts(self, now, dt):
        for f in self.parts:
            if f["kind"] == "feather":
                f["vy"] += 240 * dt
                f["vx"] *= math.exp(-1.5 * dt)
                f["vy"] = min(f["vy"], 60)
                f["x"] += (f["vx"] + 30 * math.sin((now - f["t0"]) * 6)) * dt
                f["y"] += f["vy"] * dt
                f["rot"] += f["vr"] * dt
        self.parts = [f for f in self.parts if now - f["t0"] < f["life"]]

    # --- переходы между режимами
    def retract_rope(self, now):
        self.retracts.append((list(self.A), list(self.P), now))

    def crawl_ik(self):
        """Шаг: левая рука вытянута вперёд и левая нога прямая, правая рука и нога согнуты — потом наоборот.
        Фаза идёт по пройденному пути (crawl_phase), поэтому без движения конечности замирают."""
        self.J = crawl_joints(self.style, self.J, crawl_targets(self.crawl_phase))

    def start_crawl(self, now):
        self.end_band(now)
        self.vs = [0.0, 0.0]
        if self.mode in ("hang", "swing"):
            self.retract_rope(now)
        self.set_pivot(self.st["com"])
        self.V = [0.0, 0.0]
        self.shooting = False
        self.sit = None
        self.set_mode("crawl")

    def start_travel(self, now, G):
        k = self.k
        self.end_band(now)
        if self.mode in ("hang", "swing"):
            self.retract_rope(now)
        self.set_pivot(self.st["com"])
        if abs(G[0] - self.P[0]) > 30 * k:
            self.dir = sign(G[0] - self.P[0])
        self.V = [self.dir * 220 * k + self.V[0] * 0.5, -380 * k]     # прыжок
        self.shooting = False
        self.sit = None
        self.next_trick()
        self.t_air = 0.0
        self.set_mode("air")

    def start_sit(self, now, hwnd, rect, x):
        seat = (0.0, self.st["hip"][1] + 4 * self.st["hs"])
        self.set_pivot(seat)
        self.P = [x, rect[1]]
        self.V = [0.0, 0.0]
        self.shooting = False
        self.sit = dict(hwnd=hwnd, rect=rect, x=x, t0=now)
        self.set_mode("sit")

    def release(self, now):
        self.retract_rope(now)
        self.set_pivot(self.st["com"])
        self.V[0] *= 1.05
        self.V[1] = min(self.V[1] * 1.05, self.V[1] - 150 * self.k)
        self.next_trick()
        self.t_air = 0.0
        self.set_mode("air")

    def next_trick(self):
        self.trick_i += 1
        self.trick = TRICKS[self.trick_i % len(TRICKS)]

    def shoot(self, A_new, final):
        self.A_new = A_new
        self.final = final
        self.tip = self.hand_world()
        self.shooting = True

    def zip_to(self, now, pt):
        """Долгое нажатие: выстрел паутиной в точку нажатия; нить цепляется, и паук подтягивается к ней."""
        if self.meme:
            return
        k = self.k
        self.roost = None
        self.end_band(now)
        self.sit_target = None
        if self.mode == "sit":
            self.sit = None
            self.set_pivot(self.st["com"])
            self.V = [0.0, -60 * k]
            self.t_air = 0.0
            self.trick = "reach"
            self.set_mode("air")
        self.zip = True
        self.shoot([pt[0], pt[1]], True)
        self.log("zip")

    def plan_next_web(self, G):
        k = self.k
        hand = self.hand_world()
        scr = self.screen_at(*G) or self.screen_at(*hand)
        top = (scr.geometry().top() if scr else self.vrect.top()) + 4
        dx, dy = G[0] - hand[0], G[1] - hand[1]
        if math.hypot(dx, dy) < 240 * k:            # последний мах — повиснуть у курсора (или на месте сна)
            self.shoot(list(self.roost["A"]) if self.roost
                       else [G[0], max(G[1] - random.uniform(120, 170) * k, top)], True)
            return
        if abs(dx) > 30 * k:
            self.dir = sign(dx)
        ahead = self.dir * min(abs(dx) * 0.55 + 30 * k, random.uniform(*SWING_PX) * k)
        ahead += max(-80 * k, min(80 * k, self.V[0] * 0.12))
        ax = max(self.vrect.left() + 4, min(self.vrect.right() - 4, hand[0] + ahead))
        ay = max(min(hand[1], G[1]) - random.uniform(130, 190) * k, top)
        self.shoot([ax, ay], False)

    def attach(self):
        if self.mode in ("hang", "swing"):
            self.retract_rope(time.perf_counter())
        self.set_pivot(self.J["rh"])
        self.A = list(self.A_new)
        self.L = max(20.0, math.hypot(self.P[0] - self.A[0], self.P[1] - self.A[1]))
        self.shooting = False
        self.rope = Rope(self.A, self.P)
        if self.mode == "crawl":
            self.V = [0.0, 0.0]
        if self.final:
            self.set_mode("hang")
        else:
            self.t_swing = 0.0
            self.swing_i += 1          # каждый мах — в другой позе
            self.set_mode("swing")

    # --- физика
    def physics(self, h, G):
        k = self.k
        g = 2400 * k
        P, V = self.P, self.V
        mode = self.mode
        if self.shooting:
            dx, dy = self.A_new[0] - self.tip[0], self.A_new[1] - self.tip[1]
            d = math.hypot(dx, dy)
            step = (2200 if self.zip else 3600) * k * h
            if d <= step:
                self.attach()
                mode = self.mode
            else:
                self.tip[0] += dx / d * step
                self.tip[1] += dy / d * step
        if mode == "sit":
            V[0] = V[1] = 0.0
            return
        if mode == "crawl":
            Gc = self.crawl_goal
            dvx, dvy = (Gc[0] - P[0]) * 3, (Gc[1] - P[1]) * 3
            d = math.hypot(dvx, dvy)
            vmax = CRAWL_SPEED * k * (0.5 if self.noir else 1.0)      # Нуар старый — 150 px/с
            if d > vmax:
                dvx, dvy = dvx / d * vmax, dvy / d * vmax
            ax, ay = dvx - V[0], dvy - V[1]
            am = math.hypot(ax, ay)
            amax = CRAWL_ACCEL * k * h * (0.5 if self.noir else 1.0)
            if am > amax:
                ax, ay = ax / am * amax, ay / am * amax
            V[0] += ax
            V[1] += ay
            P[0] += V[0] * h
            P[1] += V[1] * h
            self.crawl_phase += 2 * math.pi * math.hypot(V[0], V[1]) * h / (110 * k)   # цикл — 110 px пути
            return
        V[1] += g * h * (0.25 if (self.shooting and self.zip) else 1.0)   # к точке нажатия — почти без падения
        if mode == "hang" and self.zip:              # подтягивается к точке, куда долго нажали
            self.L = max(55 * k, self.L - 650 * k * h)
            if self.L <= 55 * k + 0.5:
                self.zip = False
        elif mode == "hang":
            tgt = max(30 * k, min(math.hypot(G[0] - self.A[0], G[1] - self.A[1]), 430 * k))
            rate = 380 * k * h
            self.L += max(-rate, min(rate, tgt - self.L))
            V[0] += (G[0] - P[0]) * 6.0 * h
            V[1] += (G[1] - P[1]) * 2.0 * h
        reel = 0.0
        if mode == "swing":
            dx, dy = P[0] - self.A[0], P[1] - self.A[1]
            d = math.hypot(dx, dy) or 1.0
            tx, ty = -dy / d, dx / d                      # касательная, в сторону полёта
            if tx * self.dir < 0:
                tx, ty = -tx, -ty
            if math.atan2(dx, dy) * self.dir < 0.6:
                V[0] += tx * 1100 * k * h
                V[1] += ty * 1100 * k * h
            if G[1] < P[1] - 80 * k and self.L > 70 * k:          # цель выше — подтягиваемся
                reel = 260 * k
                self.L -= reel * h
            elif G[1] > P[1] + 100 * k and self.L < 400 * k:      # ниже — травим паутину
                self.L += 300 * k * h
        # в покое вис гасится быстрее, чтобы паук замер и кадры упали до 30/с
        damp = math.exp(-(0.4 if mode == "air" else (3.5 if mode == "hang" and self.calm else 0.9)) * h)
        V[0] *= damp
        V[1] *= damp
        sp = math.hypot(V[0], V[1])
        vmax = 3500 * k
        if sp > vmax:
            V[0] *= vmax / sp
            V[1] *= vmax / sp
        P[0] += V[0] * h
        P[1] += V[1] * h
        if mode in ("hang", "swing"):
            dx, dy = P[0] - self.A[0], P[1] - self.A[1]
            d = math.hypot(dx, dy)
            if d > self.L and d > 1e-6:
                nx, ny = dx / d, dy / d
                P[0], P[1] = self.A[0] + nx * self.L, self.A[1] + ny * self.L
                vr = V[0] * nx + V[1] * ny
                if vr > -reel:
                    V[0] -= nx * (vr + reel)
                    V[1] -= ny * (vr + reel)

    # --- главный цикл
    def tick(self):
        now = time.perf_counter()
        dt = min(now - self.last, 0.05)
        self.last = now
        self.frames += 1
        k = self.k

        cur = self.cursor_fn()
        moved = cur != self.prev_cur
        vx = (cur[0] - self.prev_cur[0]) / dt if dt > 0 else 0.0
        self.prev_cur = cur
        idle_before = now - self.last_move

        # время суток
        period = self.period_of(self.clock())
        if period != self.period:
            if period == "night" and self.s["seasonal"]:
                self.say("Evening already... time for pajamas.", now)
            if self.period == "night":
                self.pending_stretch = True
            self.period = period

        if moved:
            if idle_before > 120:
                self.say("Welcome back!", now)
            if idle_before > 300:
                self.active_since = now
            if self.pending_stretch and self.s["seasonal"]:
                self.pending_stretch = False
                self.stretch_until = now + 1.8
                self.say("Good morning! Coffee?", now)
            self.last_move = now
            self.meme_shown = False
            if self.meme and self.meme["phase"] != "out":
                self.meme["phase"] = "out"
                self.meme["tout"] = now
        idle = now - self.last_move
        self.calm = idle > 1.0
        if now - self.active_since > 3600:
            self.say("You have been working for an hour - stretch!", now)
            self.active_since = now
        if self.s["bubbles"] and now >= self.next_joke:
            if idle < 60 and not self.bubble:
                self.say(random.choice(NOIR_JOKES if self.noir else self.jokes), now)
            self.next_joke = now + random.uniform(1500, 2400)       # шутка раз в 25–40 мин

        # головокружение: очень быстрая тряска — 8 мазков туда-сюда (пик скорости > 2500 px/с) за 1,5 с
        if abs(vx) > 1:
            if sign(vx) != sign(self.prev_vx):
                if self.stroke_max > 2500 * k:
                    self.reversals.append(now)
                self.stroke_max = 0.0
            self.stroke_max = max(self.stroke_max, abs(vx))
            self.prev_vx = vx
        self.reversals = [t for t in self.reversals if now - t < 1.5]
        if len(self.reversals) >= 8 and now > self.dizzy_until:
            self.dizzy_until = now + 3.0
            self.reversals = []
            self.say("Whoa... my head is spinning!", now)
            self.log("dizzy")

        # цели: G — куда тянется кисть в висе, crawl_goal — куда ползёт центр тела (справа-снизу от курсора)
        scr = self.screen_at(*cur)
        com = self.st["com"]
        G = [cur[0] + 28 * k, cur[1] + 14 * k]
        Gc = [cur[0] + 30 * k, cur[1] + (com[1] - 16) * self.scale + 20 * k]
        if scr:
            sg = scr.geometry()
            for pt, mx, my in ((G, 30, 75), (Gc, 40, 45)):
                pt[0] = min(pt[0], sg.right() - mx * k)
                pt[1] = min(pt[1], sg.bottom() - my * k)
        if moved:
            self.sit_target = None
        st_ = self.sit_target
        if st_ and self.mode == "crawl":          # ползёт к кромке окна, чтобы сесть
            Gc = st_["tgt"]
            if math.hypot(Gc[0] - self.P[0], Gc[1] - self.P[1]) < 12 * k:
                self.sit_target = None
                self.start_sit(now, st_["hwnd"], st_["rect"], st_["x"])
                self.log("sit")
        self.crawl_goal = Gc

        # сон: улетает к боковой кромке окна (или экрана) и спит вниз головой, свисая на паутине
        sleep_after = IDLE_SLEEP_NIGHT if self.period == "night" else IDLE_SLEEP
        if (self.s["sleep"] and not self.noir and idle > sleep_after and not self.roost and not self.double
                and not self.meme and not self.shooting and self.mode in ("hang", "sit", "crawl")):
            self.plan_roost(cur)
        if self.roost:
            G = list(self.roost["goal"])
        want_sleep = (self.roost is not None and self.roost["arrived"] and self.mode == "hang"
                      and not self.double)
        self.sleep_f = max(0.0, min(1.0, self.sleep_f + (dt / 0.6 if want_sleep else -dt / 0.35)))
        if self.s["meme"] and idle > IDLE_MEME and not self.meme and not self.meme_shown:
            self.start_meme(now)
        self.update_meme(now)

        # двойник
        if DOUBLE_ENABLED and self.s["double"] and now >= self.next_double and not self.double:
            if not self.meme and idle < 600 and self.mode == "hang":
                self.start_double(now)
            else:
                self.next_double = now + 20

        # клик -> паутина
        down = self.mouse_fn()
        if down and not self.mouse_down:
            self.press = dict(t=now, pos=cur, zip=False, moved=False)
            if self.parked() and self.hit_hero(cur):
                self.wake(now)
        pr = self.press
        if pr and math.hypot(cur[0] - pr["pos"][0], cur[1] - pr["pos"][1]) >= 12 * k:
            pr["moved"] = True                   # потащили — это не долгое нажатие
        if down and pr and not pr["zip"] and not pr["moved"] and now - pr["t"] >= LONG_PRESS and self.s["clickweb"]:
            pr["zip"] = True                     # долгое нажатие: паутина цепляется за точку, паук летит к ней
            self.zip_to(now, pr["pos"])
        if not down and self.mouse_down and pr:
            if not pr["zip"] and self.s["clickweb"] and now - pr["t"] < LONG_PRESS:
                hw = self.hand_world()           # короткий клик — выстрел паутиной в точку клика
                self.splats.append([pr["pos"][0], pr["pos"][1], now, hw[0], hw[1]])
            self.press = None
        self.mouse_down = down
        self.splats = [s for s in self.splats if now - s[2] < 1.6]
        self.retracts = [r for r in self.retracts if now - r[2] < 0.25]

        # переходы
        stretching = now < self.stretch_until
        # в пределах одного монитора только ползает; махами на паутине — только на другой монитор
        far = scr is not None and self.screen_at(*self.P) is not scr
        dG = math.hypot(G[0] - self.P[0], G[1] - self.P[1])
        if stretching:
            pass
        elif (self.roost and not self.roost["arrived"] and not self.shooting
              and self.mode in ("hang", "sit", "crawl")):
            ra = self.roost["A"]
            if self.mode == "hang" and math.hypot(self.A[0] - ra[0], self.A[1] - ra[1]) < 6:
                self.roost["arrived"] = True
            else:
                self.start_travel(now, G)
        elif self.mode == "hang" and not self.shooting and self.sleep_f < 0.3:
            if far and not self.roost:
                self.start_travel(now, G)
            elif idle < 0.3 and dG > 55 * k:
                self.start_crawl(now)
        elif self.mode == "sit":
            self.watch_window(now, G)       # слезает только по клику на него или если окно закрыли/свернули
        elif self.mode == "crawl":
            if far:
                self.start_travel(now, G)
            elif moved:
                self.shooting = False
                self.zip = False
            elif (not self.shooting and idle > 0.7 and not self.sit_target
                  and math.hypot(Gc[0] - self.P[0], Gc[1] - self.P[1]) < 14 * k):
                if not self.try_sit(now, cur, idle):
                    hw = self.hand_world()
                    top = (scr.geometry().top() if scr else self.vrect.top()) + 4
                    self.shoot([hw[0], max(hw[1] - random.uniform(110, 150) * k, top)], True)
        elif self.mode == "swing":
            self.t_swing += dt
            th = math.atan2(self.P[0] - self.A[0], self.P[1] - self.A[1]) * self.dir
            near = dG < 200 * k
            if ((th > 0.5 and self.V[0] * self.dir > 0) or self.t_swing > 1.3 or (near and th > 0.15)
                    or self.L <= 72 * k):
                self.release(now)
        if self.mode == "hang" and not self.shooting and not self.double:
            self.try_sit(now, cur, idle)
        if self.mode == "air":
            self.t_air += dt
            low = scr is not None and self.P[1] > scr.geometry().bottom() - 70 * k and self.V[1] > 0
            if not self.shooting and ((self.t_air > 0.42 and self.V[1] > -80 * k) or self.t_air > 0.8 or low):
                self.plan_next_web(G)

        n = max(1, int(dt * 120 + 0.5))
        for _ in range(n):
            self.physics(dt / n, G)

        if self.roost and self.roost.get("hwnd") and now - self.roost["chk"] > 0.3:
            self.roost["chk"] = now
            if window_rect(self.roost["hwnd"]) is None:      # окно, с которого он свисает, закрыли или свернули
                self.wake(now)
        self.update_noir(now)
        self.update_band(now, dt)
        self.update_double(now, dt)
        self.update_parts(now, dt)
        if self.bubble and now - self.bubble["t0"] > self.bubble["dur"]:
            self.bubble = None
        self.orient(dt, now)
        if self.mode in ("hang", "swing"):
            if self.rope is None:
                self.rope = Rope(self.A, self.P)
            d = math.hypot(self.P[0] - self.A[0], self.P[1] - self.A[1])
            self.rope.step(self.A, self.P, max(self.L, d) * 1.015 + 2 * k, dt, 2400 * k)
        else:
            self.rope = None
        self.invalidate(now)

        # частота кадров: 120 при движении, 30 в покое (висит, спит, сидит, мем стоит) — экономия CPU
        busy = (self.mode not in ("hang", "sit") or self.shooting or math.hypot(*self.V) > 12 * k
                or self.splats or self.retracts or 0 < self.sleep_f < 1 or self.parts or self.double
                or now < self.dizzy_until or stretching)
        # медленный спуск/подъём гостей на паутине (мем, гитарист) — плавно и на 60 к/с
        glide = (self.meme and self.meme["phase"] != "idle") or (self.band and self.band["phase"] != "play")
        iv = 8 if busy else (16 if glide or (self.noir_look and self.mode != "crawl" and not self.band) else 33)
        # у Нуара анимированный дым — 60 к/с; во время номера с гитаристом хватает 30 (CPU)
        if self.timer.interval() != iv:
            self.timer.setInterval(iv)

    def plan_roost(self, cur):
        """Место сна: боковая кромка активного окна (верхний угол), а без окна — край экрана. Паук вешается
        на паутине, закреплённой там, и спит вниз головой."""
        k = self.k
        scr = self.screen_at(*self.P) or self.screen_at(*cur) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        hwnd, r = foreground_window() if self.s["windows"] else (None, None)
        if hwnd and r and r[2] - r[0] >= 200 and r[3] - r[1] >= 120:
            left, top, right, _ = r
            x = left if abs(self.P[0] - left) < abs(self.P[0] - right) else right
            y = max(top, g.top() + 4) + 6 * k
        else:
            x = g.left() + 8 * k if self.P[0] < g.center().x() else g.right() - 8 * k
            y = g.top() + 4 + 0.3 * g.height()
        x = max(g.left() + 10 * k, min(g.right() - 10 * k, x))
        self.roost = dict(A=[x, y], goal=[x, y + 100 * k], arrived=False, hwnd=hwnd, chk=0.0)
        self.sit_target = None
        self.log("roost")

    def try_sit(self, now, cur, idle):
        """Пауза > 3 с — переползти на верхнюю кромку активного окна и сесть, свесив ноги. Нуар, если окна нет
        или оно развёрнуто на весь экран, садится посреди экрана."""
        noir = self.noir
        if (not self.s["windows"] and not noir) or idle < IDLE_SIT or self.meme or self.double or self.roost:
            return False
        if now - self.last_win_check < 0.5:
            return False
        self.last_win_check = now
        hwnd, r = foreground_window() if self.s["windows"] else (None, None)
        k = self.k
        ok = False
        if hwnd:
            left, top, right, bottom = r
            scr = self.screen_at(cur[0], top + 2)
            ok = (right - left >= 200 and bottom - top >= 120 and scr is not None
                  and top - scr.geometry().top() >= 70 * k)
        if ok:
            x = max(left + 40 * k, min(right - 40 * k, cur[0]))
        elif noir:
            g = (self.screen_at(*cur) or QGuiApplication.primaryScreen()).availableGeometry()
            x = max(g.left() + 60 * k, min(g.right() - 60 * k, cur[0]))
            top = float(g.center().y())
            hwnd, r = None, (x - 1, top, x + 1, top + 1)
        else:
            return False
        seat_h = (self.st["hip"][1] + 4 * self.st["hs"] - self.st["com"][1]) * self.scale
        tgt = [x, top - seat_h]                  # куда ползёт центр тела, чтобы сесть
        d = math.hypot(tgt[0] - self.P[0], tgt[1] - self.P[1])
        if d > 900 * k:
            return False
        if self.mode != "crawl":
            self.start_crawl(now)
        self.sit_target = dict(hwnd=hwnd, rect=r, x=x, tgt=tgt)
        return True

    def update_noir(self, now):
        """Старый детектив: изредка кашляет, ворчит; как только сел — номер с гитарой, пока его не прервут
        (клик по пауку, закрытие окна) — как сон у обычного паука."""
        if not self.noir:
            return
        if (self.mode == "sit" and self.sit and not self.band and not self.double and not self.meme
                and now - self.sit["t0"] > NOIR_BAND_AFTER and now >= self.next_band):
            self.start_band(now)
        quiet = self.mode in ("sit", "hang") and not self.bubble and not self.band
        if quiet and now >= self.next_cough:
            self.cough_until = now + 0.9
            self.say(random.choice(NOIR_COUGH), now)
            self.next_cough = now + random.uniform(180, 360)
        if quiet and now >= self.next_quip:
            self.say(random.choice(NOIR_JOKES + self.jokes[len(JOKES):]), now)
            self.next_quip = now + random.uniform(240, 420)

    def parked(self):
        """Спит или сидит: такого паука не будит движение мыши — только клик по нему или закрытие окна."""
        return bool(self.roost) or self.mode == "sit" or bool(self.band)

    def hit_hero(self, cur):
        pt = QPointF(*cur)
        if self.T.mapRect(QRectF(-34, 0, 68, 100)).contains(pt):
            return True
        return bool(self.band) and self.band["T"].mapRect(QRectF(-34, 0, 68, 100)).contains(pt)

    def wake(self, now):
        """Клик по пауку: встаёт и возвращается к курсору."""
        self.roost = None
        self.last_move = now
        self.end_band(now)
        self.log("wake: click")
        if self.mode == "sit":
            self.start_crawl(now)

    def watch_window(self, now, G):
        """Окно, на котором сидит паук, закрыли или свернули — спрыгнуть на паутине; потащили — тоже."""
        if now - self.last_win_check < 0.1:
            return
        self.last_win_check = now
        st = self.sit
        if not st["hwnd"]:                      # сидит посреди экрана (окна нет) — только клик
            return
        r = window_rect(st["hwnd"])
        if r is None:
            self.start_travel(now, G)
            return
        if max(abs(r[i] - st["rect"][i]) for i in (0, 1, 2)) > 2:
            self.say("Hey, careful!", now)
            self.log("window moved: jump")
            self.start_travel(now, G)

    def orient(self, dt, now):
        """Поза, поворот и отражение героя для текущего режима."""
        k = self.k
        mode = self.mode
        style = self.style
        self.trail += (max(-9.0, min(9.0, -self.V[0] / (60 * k))) - self.trail) * min(1.0, dt * 8)
        sgn = sign(self.flip)
        trail = self.trail * sgn * 2.2
        f = self.sleep_f * self.sleep_f * (3 - 2 * self.sleep_f)
        coffee = self.s["seasonal"] and self.period == "morning"
        sip = 0.0
        if coffee:
            t7 = now % 7.0
            sip = smooth((t7 - 5.0) / 0.4) - smooth((t7 - 6.3) / 0.4)
        hang = pose_hang(style, trail, "mug" if coffee else None, sip)
        rate = 14.0
        spin = 0.0
        if mode in ("hang", "swing"):
            rope = math.degrees(math.atan2(self.A[0] - self.P[0], max(1.0, self.P[1] - self.A[1])))
            rope = max(-80.0, min(80.0, rope))
            if mode == "hang":
                if abs(self.A[0] - self.P[0]) > 12 * k:
                    self.flip_target = sign(self.A[0] - self.P[0])
                if self.double and self.double["phase"] == "act":
                    target_pose = self.hero_double_pose(now)
                    self.flip_target = -self.double["side"]
                else:
                    target_pose = lerp_pose(hang, get_pose("sleep", style), f)
            else:
                self.flip_target = self.dir
                sw = SWINGS[self.swing_i % len(SWINGS)]
                target_pose = hang if sw == "hang" else get_pose(sw, style)
            rot_t = rope - 12 * sgn * (1 - f) + 180 * f      # во сне — вниз головой
        elif mode == "sit":
            target_pose = get_pose("sit", style)
            sw = math.sin(now * 3.0) * 14
            target_pose["rl"] = (target_pose["rl"][0], target_pose["rl"][1] + sw)
            target_pose["ll"] = (target_pose["ll"][0], target_pose["ll"][1] - sw)
            if coffee:
                target_pose["la"] = hang["la"]
                target_pose["hl"] = "mug"
                target_pose["lafs"] = hang.get("lafs", 1.0)
                target_pose["front"] = hang["front"].replace("r", "")
            rot_t = 0.0
            if self.band and self.band["phase"] == "play":
                rot_t = 3.0 * math.sin(now * 2.2 + 1.0)      # поёт — покачивается в такт гитаре
        elif mode == "crawl":
            # корпус разворачивается плавно по сглаженной скорости; руки и ноги ставит IK (см. ниже)
            self.vs = [self.vs[0] + (self.V[0] - self.vs[0]) * min(1.0, dt * 10),
                       self.vs[1] + (self.V[1] - self.vs[1]) * min(1.0, dt * 10)]
            sp = math.hypot(*self.vs)
            target_pose = pose_crawl(style)
            self.flip_target = 1.0              # вид со спины: левая рука героя — слева, как в схеме походки
            rot_t = math.degrees(math.atan2(self.vs[0], -self.vs[1])) if sp > 30 * k else self.rot
            rate = 9.0
        else:  # air
            vel = math.degrees(math.atan2(self.V[0], -self.V[1]))
            if self.shooting:                     # тянется к выстреленной паутине
                target_pose = hang
                rot_t = math.degrees(math.atan2(self.tip[0] - self.P[0], self.P[1] - self.tip[1])) - 12 * sgn
                self.flip_target = sign(self.tip[0] - self.P[0])
                rate = 12.0
            elif self.trick in ("flip", "backflip"):        # сальто вперёд / назад за 0.42 с
                if self.t_air < 0.42:
                    spin = self.dir * 860 * (1 if self.trick == "flip" else -1)
                    target_pose = get_pose("tuck", style)
                else:
                    target_pose = get_pose("star", style)
                rot_t = vel
            elif self.trick == "corkscrew":                  # винт: разворот вокруг продольной оси
                target_pose, rot_t = get_pose("reach", style), vel
                self.flip_target = math.cos(self.t_air * 2 * math.pi / 0.4) * self.dir
                self.flip = self.flip_target
            elif self.trick == "tuck":
                spin, target_pose, rot_t = self.dir * 900, get_pose("tuck", style), self.rot
            elif self.trick == "star":
                target_pose, rot_t = get_pose("star", style), self.dir * 12
            else:  # reach
                target_pose, rot_t = get_pose("reach", style), vel
                self.flip_target = self.dir
        if now < self.stretch_until and mode in ("hang", "sit", "crawl"):
            target_pose = get_pose("stretch", style)
        if spin:
            self.rot += spin * dt
        else:
            self.rot += wrap180(rot_t - self.rot) * min(1.0, dt * rate)
        self.flip += max(-dt * 9, min(dt * 9, self.flip_target - self.flip))
        self.pose = lerp_pose(self.pose, target_pose, min(1.0, dt * 14))
        self.J = fk(style, self.pose)
        com = self.st["com"]
        if mode in ("hang", "swing"):
            rh, lh = self.J["rh"], self.J["lh"]     # висит на правой руке; во сне держится обеими у пояса
            self.att = (lerp(rh[0], (rh[0] + lh[0]) / 2, f), lerp(rh[1], (rh[1] + lh[1]) / 2, f))
        elif mode == "sit":
            self.att = (0.0, self.st["hip"][1] + 4 * self.st["hs"])
        else:
            self.att = com
        s = self.scale
        fl = self.flip if abs(self.flip) > 0.08 else 0.08 * sign(self.flip)
        wob = 14 * math.sin(now * 9) * min(1.0, (self.dizzy_until - now) / 0.5) if now < self.dizzy_until else 0
        if now < self.cough_until:
            wob = 5 * math.sin(now * 38)
        self.T = (QTransform().translate(self.P[0], self.P[1]).rotate(self.rot + wob).scale(s * fl, s)
                  .translate(-self.att[0], -self.att[1]))
        if mode == "crawl":
            self.crawl_ik()
        dozing = mode == "sit" and self.s["sleep"] and not self.noir and now - self.last_move > (
            IDLE_SLEEP_NIGHT if self.period == "night" else IDLE_SLEEP)
        if now < self.dizzy_until:
            self.eyes = "dizzy"
        elif self.sleep_f > 0.5:
            self.eyes = "sleep"                     # спит на паутине вниз головой
        elif dozing:
            self.eyes = "sleep"
        elif now < self.stretch_until or mode == "crawl":
            self.eyes = "squint"
        else:
            self.eyes = "open"
        self.dozing = dozing

    def head_center(self):
        return (0.0, 29.0)

    def invalidate(self, now):
        k = self.k
        rects = []
        R = 115 * self.scale + 16
        hero = QRectF(self.P[0] - R, self.P[1] - R, 2 * R, 2 * R)
        if self.sleep_f > 0.9 or getattr(self, "dozing", False):
            hero = hero.united(QRectF(self.P[0] - R, self.P[1] - R - 30 * k, 2 * R + 50 * k, 2 * R + 30 * k))
        rects.append(hero)

        def seg(a, b):
            m = 8 + 0.07 * math.hypot(b[0] - a[0], b[1] - a[1])      # запас на провисание нити
            rects.append(QRectF(QPointF(min(a[0], b[0]) - m, min(a[1], b[1]) - m),
                                QPointF(max(a[0], b[0]) + m, max(a[1], b[1]) + 40 * k + m)))

        if self.mode in ("hang", "swing"):
            seg(self.A, self.P)
            rects.append(QRectF(self.A[0] - 14 * k, self.A[1] - 6, 28 * k, 26 * k))   # конус крепления
            if self.rope:                                                            # изгиб нити
                xs = [q_[0] for q_ in self.rope.p]
                ys = [q_[1] for q_ in self.rope.p]
                m = 10 * k
                rects.append(QRectF(min(xs) - m, min(ys) - m, max(xs) - min(xs) + 2 * m, max(ys) - min(ys) + 2 * m))
        if self.shooting:
            seg(self.tip, self.P)
        for a, b, t0 in self.retracts:
            seg(a, b)
        for sx, sy, t0, px, py in self.splats:
            r = 24 * k
            rects.append(QRectF(QPointF(min(sx, px) - r, min(sy, py) - r), QPointF(max(sx, px) + r, max(sy, py) + r)))
        d = self.double
        if d:
            Rd = 150 * self.scale + 16
            rects.append(QRectF(d["x"] - Rd, d["top"] - 10, 2 * Rd, d["y"] - d["top"] + Rd + 20))
        b = self.band
        if b:
            Rb = 150 * self.scale + 16
            rects.append(QRectF(b["x"] - Rb, b["top"] - 10, 2 * Rb, b["y"] - b["top"] + Rb + 20))
        for f in self.parts:
            rects.append(QRectF(f["x"] - 40, f["y"] - 40, 80, 80))
        if self.bubble:
            self.bubble_rect = self.layout_bubble()
            if self.bubble_rect:
                rects.append(self.bubble_rect[0].adjusted(-4, -4, 4, 40))
        if self.meme:
            m = self.meme
            for f in m["figs"]:
                sm = m["H"] * f["sc"] / 104
                y0 = m["top"] if f.get("hold", 0) > 0 else f["feet"] - 150 * sm
                rects.append(QRectF(f["x"] - 80 * sm, y0 - 4, 160 * sm, f["feet"] + 14 * sm - y0 + 8))
        for r in self.prev_rects + rects:
            ri = r.toAlignedRect()
            for o in self.overlays:
                x = ri.intersected(o.geo)
                if not x.isEmpty():
                    o.update(x.translated(-o.geo.topLeft()))
        self.prev_rects = rects

    def layout_bubble(self):
        b = self.bubble
        k = self.k
        self.bfont.setPixelSize(int(13 * max(1.0, min(1.5, k))))
        fm = QFontMetrics(self.bfont)
        tr = fm.boundingRect(QRect(0, 0, 220, 1000), Qt.TextWordWrap, b["text"])
        w, h = tr.width() + 18, tr.height() + 12
        # точка над головой (или над ногами, если висит вниз головой)
        pts = [self.world(self.head_center()), self.world(self.J["feet"])]
        ax, ay = min(pts, key=lambda q: q[1])
        ay -= 34 * self.scale
        x = ax - w / 2
        y = ay - h - 12
        scr = self.screen_at(ax, ay) or QGuiApplication.primaryScreen()
        g = scr.geometry()
        x = max(g.left() + 4, min(g.right() - w - 4, x))
        if y < g.top() + 4:
            y = g.top() + 4
        return QRectF(x, y, w, h), (ax, ay)

    # --- отрисовка
    def paint(self, p):
        if self.frames == 0:   # до первого шага физики положение ещё не посчитано
            return
        now = self.last
        k = self.k
        wl = max(1.0, k * 0.85)
        if self.meme:
            self.paint_meme(p, now)
        if self.double:
            self.paint_double(p, now)
        if self.band:
            self.paint_band(p, now)
        for a, b, t0 in self.retracts:     # отпущенная паутина втягивается к точке крепления
            u = min(1.0, (now - t0) / 0.22)
            draw_web_line(p, QPointF(*a), QPointF(lerp(b[0], a[0], u), lerp(b[1], a[1], u)), wl,
                          alpha=int(255 * (1 - u)))
        P = QPointF(*self.P)
        if self.mode in ("hang", "swing") and self.rope:
            draw_web_rope(p, self.rope.p, wl, cone=11 * k, phase=now * 0.7)
        if self.shooting:          # летящая нить чуть провисает
            hw = self.hand_world()
            dx, dy = self.tip[0] - hw[0], self.tip[1] - hw[1]
            sag = 0.05 * math.hypot(dx, dy)
            pts = [(self.tip[0] - dx * i / 8, self.tip[1] - dy * i / 8 + sag * 4 * (i / 8) * (1 - i / 8)) for i in range(9)]
            draw_web_rope(p, pts, wl, phase=now * 0.7)
        p.save()
        p.setTransform(self.T, True)
        # ползёт по стене — виден со спины (голова вперёд, лица не видно)
        draw_spider(p, self.costume, self.pose, self.eyes, "top" if self.mode == "crawl" else "front",
                    style=self.style, hat=self.hat, t=now, J=self.J)
        if self.noir_look and self.mode != "crawl":
            # дым и огонёк сигареты анимируются каждый кадр (преобразование героя уже применено)
            draw_smoke(p, now, max(0.0, (self.cough_until - now) / 0.9))
        p.restore()
        if now < self.dizzy_until:
            self.paint_dizzy_stars(p, now)
        if self.sleep_f > 0.95 or getattr(self, "dozing", False):
            hw = self.world(self.head_center())
            for i in range(3):
                ph = (now * 0.55 + i / 3) % 1.0
                x = hw[0] + (24 + 12 * ph + 3 * math.sin(ph * 9)) * k
                y = hw[1] - (6 + 46 * ph) * k
                a = math.sin(ph * math.pi)
                self.font.setPixelSize(max(6, int((9 + 9 * ph) * k)))
                p.setFont(self.font)
                p.setPen(QColor(0, 0, 0, int(120 * a)))
                p.drawText(QPointF(x + 1, y + 1), "z")
                p.setPen(QColor(255, 255, 255, int(255 * a)))
                p.drawText(QPointF(x, y), "z")
        for sx, sy, t0, px, py in self.splats:
            age = now - t0
            if age < 0.08:
                tip = QPointF(lerp(px, sx, age / 0.08), lerp(py, sy, age / 0.08))
                draw_web_line(p, QPointF(px, py), tip, 0.9)
            else:
                r = 16 * k * min(1.0, (age - 0.08) / 0.12)
                alpha = 1.0 - max(0.0, (age - 0.7) / 0.9)
                draw_splat(p, sx, sy, r, alpha)
        self.paint_parts(p, now)
        if self.bubble:
            self.paint_bubble(p, now)

    def paint_dizzy_stars(self, p, now):
        hc = self.head_center()
        rx = 30
        p.setPen(QPen(QColor(90, 60, 0), 0.8))
        p.setBrush(QColor("#ffd60a"))
        for i in range(3):
            a = now * 5 + i * 2.094
            w = self.world((hc[0] + rx * math.cos(a), hc[1] - 14 + rx * 0.25 * math.sin(a)))
            r = 4.5 * self.k
            pts = [QPointF(w[0] + (r if j % 2 == 0 else r * 0.45) * math.cos(j * math.pi / 5 - math.pi / 2),
                           w[1] + (r if j % 2 == 0 else r * 0.45) * math.sin(j * math.pi / 5 - math.pi / 2))
                   for j in range(10)]
            p.drawPolygon(QPolygonF(pts))

    def paint_double(self, p, now):
        d = self.double
        if d["J"] is None:
            return
        hand = d["T"].map(QPointF(*d["J"]["rh"]))
        draw_web_line(p, QPointF(d["x"], d["top"]), hand, max(1.0, self.k * 0.85))
        p.save()
        p.setTransform(d["T"], True)
        draw_spider(p, COSTUME_BY_KEY[d["key"]], d["pose"], "open", "front", style=self.style, t=now, J=d["J"])
        p.restore()

    def paint_parts(self, p, now):
        for f in self.parts:
            age = (now - f["t0"]) / f["life"]
            if f["kind"] == "burst":
                r = 6 + 22 * age
                p.setPen(QPen(QColor(255, 214, 10, int(255 * (1 - age))), 2.2))
                for j in range(8):
                    a = j * math.pi / 4
                    p.drawLine(QPointF(f["x"] + r * 0.45 * math.cos(a), f["y"] + r * 0.45 * math.sin(a)),
                               QPointF(f["x"] + r * math.cos(a), f["y"] + r * math.sin(a)))
            else:
                p.save()
                p.translate(f["x"], f["y"])
                p.rotate(f["rot"])
                a = int(255 * (1 - max(0.0, age - 0.6) / 0.4))
                p.setPen(QPen(QColor(120, 130, 150, a), 0.7))
                p.setBrush(QColor(255, 255, 255, a))
                p.drawEllipse(QPointF(0, 0), 5 * self.k, 1.8 * self.k)
                p.drawLine(QPointF(-5 * self.k, 0), QPointF(5 * self.k, 0))
                p.restore()

    def paint_bubble(self, p, now):
        b = self.bubble
        lay = self.bubble_rect or self.layout_bubble()
        rect, (ax, ay) = lay
        age = now - b["t0"]
        a = min(1.0, age / 0.15, max(0.0, (b["dur"] - age) / 0.4))
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        tx = max(rect.left() + 12, min(rect.right() - 12, ax))
        tail = QPainterPath(QPointF(tx - 7, rect.bottom() - 1))
        tail.lineTo(ax, ay - 2)
        tail.lineTo(tx + 7, rect.bottom() - 1)
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(QColor(30, 30, 40, int(230 * a)), 1.6))
        p.setBrush(QColor(255, 255, 255, int(240 * a)))
        p.drawPath(path)
        p.setFont(self.bfont)
        p.setPen(QColor(20, 20, 28, int(255 * a)))
        p.drawText(rect.adjusted(9, 6, -9, -6), Qt.TextWordWrap | Qt.AlignCenter, b["text"])

    def meme_pixmap(self, f, c, pose, eyes, hat, sm, p, part="all", tag="hang"):
        """Картинка фигуры мема в неподвижной позе (кэш по глазам и масштабу) -> аргументы drawPixmap."""
        dev = p.device()
        dpr = dev.devicePixelRatioF() if dev is not None else 1.0
        ck = (tag, eyes, round(sm * dpr, 3), hat)
        cache = f.setdefault("cache", {})
        pm = cache.get(ck)
        if pm is None:
            s2 = sm * dpr
            pm = QPixmap(int(BASE_BOX.width() * s2) + 2, int(BASE_BOX.height() * s2) + 2)
            pm.fill(Qt.transparent)
            q = QPainter(pm)
            q.setRenderHint(QPainter.Antialiasing)
            q.scale(s2, s2)
            q.translate(-BASE_BOX.x(), -BASE_BOX.y())
            draw_spider(q, c, pose, eyes, f["view"], part=part, style=self.style, hat=hat)
            q.end()
            cache[ck] = pm
        return (QRectF(BASE_BOX.x(), BASE_BOX.y(), pm.width() / (sm * dpr), pm.height() / (sm * dpr)), pm,
                QRectF(pm.rect()))

    def paint_meme(self, p, now):
        m = self.meme
        top = m["top"]
        style = self.style
        hang = pose_hang(style)
        for f in m["figs"]:
            H = m["H"] * f["sc"]
            sm = H / 104
            if f["feet"] < top - 20:
                continue
            x, floor = f["x"], f["floor"]
            near = max(0.0, 1.0 - abs(floor - f["feet"]) / (H * 0.6))
            if near > 0:      # тень на «полу»
                p.setPen(Qt.NoPen)
                p.setBrush(QColor(0, 0, 0, int(70 * near)))
                p.drawEllipse(QPointF(x, floor + 3 * sm), 40 * sm, 7 * sm)
            t = now + f["ph"]
            standing = m["phase"] == "idle" and f["hold"] <= 0
            pose = pose_point(f["var"], t if standing else 0.0, style)
            bob = -1.5 * abs(math.sin(t * 4)) if standing else 0
            eyes = "squint" if (t % 4.0) < 0.9 and f["view"] != "back" else "open"
            c = COSTUME_BY_KEY[f["key"]]
            hat = self.hat if f["var"] == "left" else None
            p.save()
            p.translate(x, f["feet"])
            p.scale(sm * f["mirror"], sm)
            p.translate(0, -105 + bob)
            if f["hold"] > 0:
                # на паутине: держится правой рукой, паутина — из кулака вверх, у края экрана расходится конусом
                ps = lerp_pose(pose, hang, f["hold"])
                J = fk(style, ps)
                hand = QPointF(x + J["rh"][0] * sm * f["mirror"], f["feet"] + (J["rh"][1] - 105 + bob) * sm)
                f.setdefault("wx", hand.x())
                if f["web_u"] > 0:
                    p.restore()
                    end = QPointF(hand.x(), lerp(top, hand.y(), f["web_u"]))
                    if f["web_u"] >= 1:          # висит на нити: нить провисает и гнётся
                        a = (f["wx"], top)
                        rope = f.get("rope") or Rope(a, (end.x(), end.y()))
                        f["rope"] = rope
                        rope.step(a, (end.x(), end.y()), math.hypot(end.x() - a[0], end.y() - a[1]) * 1.012,
                                  1 / 60, 2400 * sm, now)
                        draw_web_rope(p, rope.p, max(1.2, sm * 0.9), cone=14 * sm, phase=now * 0.7)
                    else:
                        f.pop("rope", None)
                        draw_web_line(p, QPointF(f["wx"], top), end, max(1.2, sm * 0.9), cone=14 * sm)
                    p.save()
                    p.translate(x, f["feet"])
                    p.scale(sm * f["mirror"], sm)
                    p.translate(0, -105 + bob)
                if f["hold"] >= 1.0:     # спуск: поза неподвижна — фигура целиком из кэша (CPU)
                    p.drawPixmap(*self.meme_pixmap(f, c, ps, eyes, hat, sm, p))
                else:
                    draw_spider(p, c, ps, eyes, f["view"], style=style, hat=hat, t=t, J=J)
                p.restore()
                continue
            f.pop("wx", None)
            # ноги, торс и голова не двигаются — рисуются в картинку один раз; руки (тычут) — каждый кадр
            dev = p.device()
            dpr = dev.devicePixelRatioF() if dev is not None else 1.0
            ck = (eyes, round(sm * dpr, 3), style, hat)
            cache = f.setdefault("cache", {})
            pm = cache.get(ck)
            if pm is None:
                s2 = sm * dpr
                pm = QPixmap(int(BASE_BOX.width() * s2) + 2, int(BASE_BOX.height() * s2) + 2)
                pm.fill(Qt.transparent)
                q = QPainter(pm)
                q.setRenderHint(QPainter.Antialiasing)
                q.scale(s2, s2)
                q.translate(-BASE_BOX.x(), -BASE_BOX.y())
                draw_spider(q, c, pose_point(f["var"], 0.0, style), eyes, f["view"], part="base", style=style,
                            hat=hat)
                q.end()
                cache[ck] = pm
            p.drawPixmap(QRectF(BASE_BOX.x(), BASE_BOX.y(), pm.width() / (sm * dpr), pm.height() / (sm * dpr)),
                         pm, QRectF(pm.rect()))
            draw_spider(p, c, pose, eyes, f["view"], part="arms", style=style, t=t)
            p.restore()


# ----------------------------------------------------------------------------- самотест
class PMC(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]


def memory_mb():
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    kernel32.K32GetProcessMemoryInfo.argtypes = [ctypes.c_void_p, ctypes.POINTER(PMC), wintypes.DWORD]
    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    kernel32.K32GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb)
    return pmc.WorkingSetSize / 2 ** 20, pmc.PeakWorkingSetSize / 2 ** 20, pmc.PagefileUsage / 2 ** 20


def run_selftest(app, b, outdir, prefix="", sleep_demo=False, noir_demo=False, crawl_demo=False, zip_demo=False):
    """Курсор подменяется виртуальным (реальную мышь пользователя не трогаем):
    0–1 с покой; 1–4 с круг (ползёт); 4.0–5.0 с тряска (головокружение); с 5.0 с покой:
    двойник (вызов на 6 с), сидит на окне, сон, кокон в 24.6 с, мем в 34.6 с; с 38 с движение."""
    os.makedirs(outdir, exist_ok=True)
    scr = QGuiApplication.primaryScreen()
    c = scr.availableGeometry().center()
    t0 = b.t_start
    x0, y0 = c.x() - 350, c.y() + 120

    def fake():
        t = time.perf_counter() - t0
        if t < 1:
            return (x0, y0)
        if t < 4:
            a = (t - 1) * 1.2
            return (x0 + 120 * math.sin(a), y0 - 120 + 120 * math.cos(a))
        x1, y1 = x0 + 120 * math.sin(3.6), y0 - 120 + 120 * math.cos(3.6)
        if t < 5.0:
            return (x1 + 160 * math.sin((t - 4) * 2 * math.pi * 5), y1)
        if t >= 38:
            return (x1 + 150 * (t - 38), y1)
        return (x1, y1)

    b.cursor_fn = fake
    b.prev_cur = fake()
    b.mouse_fn = lambda: False          # реальные клики пользователя во время теста не учитываем
    b.P = [x0 + 26, y0 + 16]
    b.A = [x0 + 26, y0 - 134]
    # имитация активного окна (настоящие окна пользователя не трогаем): кромка над курсором, в 21 с окно сдвигают
    x1, y1 = x0 + 120 * math.sin(3.6), y0 - 120 + 120 * math.cos(3.6)
    win = {"r": (x1 - 320, y1 - 150, x1 + 280, y1 + 260)}
    globals()["foreground_window"] = lambda: (12345, win["r"])
    globals()["window_rect"] = lambda h: win["r"]

    def move_window():
        win["r"] = tuple(v + d for v, d in zip(win["r"], (60, 40, 60, 40)))
    log = {"style": b.style, "time": str(b.clock()), "costume": b.costume["key"], "hat": b.hat, "events": {}}
    marks = {}
    finished = []
    poll_extra = []

    def mark(name):
        marks[name] = (time.perf_counter(), time.process_time(), b.frames)

    def shot(name, at_cursor=False):
        cx, cy = b.cursor_fn()
        s = b.screen_at(cx, cy) if at_cursor else (b.screen_at(*b.P) or b.screen_at(cx, cy))
        s = s or scr
        pm = s.grabWindow(0)
        g = s.geometry()
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        l, t_, r, bt = win["r"]                # контур имитации окна
        p.setPen(QPen(QColor(255, 190, 0), 2, Qt.DashLine))
        p.setBrush(Qt.NoBrush)
        p.drawRect(QRectF(l - g.x(), t_ - g.y(), r - l, bt - t_))
        p.drawText(QPointF(l - g.x() + 8, t_ - g.y() + 18), "simulated window (test)")
        p.translate(cx - g.x(), cy - g.y())
        arrow = QPolygonF([QPointF(*q) for q in ((0, 0), (0, 17), (4, 13), (7, 20), (9.5, 19), (6.5, 12), (12, 12))])
        p.setPen(QPen(QColor(0, 0, 0), 1.2))
        p.setBrush(QColor(255, 255, 255))
        p.drawPolygon(arrow)   # курсор дорисован: системный курсор в снимок экрана не попадает
        p.end()
        pm.save(os.path.join(outdir, prefix + name))
        log["events"][prefix + name] = dict(t=round(time.perf_counter() - t0, 2), mode=b.mode,
                                   at=[round(b.P[0] - g.x()), round(b.P[1] - g.y())])

    def check(name):
        o = b.overlays[0]
        ex = user32.GetWindowLongPtrW
        ex.restype = ctypes.c_ssize_t
        ex.argtypes = [ctypes.c_void_p, ctypes.c_int]
        st = ex(int(o.winId()), -20)
        log["events"][name] = dict(
            t=round(time.perf_counter() - t0, 2), mode=b.mode, meme=(b.meme["phase"] if b.meme else None),
            sleep_f=round(b.sleep_f, 2), band=(b.band["phase"] if b.band else None),
            exstyle=dict(TRANSPARENT=bool(st & 0x20), LAYERED=bool(st & 0x80000),
                         TOOLWINDOW=bool(st & 0x80), TOPMOST=bool(st & 0x8)))

    def finish():
        if finished:
            return
        finished.append(1)
        mark("end")

        def seg(a, z):
            (w0, c0, f0), (w1, c1, f1) = marks[a], marks[z]
            return dict(fps=round((f1 - f0) / (w1 - w0), 1),
                        cpu_total_pct=round(100 * (c1 - c0) / (w1 - w0) / os.cpu_count(), 2))

        for key, (m0, m1) in (("crawl_1_4s", ("a", "b")), ("double_7_14s", ("c", "d")), ("calm_18_24s", ("e", "f")),
                              ("meme_36_38s", ("g", "h")), ("whole", ("a", "end"))) if not noir_demo else (
                ("noir_play1_to_play2", ("c", "e")), ("noir_play2_6s", ("e", "f")), ("whole", ("a", "end"))):
            if m0 in marks and m1 in marks and marks[m1][0] > marks[m0][0]:
                log[key] = seg(m0, m1)
        ws, peak, priv = memory_mb()
        log["memory_mb"] = dict(working_set=round(ws, 1), peak=round(peak, 1), private=round(priv, 1))
        log["modes"] = list(b.mode_log)
        log["log"] = list(b.events)
        with open(os.path.join(outdir, prefix + ("noir_" if noir_demo else "") + "selftest.json"), "w", encoding="utf-8") as fh:
            json.dump(log, fh, ensure_ascii=False, indent=1)
        print(json.dumps(log, ensure_ascii=True))
        app.quit()

    sched = [(1.0, lambda: mark("a")), (2.8, lambda: shot("1_ползёт.png")), (4.0, lambda: mark("b")),
             (5.4, lambda: shot("2_голова_кругом.png")),
             (6.0, lambda: DOUBLE_ENABLED and b.start_double(time.perf_counter(), True)), (7.0, lambda: mark("c")),
             (8.4, lambda: DOUBLE_ENABLED and shot("3_двойник.png")), (14.0, lambda: mark("d")),
             (18.0, lambda: mark("e")), (20.5, lambda: shot("4_сидит_на_окне.png")), (21.0, move_window),
             (21.25, lambda: shot("4б_окно_сдвинули.png")), (24.0, lambda: mark("f")),
             (32.0, lambda: check("at_32s")),
             (34.6, lambda: b.start_meme(time.perf_counter())),     # мем по таймеру — через 10 мин, в тесте вызов
             (36.0, lambda: mark("g")), (38.0, lambda: mark("h")), (38.6, lambda: shot("6_мем.png", True)),
             (40.0, lambda: check("at_40s")), (40.2, finish)]
    if sleep_demo:      # сон: 5 с покоя -> улетает к боковой кромке окна и висит вниз головой
        sched = [(1.0, lambda: mark("a")), (4.0, lambda: shot("s1_до_сна.png")), (5.9, lambda: shot("s2_летит.png")),
                 (6.5, lambda: shot("s3_летит.png")), (7.5, lambda: shot("s4_летит.png")),
                 (11.0, lambda: shot("s5_спит.png")), (11.5, lambda: check("sleep")), (11.7, finish)]
    watch = []          # (имя, условие, действие) — снимки по событиям, а не по часам
    if noir_demo:       # режим Noir: садится, через NOIR_BAND_AFTER прилетает гитарист; потом клик по пауку
        # тестовый файл со служебными строками (не текст песни): проверка, что строки идут по очереди
        test_lyrics = os.path.join(outdir, "noir_lyrics_test.txt")
        with open(test_lyrics, "w", encoding="utf-8") as fh:
            fh.write("# тест\nТестовая строка 1\nТестовая строка 2\n")
        missing = os.path.join(outdir, "нет_такого_файла.txt")
        b.lyrics_path = lambda: test_lyrics if time.perf_counter() - t0 > 20 else missing
        st_ = {}

        def band_phase():
            return b.band["phase"] if b.band else None

        def once(name, cond, act):
            watch.append((name, cond, act))

        def hit_and_wake():
            hw = b.world((0, 40))
            b.cursor_fn = lambda: (hw[0], hw[1])          # курсор «над пауком», как при клике
            log["events"]["hit_hero"] = bool(b.hit_hero(b.cursor_fn()))
            b.wake(time.perf_counter())
            b.next_band = 0.0
            st_["woke"] = time.perf_counter()
        once("sit", lambda: b.mode == "sit", lambda: shot("noir_n1_сидит.png"))
        once("in", lambda: band_phase() == "in" and time.perf_counter() - b.band["t0"] > 1.3,
             lambda: shot("noir_n2_гитарист_спускается.png"))
        once("play", lambda: band_phase() == "play" and b.bubble is not None
             and time.perf_counter() - b.bubble["t0"] > 0.6,
             lambda: (shot("noir_n3_поёт_подпись.png"), check("noir_play1"), mark("c")))
        once("wake", lambda: "c" in marks and time.perf_counter() - t0 > 21, hit_and_wake)
        once("band2", lambda: "woke" in st_ and band_phase() == "play" and b.bubble is not None
             and b.bubble["text"].startswith("Тестовая") and time.perf_counter() - b.bubble["t0"] > 0.6,
             lambda: (shot("noir_n4_поёт_строки.png"), check("noir_play2"), mark("e")))
        once("end", lambda: "e" in marks and time.perf_counter() - marks["e"][0] > 6,
             lambda: (mark("f"), check("noir_end"), finish()))
        b.next_band = 0.0
        sched = [(1.0, lambda: mark("a")), (90.0, finish)]
    if crawl_demo:      # ползание: ~8 с непрерывного движения во все стороны, замер суставов каждый кадр
        frames = []
        orig_ik = b.crawl_ik

        def rec_ik():
            orig_ik()
            J = b.J
            st = b.st
            ext = {}
            for key, (s0, s1, l1, l2) in (("ra", ("rs", "rw", st["ua"], st["fa"])), ("la", ("ls", "lw", st["ua"], st["fa"])),
                                          ("rl", ("rp", "rn", st["th"], st["sn"])), ("ll", ("lp", "ln", st["th"], st["sn"]))):
                ext[key] = math.hypot(J[s1][0] - J[s0][0], J[s1][1] - J[s0][1]) / (l1 + l2)
            frames.append(dict(bend=joint_bends(J), ext=ext, sin=math.sin(b.crawl_phase), flip=b.flip))
        b.crawl_ik = rec_ik
        shots = {}
        cx0, cy0 = x0 + 200, y0 - 150

        def fake_c():
            t = time.perf_counter() - t0
            if t < 1:
                return (x0, y0)
            u = t - 1
            if u < 5:                                   # круг: ползёт во всех направлениях
                a_ = u * 1.25
                return (cx0 + 230 * math.sin(a_), cy0 - 230 * math.cos(a_) + 230)
            return (cx0 + 230 * math.sin(6.25) - 160 * (u - 5), cy0 - 230 * math.cos(6.25) + 230)   # прямая влево
        b.cursor_fn = fake_c
        b.prev_cur = fake_c()
        win["r"] = (-10000, -10000, -9000, -9000)       # окна нет — не садится

        def grab_phase(tag, want):
            if (b.mode == "crawl" and tag not in shots and time.perf_counter() - t0 > 2.0
                    and math.sin(b.crawl_phase) * want > 0.985):
                shots[tag] = round(time.perf_counter() - t0, 2)
                shot("ползание_фаза_%s_экран.png" % tag)
        poll_extra.append(lambda: grab_phase("A", 1))
        poll_extra.append(lambda: grab_phase("B", -1))

        def crawl_finish():
            mark("b")
            n = len(frames)
            keys = ("ra", "la", "rl", "ll")
            rev = {k: sum(1 for f in frames if f["bend"][k] <= 0) for k in keys}
            rng = {k: [round(min(f["bend"][k] for f in frames), 1), round(max(f["bend"][k] for f in frames), 1)]
                   for k in keys}
            # перекрёстная походка: где руки заметно разведены, нога той же стороны — наоборот
            sig = [f for f in frames if abs(f["ext"]["la"] - f["ext"]["ra"]) > 0.15]
            cross_ok = sum(1 for f in sig if (f["ext"]["la"] > f["ext"]["ra"]) == (f["ext"]["ll"] < f["ext"]["rl"]))
            a_ok = sum(1 for f in sig if (f["sin"] > 0) == (f["ext"]["la"] > f["ext"]["ra"]))
            seq = [1 if f["sin"] > 0.9 else (-1 if f["sin"] < -0.9 else 0) for f in frames]
            seq = [v for v in seq if v]
            switches = sum(1 for p_, q_ in zip(seq, seq[1:]) if p_ != q_)
            log["crawl"] = dict(frames=n, reverse_bend_frames=rev, bend_range_deg=rng,
                                cross_frames=len(sig), cross_pattern_ok=cross_ok,
                                phaseA_left_arm_straight_ok=a_ok, phase_switches_A_B=switches,
                                flip_min=round(min(f["flip"] for f in frames), 2) if n else None, shots=shots)
            finish()
        sched = [(1.0, lambda: mark("a")), (9.0, crawl_finish)]
    if zip_demo:        # долгое нажатие: курсор в точку, кнопка зажата 0,7 с -> паутина цепляется, паук летит к ней
        tx, ty = x0 + 420, y0 - 380
        win["r"] = (-10000, -10000, -9000, -9000)
        b.cursor_fn = lambda: (x0, y0) if time.perf_counter() - t0 < 1.5 else (tx, ty)
        b.mouse_fn = lambda: 1.6 <= time.perf_counter() - t0 < 2.3
        track = []
        poll_extra.append(lambda: track.append((round(time.perf_counter() - t0, 2), b.mode, round(math.hypot(
            b.P[0] - tx, b.P[1] - ty)), b.rope is not None)))

        def zip_finish():
            ev = [e for e in b.events if e[1] == "zip"]
            hang = [tr for tr in track if tr[1] == "hang" and tr[0] > 2.0]
            log["zip"] = dict(zip_event=ev, first_hang_t=hang[0][0] if hang else None,
                              dist_to_point_end=track[-1][2], anchor=[round(v) for v in b.A], target=[tx, ty],
                              mode_end=track[-1][1], rope_end=track[-1][3])
            finish()
        zs = {}

        def zip_shots():
            if b.shooting and "1" not in zs and b.zip:
                zs["1"] = 1
                shot("zip_1_летит_нить.png", True)
            if b.mode == "hang" and b.zip and "2" not in zs and b.L < 0.6 * math.hypot(b.P[0] - tx, b.P[1] - ty) + 200:
                zs["2"] = 1
                shot("zip_2_подтягивается.png", True)
        poll_extra.append(zip_shots)
        sched = [(1.0, lambda: mark("a")), (3.6, lambda: shot("zip_3_висит_в_точке.png", True)),
                 (3.7, lambda: mark("b")), (3.8, zip_finish)]
    poll = QTimer(app)
    poll.setTimerType(Qt.PreciseTimer)

    def run_due():
        while sched and time.perf_counter() - t0 >= sched[0][0]:
            sched.pop(0)[1]()
        for item in list(watch):
            if item[1]():
                watch.remove(item)
                item[2]()
        for fn_ in poll_extra:
            fn_()

    poll.timeout.connect(run_due)
    poll.start(10)


# ----------------------------------------------------------------------------- запуск
def main():
    argv = sys.argv
    selftest = "--selftest" in argv
    if not selftest:
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = ctypes.c_void_p
        main.mutex = k32.CreateMutexW(None, False, "Local\\SpiderPal_single_instance")
        if ctypes.get_last_error() == 183:   # ERROR_ALREADY_EXISTS — уже запущен
            return
    overrides = {}
    if selftest:
        overrides["sleep"] = "--sleep" in argv      # обычный самотест — без сна (уводит паука с окна)
    if "--noir" in argv:
        overrides["noir_mode"] = True
    if "--size" in argv:
        overrides["size"] = float(argv[argv.index("--size") + 1])      # обычный самотест — без сна (он уводит паука с окна); --sleep — только сон
    fake_time = None
    if "--time" in argv:
        fake_time = datetime.datetime.strptime(argv[argv.index("--time") + 1], "%Y-%m-%d %H:%M")
    app = QApplication(argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName(APP_NAME)
    b = Buddy(app, selftest=selftest, overrides=overrides, fake_time=fake_time)
    if selftest:
        i = argv.index("--selftest")
        out = argv[i + 1] if len(argv) > i + 1 else os.path.join(app_dir(), "скриншоты")
        prefix = argv[argv.index("--prefix") + 1] if "--prefix" in argv else ""
        run_selftest(app, b, out, prefix, "--sleep" in argv, "--noir" in argv, "--crawl" in argv, "--zip" in argv)
    app.exec()


if __name__ == "__main__":
    main()
