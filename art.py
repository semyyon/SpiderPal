# -*- coding: utf-8 -*-
"""Рисовка персонажа: чиби-паук с большой головой. Всё векторно через QPainter, без картинок.

Система координат модели: макушка y=0, подошвы y~104, ось x вправо, плечи (±14, 55), бёдра (±7, 79).
Голова — эллипс 64×58 (≈56 % роста). Голова и торс не зависят от позы и рисуются в кэш-картинки;
руки, ноги и кисти — каждый кадр.
Виды: front — спереди; back — со спины (кусочек линзы из-за края головы, для мема); top — со спины
при ползании по стене (лица не видно).
"""
import math

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (QPainter, QColor, QPen, QPainterPath, QPixmap, QTransform, QPolygonF,
                           QLinearGradient, QRadialGradient)

# ----------------------------------------------------------------------------- костюмы
# main — основной цвет (у классики красный), second — бока/спина/ноги (синий), web — линии паутины,
# emblem — паук на груди, back — паук на спине
COSTUMES = [
    dict(key="classic", name="Classic", main="#d7262f", second="#1f4fb6", web="#5c0d12",
         emblem="#151515", back="#d7262f", eye="#ffffff", rim="#1a0a0c"),
    dict(key="black", name="Black", main="#262632", second="#17171e", web="#5c5c72",
         emblem="#f4f4f4", back="#f4f4f4", eye="#ffffff", rim="#000000"),
    dict(key="punk", name="Spider-Punk", main="#e2336b", second="#1c1c1c", web="#3a0a1c",
         emblem="#1c1c1c", back="#e2336b", eye="#fff4c9", rim="#0d0d0d", mohawk="#3dff6e"),
    dict(key="neon", name="Cyber Neon", main="#191b3d", second="#0b0c1e", web="#00e5ff",
         emblem="#ff2bd6", back="#ff2bd6", eye="#d8fdff", rim="#00c8e8"),
    dict(key="gold", name="Gold", main="#e7ae22", second="#2c2219", web="#7a5303",
         emblem="#2c2219", back="#e7ae22", eye="#ffffff", rim="#2c2219"),
    dict(key="arctic", name="Arctic", main="#f1f5f9", second="#3d8fd6", web="#9db4c9",
         emblem="#3d8fd6", back="#f1f5f9", eye="#c7ecff", rim="#22405c"),
    dict(key="toxic", name="Toxic", main="#7fd321", second="#5a2a87", web="#2e5a06",
         emblem="#5a2a87", back="#7fd321", eye="#ffffff", rim="#1d0d2b"),
    # Нуар: графитовый костюм, маска поднята до носа (видна нижняя часть лица), всегда с сигаретой
    dict(key="noir", name="Spider-Noir", main="#4b4e56", second="#1c1d22", web="#9097a2",
         emblem="#868b95", back="#868b95", eye="#efebdc", rim="#08080a", scuff="#ffffff",
         lowface=True, hooded=True),
    # сезонные (включаются сами, если в меню включены «Праздники и время суток»; можно выбрать и вручную)
    dict(key="pajama", name="Pajamas (night)", main="#9cc3ee", second="#f1ead8", web="#ffffff",
         emblem="#3c5a8c", back="#3c5a8c", eye="#ffffff", rim="#2a3f63"),
    dict(key="newyear", name="New Year (December)", main="#c8102e", second="#17703f", web="#f6e7b0",
         emblem="#f6e7b0", back="#f6e7b0", eye="#ffffff", rim="#3a0710"),
    dict(key="halloween", name="Halloween (Oct 31)", main="#ff7a00", second="#1a1a1a", web="#2a1200",
         emblem="#1a1a1a", back="#1a1a1a", eye="#c6ff3b", rim="#120800"),
]
COSTUME_BY_KEY = {c["key"]: c for c in COSTUMES}

WHITE, BLACK = QColor(255, 255, 255), QColor(0, 0, 0)
SHADOW = QColor(0, 0, 0, 58)
HILITE = QColor(255, 255, 255, 75)


def mix(a, b, t):
    return QColor(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
                  int(a.blue() + (b.blue() - a.blue()) * t), int(a.alpha() + (b.alpha() - a.alpha()) * t))


def _alpha(c, a):
    return QColor(c.red(), c.green(), c.blue(), a)


for _c in COSTUMES:
    q = {k: QColor(v) for k, v in _c.items() if isinstance(v, str) and v.startswith("#")}
    for k in ("main", "second"):
        q[k + "L"] = mix(q[k], WHITE, 0.32)
        q[k + "D"] = mix(q[k], BLACK, 0.38)
    q["eyeD"] = mix(q["eye"], QColor("#8ea3ba"), 0.5)
    q["rimA"] = _alpha(q["rim"], 150)
    q["fold"] = _alpha(mix(q["main"], BLACK, 0.6), 110)      # складки и мышцы
    q["fold2"] = _alpha(mix(q["second"], BLACK, 0.6), 110)
    _c["q"] = q


def lerp(a, b, f):
    return a + (b - a) * f


def _pen(color, w):
    return QPen(color, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _mirror(path):
    return QTransform().scale(-1, 1).map(path)


# ----------------------------------------------------------------------------- готовые контуры
def _web_pattern(cx, cy, n, radii, length, rot=0.11):
    path = QPainterPath()
    angs = [2 * math.pi * i / n + rot for i in range(n)]
    for a in angs:
        path.moveTo(cx, cy)
        path.lineTo(cx + length * math.cos(a), cy + length * math.sin(a))
    for r in radii:
        for i in range(n):
            a0, a1 = angs[i], angs[(i + 1) % n] + (2 * math.pi if i == n - 1 else 0)
            am = (a0 + a1) / 2
            path.moveTo(cx + r * math.cos(a0), cy + r * math.sin(a0))
            path.quadTo(cx + 0.8 * r * math.cos(am), cy + 0.8 * r * math.sin(am),
                        cx + r * math.cos(a1), cy + r * math.sin(a1))
    return path


HEAD_C = QPointF(0, 29)
HEAD = QPainterPath()
HEAD.addEllipse(HEAD_C, 32, 29)
WEB = _web_pattern(0, 37, 14, (7, 14, 22, 31, 41, 53), 75)
WEB_BACK = _web_pattern(-6, 26, 14, (6, 13, 21, 30, 40, 52), 75)
WEB_TOP = _web_pattern(0, 22, 14, (6, 13, 21, 30, 40, 52), 75)   # затылок при виде со спины сверху


def _sym(right):
    """Замкнутый симметричный контур: right — список кривых (c1, c2, end) правой половины сверху вниз
    от точки (0, y0) до (0, y1); левая половина — зеркально."""
    start, segs = right
    path = QPainterPath(QPointF(*start))
    pts = [start]
    for c1, c2, end in segs:
        path.cubicTo(QPointF(*c1), QPointF(*c2), QPointF(*end))
        pts.append(end)
    for i in range(len(segs) - 1, -1, -1):
        c1, c2, _ = segs[i]
        end = pts[i]
        path.cubicTo(QPointF(-c2[0], c2[1]), QPointF(-c1[0], c1[1]), QPointF(-end[0], end[1]))
    path.closeSubpath()
    return path


# торс: плечи шире, к талии сужается, бёдра
TORSO = _sym(((0, 49.5), [((8, 49.5), (16, 50.5), (16.2, 56.5)),     # дельта
                          ((16.4, 62), (11.5, 66), (11, 72)),         # широчайшая -> талия
                          ((10.8, 76), (13.6, 78), (13.4, 81.5)),     # бедро
                          ((12.6, 85.5), (4.5, 88.5), (0.01, 89))]))  # таз сужается к паху, без «квадрата»
TORSO_BOX = QRectF(-19, 46, 38, 46)

# спереди: красный верх, к поясу сходится клином, красный пояс уголком вниз, синие бока и трусы
RED_FRONT = QPainterPath(QPointF(-17, 48))
for _pt in ((17, 48), (17, 57)):
    RED_FRONT.lineTo(*_pt)
RED_FRONT.cubicTo(12, 59.5, 8.5, 64, 7.2, 71.5)
RED_FRONT.lineTo(11.8, 72.8)
RED_FRONT.lineTo(12.4, 75.8)
RED_FRONT.cubicTo(7, 76.6, 3, 78.6, 0, 81.2)
RED_FRONT.cubicTo(-3, 78.6, -7, 76.6, -12.4, 75.8)
RED_FRONT.lineTo(-11.8, 72.8)
RED_FRONT.lineTo(-7.2, 71.5)
RED_FRONT.cubicTo(-8.5, 64, -12, 59.5, -17, 57)
RED_FRONT.closeSubpath()
SEAMS_FRONT = QPainterPath(QPointF(12.4, 75.8))
SEAMS_FRONT.cubicTo(7, 76.6, 3, 78.6, 0, 81.2)
SEAMS_FRONT.cubicTo(-3, 78.6, -7, 76.6, -12.4, 75.8)
SEAMS_FRONT.moveTo(7.2, 71.5)
SEAMS_FRONT.lineTo(11.8, 72.8)
SEAMS_FRONT.moveTo(-7.2, 71.5)
SEAMS_FRONT.lineTo(-11.8, 72.8)
MUSCLES_FRONT = QPainterPath()
for _sx in (1, -1):
    MUSCLES_FRONT.moveTo(1.2 * _sx, 56.5)                       # грудь
    MUSCLES_FRONT.quadTo(6.5 * _sx, 61.8, 12 * _sx, 57.2)
    for _y in (65.5, 69.2):                                     # пресс
        MUSCLES_FRONT.moveTo(1.0 * _sx, _y)
        MUSCLES_FRONT.quadTo(3.4 * _sx, _y + 0.9, 5.4 * _sx, _y - 0.3)
MUSCLES_FRONT.moveTo(0, 63)
MUSCLES_FRONT.lineTo(0, 73.5)

# со спины: красная кокетка на плечах уходит клином до середины спины, ниже синяя спина,
# красный пояс прямой, большой паук с длинными лапами на спине
RED_BACK = QPainterPath(QPointF(-17, 48))
RED_BACK.lineTo(17, 48)
RED_BACK.lineTo(17, 56)
RED_BACK.cubicTo(11, 58, 4, 63, 0, 69)
RED_BACK.cubicTo(-4, 63, -11, 58, -17, 56)
RED_BACK.closeSubpath()
BELT_BACK = QPainterPath(QPointF(-14, 73.4))
BELT_BACK.cubicTo(-5, 74.6, 5, 74.6, 14, 73.4)
BELT_BACK.lineTo(14, 76.6)
BELT_BACK.cubicTo(5, 77.8, -5, 77.8, -14, 76.6)
BELT_BACK.closeSubpath()
SEAMS_BACK = QPainterPath(QPointF(17, 56))
SEAMS_BACK.cubicTo(11, 58, 4, 63, 0, 69)
SEAMS_BACK.cubicTo(-4, 63, -11, 58, -17, 56)
MUSCLES_BACK = QPainterPath(QPointF(0, 53))
MUSCLES_BACK.lineTo(0, 72)                                     # позвоночник
for _sx in (1, -1):
    MUSCLES_BACK.moveTo(3.5 * _sx, 57)                          # лопатки
    MUSCLES_BACK.quadTo(9.5 * _sx, 58, 10.5 * _sx, 64)
TORSO_WEB = _web_pattern(0, 61.5, 10, (4.5, 9, 13.5, 18.5, 24), 30, rot=-0.31)
TORSO_WEB_BACK = _web_pattern(0, 52, 10, (4.5, 9, 13.5, 18.5), 26, rot=-0.31)


def _eye(sx):
    e = QPainterPath(QPointF(4 * sx, 40))
    e.cubicTo(QPointF(3 * sx, 30), QPointF(12 * sx, 19), QPointF(27 * sx, 20))
    e.cubicTo(QPointF(31 * sx, 29), QPointF(26 * sx, 41), QPointF(14 * sx, 44))
    e.cubicTo(QPointF(9 * sx, 45), QPointF(5 * sx, 44), QPointF(4 * sx, 40))
    return e


def _squash(path, sx, ky):
    cx, cy = 15 * sx, 43
    return QTransform().translate(cx, cy).scale(1, ky).translate(-cx, -cy).map(path)


EYES = {
    "open": (_eye(1), _eye(-1)),
    "squint": (_squash(_eye(1), 1, 0.5), _squash(_eye(-1), -1, 0.5)),
    "sleep": (_squash(_eye(1), 1, 0.16), _squash(_eye(-1), -1, 0.16)),
    # голова опущена (сон на паутине): закрытые глаза ниже, сверху видна макушка
    "bowed": (QTransform().translate(0, 4).map(_squash(_eye(1), 1, 0.14)),
              QTransform().translate(0, 4).map(_squash(_eye(-1), -1, 0.14))),
}
FACE_SIDE = QTransform().translate(10, 0).scale(0.6, 1)    # вид сбоку: черты лица — к правому краю головы
SIDE_X = 0.62                                                # вид сбоку: корпус и ноги уже
EYE_SLIVER = QTransform().translate(31, 0).scale(0.42, 1).translate(-31, 0).map(_eye(1))


def _ell(cx, cy, rx, ry, ang):
    pth = QPainterPath()
    pth.addEllipse(QPointF(0, 0), rx, ry)
    return QTransform().translate(cx, cy).rotate(ang).map(pth)


GLOSS = _ell(-15, 10, 8, 4.5, -32)
GLOSS2 = _ell(-23, 21, 2.2, 1.6, -32)


def _mohawk():
    path = QPainterPath()
    for a in range(-150, -25, 17):
        pts = []
        for da, extra in ((-8, 0), (0, 12), (8, 0)):
            r = math.radians(a + da)
            pts.append(QPointF(32 * math.cos(r) * (1 + extra / 32), 29 + 29 * math.sin(r) * (1 + extra / 29)))
        path.addPolygon(QPolygonF(pts + [pts[0]]))
    return path


MOHAWK = _mohawk()

# ----------------------------------------------------------------------------- телосложение и скелет
# Фигурка в стиле Funko Pop: огромная голова, маленькое тело (рост ~104 ед. модели).
STYLES = {
    # sh — плечо, hip — тазобедренный сустав (правые, левые зеркально); ua/fa — плечо/предплечье,
    # th/sn — бедро/голень; ar/lr — радиусы рук/ног у корня, сустава и конца; hs — масштаб кисти и стопы
    "chibi": dict(sh=(14.0, 55.5), hip=(6.8, 80.0), ua=13.5, fa=12.5, th=12.5, sn=11.5,
                  ar=(4.7, 3.7, 3.1), lr=(6.3, 4.6, 3.6), hs=1.0, com=(0.0, 62.0), px=0.62),
}


def _dir(th, sx):
    """Направление кости: th — угол от «вниз», градусы; положительный — наружу от оси тела."""
    r = math.radians(th)
    return (sx * math.sin(r), math.cos(r))


def fk(style, pose):
    """Прямая кинематика: углы позы -> точки суставов. Длины костей постоянны — руки и ноги не «ломаются»."""
    st = STYLES[style]
    J = {}
    for s, sx in (("r", 1), ("l", -1)):
        shp = (st["sh"][0] * sx, st["sh"][1])
        u, f = pose[s + "a"]
        du, df = _dir(u, sx), _dir(f, sx)
        ua = st["ua"] * pose.get(s + "afs", 1.0)          # укорочение: плечо направлено к зрителю
        el = (shp[0] + du[0] * ua, shp[1] + du[1] * ua)
        wr = (el[0] + df[0] * st["fa"], el[1] + df[1] * st["fa"])
        J[s + "s"], J[s + "e"], J[s + "w"] = shp, el, wr
        J[s + "h"] = (wr[0] + df[0] * 4.3 * st["hs"], wr[1] + df[1] * 4.3 * st["hs"])   # центр кисти
        hp = (st["hip"][0] * sx, st["hip"][1])
        t, n = pose[s + "l"]
        dt, dn = _dir(t, sx), _dir(n, sx)
        th = st["th"] * pose.get(s + "lfs", 1.0)
        kn = (hp[0] + dt[0] * th, hp[1] + dt[1] * th)
        an = (kn[0] + dn[0] * st["sn"], kn[1] + dn[1] * st["sn"])
        J[s + "p"], J[s + "k"], J[s + "n"] = hp, kn, an
    J["feet"] = ((J["rn"][0] + J["ln"][0]) / 2, max(J["rn"][1], J["ln"][1]) + 3.5 * st["hs"])
    return J


# ----------------------------------------------------------------------------- позы (углы суставов)
# ra/la — (плечо, предплечье) правой/левой руки; rl/ll — (бедро, голень). 0° — вниз, 90° — в сторону от тела,
# 180° — вверх, отрицательные — внутрь (через тело). hr/hl — кисти: fist, point, open, mug, pillow.
# front — руки поверх головы; under — руки за телом (вид со спины); legsfront — ноги поверх торса;
# *afs/*lfs — укорочение плеча/бедра (направлены к зрителю).
_BASE = dict(ra=(12, 6), la=(12, 6), rl=(6, 2), ll=(6, 2), hr="fist", hl="fist", front="", under="",
             legsfront=False)


def _pose(**kw):
    d = dict(_BASE)
    d.update(kw)
    return d


POSES = {
    "hang": _pose(ra=(115, 140), la=(12, 6), rl=(6, 2), ll=(-4, -2), front="r"),
    # сон: вниз головой, обе руки держат паутину у пояса, ноги согнуты (поза со скриншота-образца)
    "sleep": _pose(ra=(5, -35), la=(5, -35), rl=(25, 125), ll=(15, 130), rlfs=0.85, llfs=0.85),
    "star": _pose(ra=(118, 128), la=(118, 128), rl=(32, 22), ll=(32, 22), hr="open", hl="open", front="rl"),
    "tuck": _pose(ra=(25, -55), la=(25, -55), rl=(150, 12), ll=(150, 12), legsfront=True, front="rl"),
    "reach": _pose(ra=(125, 150), la=(25, 40), rl=(3, 0), ll=(-2, 0), hl="open", front="r"),
    "swing_tuck": _pose(ra=(115, 140), la=(20, 10), rl=(140, 15), ll=(140, 15), front="r", legsfront=True),
    "swing_reach": _pose(ra=(115, 140), la=(95, 105), rl=(2, 0), ll=(-2, 0), hl="open", front="r"),
    "swing_kick": _pose(ra=(115, 140), la=(20, 10), rl=(70, 85), ll=(-3, 0), front="r"),
    "stretch": _pose(ra=(140, 160), la=(140, 160), rl=(4, 0), ll=(4, 0), hr="open", hl="open", front="rl"),
    "sit": _pose(ra=(28, 12), la=(28, 12), rl=(8, 4), ll=(8, 4), rlfs=0.3, llfs=0.3, hr="open", hl="open"),
    "five": _pose(ra=(115, 140), la=(118, 135), rl=(6, 2), ll=(-4, -2), hl="open", front="rl"),
    # игра на гитаре сидя: правая рука (на экране справа) держит гриф, левая бьёт по струнам
    "guitar": _pose(ra=(70, 85), la=(-20, -35), rl=(8, 4), ll=(8, 4), rlfs=0.3, llfs=0.3, hr="fist", hl="fist",
                    front="rl", item="guitar"),
    "pillow": _pose(ra=(115, 140), la=(130, 150), rl=(6, 2), ll=(-4, -2), hl="pillow", front="rl"),
}


def get_pose(name, style="chibi"):
    return dict(POSES[name])


def pose_hang(style="chibi", trail=0.0, item=None, sip=0.0):
    """Вис на правой руке; ноги отстают по движению (trail — градусы); item='mug' — кофе в левой руке,
    sip 0..1 — поднести ко рту."""
    p = get_pose("hang", style)
    p["rl"] = (p["rl"][0] + trail, p["rl"][1] + trail * 1.3)
    p["ll"] = (p["ll"][0] - trail * 0.7, p["ll"][1] - trail)
    if item == "mug":
        a, b = (15, -100), (35, -165)
        p["la"] = (lerp(a[0], b[0], sip), lerp(a[1], b[1], sip))
        p["lafs"] = lerp(1.0, 0.45, sip)
        p["hl"] = "mug"
        if sip > 0.5:
            p["front"] = "rl"
    return p


def pose_crawl(style="chibi"):
    """Базовая поза ползущего (вид со спины); сами шаги считает crawl_targets."""
    return _pose(ra=(118, 160), la=(118, 160), rl=(58, -12), ll=(58, -12), hr="open", hl="open")


def pose_point(variant, t, style="chibi"):
    """Позы мема — как в оригинале: все трое лицом к зрителю, обе руки видны.
    mid  — средний (сзади) разводит руки: показывает на обоих;
    left — левый: вытянутая рука показывает через сцену на правого, вторая — кулак на поясе;
    back — правый: то же зеркально (рисуется с mirror=-1) — показывает на левого."""
    j = 3.0 * math.sin(t * 8)
    j2 = 3.0 * math.sin(t * 8 + 1.3)
    legs = dict(rl=(20, 6), ll=(20, 6))
    if variant == "mid":
        return _pose(ra=(72 + j, 78 + j), la=(72 + j2, 78 + j2), hr="point", hl="point", front="rl", **legs)
    # вытянутая правая рука (на экране — в сторону соседа), левая — кулак на поясе; обе поверх тела
    return _pose(ra=(94 + j, 99 + j), la=(52, -88 + j2), hr="point", hl="fist", front="rl", **legs)


def _cross(u, v):
    return u[0] * v[1] - u[1] * v[0]


# Сторона сгиба суставов в координатах модели (y вниз): знак векторного произведения (плечо×предплечье,
# бедро×голень). Локоть уходит наружу-назад (кисть впереди локтя), колено — наружу-вперёд; у левой стороны
# знак зеркальный. Другой знак — это и есть «вывернутый в обратную сторону» сустав.
BEND_SIGN = {"ra": -1, "la": 1, "rl": 1, "ll": -1}
BEND_LIMITS = (4.0, 150.0)       # сгиб сустава, градусы: от «почти прямо» до предела; 0 — неопределённая сторона


def joint_bends(J):
    """Сгиб локтей и колен, градусы: > 0 — в анатомическую сторону, < 0 — обратный выгиб (для самотеста)."""
    out = {}
    for key, names in (("ra", ("rs", "re", "rw")), ("la", ("ls", "le", "lw")),
                       ("rl", ("rp", "rk", "rn")), ("ll", ("lp", "lk", "ln"))):
        a, m, b = (J[n] for n in names)
        u = (m[0] - a[0], m[1] - a[1])
        v = (b[0] - m[0], b[1] - m[1])
        ang = math.degrees(math.atan2(_cross(u, v), u[0] * v[0] + u[1] * v[1]))
        out[key] = ang * BEND_SIGN[key]
    return out


def ik(S, Tg, L1, L2, bend):
    """Двухзвенная обратная кинематика (теорема косинусов) от сустава S к цели Tg. bend — требуемый знак
    сгиба (BEND_SIGN): из двух решений берётся только анатомическое, сгиб ограничен BEND_LIMITS —
    сустав не выпрямляется «в ноль» и никогда не выгибается в обратную сторону."""
    dx, dy = Tg[0] - S[0], Tg[1] - S[1]
    d0 = math.hypot(dx, dy) or 1e-6
    ux, uy = dx / d0, dy / d0
    lo, hi = (math.sqrt(L1 * L1 + L2 * L2 + 2 * L1 * L2 * math.cos(math.radians(a))) for a in BEND_LIMITS[::-1])
    d = max(lo, min(hi, d0))
    a = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
    W = (S[0] + ux * d, S[1] + uy * d)
    for sg in (1, -1):
        ca, sa = math.cos(sg * a), math.sin(sg * a)
        e = (S[0] + L1 * (ux * ca - uy * sa), S[1] + L1 * (ux * sa + uy * ca))
        if _cross((e[0] - S[0], e[1] - S[1]), (W[0] - e[0], W[1] - e[1])) * bend > 0:
            return e, W
    return e, W


# Ползание (вид со спины, голова вперёд = вверх), перекрёстная походка в две фазы:
# фаза A — левая рука прямая (тянется вперёд), правая согнута в локте; левая нога согнута, правая прямая;
# фаза B — зеркально. Цели — запястья и лодыжки правой стороны в координатах модели (левая — зеркально).
# Плечо (14; 55,5), руки 13,5+12,5; таз (6,8; 80), ноги 12,5+11,5.
CRAWL_ARM = {"bent": (28.0, 47.0),       # кисть впереди-сбоку плеча, локоть наружу-назад (~100°)
             "straight": (35.0, 39.0)}   # рука вытянута вперёд-наружу (упор в предел 4°)
CRAWL_LEG = {"bent": (21.0, 86.0),       # колено наружу-вперёд (~100°), «лягушка»
             "straight": (12.5, 104.5)}  # нога вытянута назад (предел 4°)


def crawl_targets(phase):
    """phase — фаза шага (рад): sin = +1 — фаза A, sin = −1 — фаза B, между ними плавный переход."""
    w = 0.5 + 0.5 * math.sin(phase)           # 1 — фаза A, 0 — фаза B
    w = w * w * (3 - 2 * w)                   # чуть дольше держит крайние позы
    tg = {}
    # f — насколько вытянута рука этой стороны; нога той же стороны — наоборот (перекрёстная походка)
    for s, sx, f in (("l", -1, w), ("r", 1, 1.0 - w)):
        a0, a1, l0, l1 = CRAWL_ARM["bent"], CRAWL_ARM["straight"], CRAWL_LEG["bent"], CRAWL_LEG["straight"]
        tg[s + "h"] = (sx * lerp(a0[0], a1[0], f), lerp(a0[1], a1[1], f))
        tg[s + "n"] = (sx * lerp(l1[0], l0[0], f), lerp(l1[1], l0[1], f))
    return tg


def crawl_joints(style, J, targets):
    """Подставить в скелет решение IK: targets — запястья/лодыжки (координаты модели)."""
    st = STYLES[style]
    for s in "rl":
        e, w = ik(J[s + "s"], targets[s + "h"], st["ua"], st["fa"], BEND_SIGN[s + "a"])
        J[s + "e"], J[s + "w"] = e, w
        dl = math.hypot(w[0] - e[0], w[1] - e[1]) or 1e-6
        J[s + "h"] = (w[0] + (w[0] - e[0]) / dl * 4.3 * st["hs"], w[1] + (w[1] - e[1]) / dl * 4.3 * st["hs"])
        kn, an = ik(J[s + "p"], targets[s + "n"], st["th"], st["sn"], BEND_SIGN[s + "l"])
        J[s + "k"], J[s + "n"] = kn, an
    J["feet"] = ((J["rn"][0] + J["ln"][0]) / 2, max(J["rn"][1], J["ln"][1]) + 3.5 * st["hs"])
    return J


def lerp_pose(a, b, f):
    out = {}
    for k, vb in b.items():
        v = a.get(k, vb)
        if isinstance(vb, tuple):
            out[k] = (lerp(v[0], vb[0], f), lerp(v[1], vb[1], f))
        elif isinstance(vb, float) and isinstance(v, (int, float)):
            out[k] = lerp(float(v), vb, f)
        else:
            out[k] = vb if f > 0.5 else v
    for k in ("rafs", "lafs", "rlfs", "llfs"):      # укорочение возвращается к 1, если в цели его нет
        if k in a and k not in b:
            out[k] = lerp(a[k], 1.0, f)
    return out

# ----------------------------------------------------------------------------- конечности
def _taper(a, b, ra, rb):
    """Конус-сегмент от a (радиус ra) до b (радиус rb): многоугольник + круги на концах."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy)
    shapes = [("e", a, ra), ("e", b, rb)]
    if ln > 1e-3:
        nx, ny = -dy / ln, dx / ln
        shapes.append(("p", QPolygonF([QPointF(a[0] + nx * ra, a[1] + ny * ra), QPointF(b[0] + nx * rb, b[1] + ny * rb),
                                       QPointF(b[0] - nx * rb, b[1] - ny * rb), QPointF(a[0] - nx * ra, a[1] - ny * ra)])))
    return shapes


def _draw_shapes(p, shapes):
    for sh in shapes:
        if sh[0] == "e":
            p.drawEllipse(QPointF(*sh[1]), sh[2], sh[2])
        else:
            p.drawPolygon(sh[1])


def _pt(a, b, t):
    return (lerp(a[0], b[0], t), lerp(a[1], b[1], t))


def _seg_frame(a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1e-6
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    if nx + ny < 0:          # n смотрит вниз-вправо — туда падает тень (свет сверху-слева)
        nx, ny = -nx, -ny
    return ln, ux, uy, nx, ny


# Профиль мышц вдоль кости: (t, радиус снаружи, радиус внутри). Снаружи — сторона от оси тела.
# Нога: бедро широкое у таза, сужается к колену; икра выпирает в верхней трети, к лодыжке тонко.
# Рука: дельта у плеча, бицепс, сужение у локтя; предплечье толще у локтя, тонкое запястье.
PROFILES = {
    "chibi": {"leg": ([(0, 6.4, 6.0), (0.45, 6.0, 5.6), (1, 4.6, 4.4)],
                      [(0, 4.5, 4.4), (0.35, 5.0, 4.9), (1, 3.6, 3.5)]),
              "arm": ([(0, 5.3, 4.4), (0.35, 4.7, 4.2), (1, 3.7, 3.6)],
                      [(0, 3.7, 3.6), (0.3, 4.0, 3.8), (1, 3.1, 3.0)])},
}


def _prof(pr, t):
    """Плавная интерполяция профиля (косинусом между опорными точками) -> (снаружи, внутри)."""
    if t <= pr[0][0]:
        return pr[0][1], pr[0][2]
    for (t0, o0, i0), (t1, o1, i1) in zip(pr, pr[1:]):
        if t <= t1:
            u = (t - t0) / (t1 - t0)
            u = (1 - math.cos(math.pi * u)) / 2
            return lerp(o0, o1, u), lerp(i0, i1, u)
    return pr[-1][1], pr[-1][2]


def _frame(a, b, sx):
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1e-6
    ux, uy = dx / ln, dy / ln
    nx, ny = -uy, ux
    if nx * sx - 0.3 * ny < 0:          # n — наружу от тела
        nx, ny = -nx, -ny
    return ux, uy, nx, ny


def _seg_path(a, b, pr, t0, t1, sx, grow=0.0):
    """Контур участка кости [t0, t1] по профилю мышц; на концах кости — скругление (сустав)."""
    ux, uy, nx, ny = _frame(a, b, sx)
    outer, inner = [], []
    n = 9
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        ro, ri = _prof(pr, t)
        ro, ri = ro + grow, ri + grow
        x, y = lerp(a[0], b[0], t), lerp(a[1], b[1], t)
        outer.append((x + nx * ro, y + ny * ro))
        inner.append((x - nx * ri, y - ny * ri))
    path = QPainterPath(QPointF(*outer[0]))
    for pt in outer[1:]:
        path.lineTo(*pt)
    if t1 >= 1.0:
        ro, ri = _prof(pr, 1.0)
        k = 1.33
        path.cubicTo(QPointF(outer[-1][0] + ux * k * (ro + grow), outer[-1][1] + uy * k * (ro + grow)),
                     QPointF(inner[-1][0] + ux * k * (ri + grow), inner[-1][1] + uy * k * (ri + grow)),
                     QPointF(*inner[-1]))
    else:
        path.lineTo(*inner[-1])
    for pt in reversed(inner[:-1]):
        path.lineTo(*pt)
    if t0 <= 0.0:
        ro, ri = _prof(pr, 0.0)
        k = 1.33
        path.cubicTo(QPointF(inner[0][0] - ux * k * (ri + grow), inner[0][1] - uy * k * (ri + grow)),
                     QPointF(outer[0][0] - ux * k * (ro + grow), outer[0][1] - uy * k * (ro + grow)),
                     QPointF(*outer[0]))
    path.closeSubpath()
    return path


def _band(a, b, pr, t0, t1, sx, side, f0, f1):
    """Полоса внутри конечности вдоль кости: side +1 снаружи / -1 внутри, f0..f1 — доля радиуса."""
    ux, uy, nx, ny = _frame(a, b, sx)
    p0, p1 = [], []
    n = 8
    for i in range(n + 1):
        t = t0 + (t1 - t0) * i / n
        ro, ri = _prof(pr, t)
        r = ro if side > 0 else ri
        x, y = lerp(a[0], b[0], t), lerp(a[1], b[1], t)
        p0.append(QPointF(x + side * nx * r * f0, y + side * ny * r * f0))
        p1.append(QPointF(x + side * nx * r * f1, y + side * ny * r * f1))
    return QPolygonF(p0 + list(reversed(p1)))


def draw_limb(p, pts, profs, fills, webs, q, sx, stripe=None, ow=2.6):
    """Конечность из двух участков (плечо-локоть-запястье или бедро-колено-лодыжка) по профилю мышц.
    fills: [(участок, t0, t1, цвет)]; webs: [(участок, t0, t1)] — сетка паутины;
    stripe: (участок, t0, t1, цвет, сторона) — продольная полоса (синяя полоса на руке)."""
    segs = [(pts[i], pts[i + 1], profs[i]) for i in range(2)]
    p.setPen(_pen(q["rim"], ow))
    p.setBrush(q["rim"])
    for a, b, pr in segs:                                  # общая обводка обоих участков
        p.drawPath(_seg_path(a, b, pr, 0.0, 1.0, sx))
    p.setPen(Qt.NoPen)
    for i, t0, t1, ck in fills:
        a, b, pr = segs[i]
        p.setBrush(q[ck])
        p.drawPath(_seg_path(a, b, pr, t0, t1, sx))
    web = QPainterPath()
    for i, t0, t1 in webs:
        a, b, pr = segs[i]
        ux, uy, nx, ny = _frame(a, b, sx)
        ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1e-6
        d = t0 * ln + 1.4
        while d < t1 * ln - 0.6:
            t = d / ln
            ro, ri = _prof(pr, t)
            x, y = a[0] + ux * d, a[1] + uy * d
            web.moveTo(x + nx * ro * 0.9, y + ny * ro * 0.9)
            web.quadTo(x + ux * (ro + ri) * 0.17, y + uy * (ro + ri) * 0.17, x - nx * ri * 0.9, y - ny * ri * 0.9)
            d += 2.6
        ro0, ri0 = _prof(pr, t0)
        c0 = (ro0 - ri0) / 2                                # продольная линия по середине мышцы
        web.moveTo(lerp(a[0], b[0], t0) + nx * c0, lerp(a[1], b[1], t0) + ny * c0)
        web.lineTo(lerp(a[0], b[0], t1) + nx * c0, lerp(a[1], b[1], t1) + ny * c0)
    if not web.isEmpty():
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(q["web"], 0.5))
        p.drawPath(web)
        p.setPen(Qt.NoPen)
    if stripe:
        i, t0, t1, ck, side = stripe
        a, b, pr = segs[i]
        p.setBrush(q[ck])
        p.drawPolygon(_band(a, b, pr, t0, t1, sx, side, 0.2, 0.85))
    for a, b, pr in segs:                                  # объём: тень снизу-справа, блик сверху-слева
        ux, uy, nx, ny = _frame(a, b, sx)
        sh = 1 if nx + ny > 0 else -1
        p.setBrush(SHADOW)
        p.drawPolygon(_band(a, b, pr, 0.05, 0.95, sx, sh, 0.35, 0.92))
        p.setBrush(HILITE)
        p.drawPolygon(_band(a, b, pr, 0.1, 0.85, sx, -sh, 0.45, 0.68))

# кисть в своей системе: x — вперёд от запястья, -y — сторона большого пальца
def _capsule(a, b, r):
    return _taper(a, b, r, r)


_PALM = QRectF(-1.0, -4.3, 8.6, 8.6)


def _hand_shapes(kind):
    """Возвращает (контурные формы, линии-детали) кисти данного вида."""
    shapes, lines = [], QPainterPath()
    if kind == "open":                                    # раскрытая ладонь, пальцы веером
        for (bx, by), ang, ln in (((7, -2.9), -24, 5.4), ((7.6, -1.0), -8, 6.3), ((7.6, 1.0), 7, 6.0),
                                  ((7.0, 2.9), 22, 4.9)):
            a = math.radians(ang)
            shapes += _capsule((bx, by), (bx + ln * math.cos(a), by + ln * math.sin(a)), 1.15)
        a = math.radians(-58)
        shapes += _capsule((2.6, -3.4), (2.6 + 5.2 * math.cos(a), -3.4 + 5.2 * math.sin(a)), 1.3)
    elif kind == "point":                                 # указательный вытянут, три поджаты, большой сверху
        shapes += _capsule((6.0, -2.7), (15.5, -3.0), 1.3)
        for y in (-0.5, 1.6, 3.5):
            shapes.append(("e", (8.0, y), 1.25))
        shapes += _capsule((2.4, -3.9), (7.6, -4.9), 1.25)
        lines.moveTo(11.2, -4.2)
        lines.lineTo(11.2, -1.8)                          # сгиб пальца
        for y in (0.55, 2.55):
            lines.moveTo(6.4, y)
            lines.lineTo(9.2, y)
    else:                                                 # кулак: костяшки и большой палец поперёк
        for y in (-2.9, -0.95, 1.0, 2.95):
            shapes.append(("e", (8.0, y), 1.35))
        shapes += _capsule((3.0, -3.8), (8.2, -3.4), 1.3)
        for y in (-1.9, 0.05, 2.0):
            lines.moveTo(6.6, y)
            lines.lineTo(9.3, y)
    return shapes, lines


_HANDS = {k: _hand_shapes(k) for k in ("open", "point", "fist")}


def _guitar_body():
    """Корпус-восьмёрка: нижняя дека шире верхней, талия между ними."""
    low = QPainterPath()
    low.addEllipse(QPointF(-8, 0), 14.5, 13)
    up = QPainterPath()
    up.addEllipse(QPointF(12, 0), 10.5, 9.6)
    waist = QPainterPath()
    waist.addRoundedRect(QRectF(0, -7.0, 9.5, 14.0), 3, 3)
    return low.united(up).united(waist)


GUITAR_BODY = _guitar_body()
GUITAR_SADDLE, GUITAR_NUT = -11.0, 50.0          # подставка (седло) и верхний порожек: мензура 61
GUITAR_FRETS = [GUITAR_NUT - (GUITAR_NUT - GUITAR_SADDLE) * (1 - 2 ** (-n / 12)) for n in range(1, 19)]


def draw_guitar(p, t=0.0):
    """Шестиструнная акустическая гитара на коленях (в координатах модели): корпус-восьмёрка с окантовкой,
    резонаторное отверстие с розеткой, подставка, гриф с ладами (по правилу 2^(n/12)) и метками, голова с
    шестью колками (3 + 3). Струны дрожат при игре."""
    p.save()
    p.translate(-4, 84)
    p.rotate(-26)
    p.scale(0.68, 0.68)
    ink = QColor("#24130a")
    # гриф (накладка из палисандра, сужается к голове) и голова с колками
    p.setPen(_pen(ink, 1.4))
    p.setBrush(QColor("#3a2416"))
    p.drawPolygon(QPolygonF([QPointF(16, -2.9), QPointF(GUITAR_NUT, -2.3), QPointF(GUITAR_NUT, 2.3), QPointF(16, 2.9)]))
    p.setBrush(QColor("#d8cfb8"))                                       # колки — по три с каждой стороны
    for i in range(3):
        x = GUITAR_NUT + 3.2 + i * 3.1
        for sy in (-1, 1):
            p.drawEllipse(QPointF(x, sy * 5.2), 1.3, 0.9)
    p.setBrush(QColor("#2b1d14"))
    p.drawPolygon(QPolygonF([QPointF(GUITAR_NUT, -2.6), QPointF(GUITAR_NUT + 11, -3.9), QPointF(GUITAR_NUT + 12, 0),
                             QPointF(GUITAR_NUT + 11, 3.9), QPointF(GUITAR_NUT, 2.6)]))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#c9c2b0"))
    for i in range(3):
        x = GUITAR_NUT + 3.2 + i * 3.1
        for sy in (-1, 1):
            p.drawEllipse(QPointF(x, sy * 2.1), 0.55, 0.55)             # штифты колков на голове
    p.setBrush(QColor("#efe8d4"))
    p.drawRect(QRectF(GUITAR_NUT - 0.6, -2.4, 1.0, 4.8))               # верхний порожек
    # корпус: обечайка тёмной обводкой, светлая окантовка, ель деки
    g = QLinearGradient(-20, -11, 20, 11)
    g.setColorAt(0, QColor("#e9b866"))
    g.setColorAt(0.55, QColor("#cf8f3e"))
    g.setColorAt(1, QColor("#8a4b17"))
    p.setPen(_pen(ink, 2.0))
    p.setBrush(g)
    p.drawPath(GUITAR_BODY)
    p.setPen(_pen(QColor("#f3e6c6"), 0.55))
    p.setBrush(Qt.NoBrush)
    p.drawPath(GUITAR_BODY)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 46))                               # блик
    p.drawEllipse(QPointF(-13, -6.5), 5.5, 2.4)
    # розетка: кольца вокруг резонаторного отверстия
    hole = QPointF(10.5, 0)
    for r, col, w in ((6.2, "#f3e6c6", 0.45), (5.5, "#5a3214", 0.6), (4.8, "#f3e6c6", 0.7)):
        p.setPen(_pen(QColor(col), w))
        p.drawEllipse(hole, r, r)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#140a04"))
    p.drawEllipse(hole, 3.9, 3.9)
    # накладка грифа заходит на верхнюю деку до розетки
    p.setPen(_pen(ink, 0.8))
    p.setBrush(QColor("#3a2416"))
    p.drawRect(QRectF(16.8, -2.9, 1.0, 5.8))
    # подставка с седлом
    p.setPen(_pen(ink, 0.7))
    p.setBrush(QColor("#2b1a0e"))
    p.drawRoundedRect(QRectF(GUITAR_SADDLE - 2.0, -6.0, 3.4, 12.0), 1.2, 1.2)
    p.setPen(_pen(QColor("#efe8d4"), 0.6))
    p.drawLine(QPointF(GUITAR_SADDLE, -3.4), QPointF(GUITAR_SADDLE, 3.4))
    # лады и метки (3, 5, 7, 9 — точка, 12 — две)
    p.setPen(_pen(QColor(222, 218, 205, 210), 0.35))
    for x in GUITAR_FRETS:
        if x > 17.5:
            hw = lerp(2.9, 2.3, (x - 16) / (GUITAR_NUT - 16))
            p.drawLine(QPointF(x, -hw), QPointF(x, hw))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#e8e1cf"))
    for n in (3, 5, 7, 9, 12):
        x = (GUITAR_FRETS[n - 1] + GUITAR_FRETS[n - 2]) / 2
        for yy in ((-1.2, 1.2) if n == 12 else (0.0,)):
            p.drawEllipse(QPointF(x, yy), 0.45, 0.45)
    # шесть струн: от седла к порожку и дальше к колкам
    p.setBrush(Qt.NoBrush)
    for i in range(6):
        y0 = -2.6 + i * 1.04
        y1 = -1.9 + i * 0.76
        wob = 0.45 * math.sin(t * 55 + i * 1.7)
        p.setPen(_pen(QColor(236, 230, 214, 215), 0.18 + 0.05 * i))
        path = QPainterPath(QPointF(GUITAR_SADDLE, y0))
        path.quadTo(QPointF(10.5, (y0 + y1) / 2 + wob), QPointF(GUITAR_NUT, y1))
        k = i if i < 3 else 5 - i
        path.lineTo(QPointF(GUITAR_NUT + 3.2 + (2 - k) * 3.1, -2.1 if i < 3 else 2.1))
        p.drawPath(path)
    p.restore()


def draw_hand(p, wrist, el, kind, q, hs=1.0, t=0.0):
    """Кисть у запястья, направление — по предплечью. kind: fist, point, open, mug (кулак + кружка),
    pillow (кулак + подушка)."""
    dx, dy = wrist[0] - el[0], wrist[1] - el[1]
    ang = math.degrees(math.atan2(dy, dx))
    ln = math.hypot(dx, dy) or 1e-6
    nx, ny = -dy / ln, dx / ln              # мировое направление локальной оси +y
    # большой палец (локальный -y): у раскрытой ладони — к оси тела, у кулака и указующей — вверх
    if kind == "open":
        flip = -1 if (-nx) * (-wrist[0]) < 0 else 1
    else:
        flip = -1 if -ny > 0 else 1
    shapes, lines = _HANDS["fist" if kind in ("mug", "pillow") else kind]
    if kind == "pillow":
        draw_pillow(p, wrist, ang, hs)
    p.save()
    p.translate(*wrist)
    p.rotate(ang)
    p.scale(hs, hs * flip)
    p.setPen(_pen(q["rim"], 2.4))
    p.setBrush(q["rim"])
    p.drawRoundedRect(_PALM, 3.6, 3.6)
    _draw_shapes(p, shapes)
    p.setPen(Qt.NoPen)
    g = QRadialGradient(QPointF(2.5, -2.5), 9)
    g.setColorAt(0, q["mainL"])
    g.setColorAt(0.55, q["main"])
    g.setColorAt(1, q["mainD"])
    p.setBrush(g)
    _draw_shapes(p, shapes)
    p.drawRoundedRect(_PALM, 3.6, 3.6)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(q["fold"], 0.55))
    p.drawPath(lines)
    p.drawLine(QPointF(0.4, -3.9), QPointF(0.4, 3.9))      # край перчатки
    p.setPen(_pen(q["web"], 0.4))
    p.drawLine(QPointF(1.5, 0), QPointF(6.2, 0))
    p.drawLine(QPointF(3.6, -3.6), QPointF(3.6, 3.6))
    p.restore()
    if kind == "mug":
        hc = (wrist[0] + dx / ln * 6 * hs, wrist[1] + dy / ln * 6 * hs)
        draw_mug(p, hc, hs, t)


MUG_BODY = QColor("#f4efe6")
COFFEE = QColor("#5a3418")


def draw_mug(p, c, hs, t):
    """Кружка кофе стоит вертикально в кулаке, над ней пар."""
    p.save()
    p.translate(c[0] + 5.5 * hs, c[1] - 1.5 * hs)
    p.scale(hs, hs)
    p.setPen(_pen(QColor("#2b2b2b"), 1.3))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(-9.5, -4.5, 7, 8), 90 * 16, 180 * 16)      # ручка
    g = QLinearGradient(-5, 0, 5, 0)
    g.setColorAt(0, MUG_BODY)
    g.setColorAt(1, mix(MUG_BODY, BLACK, 0.25))
    p.setBrush(g)
    p.drawRoundedRect(QRectF(-5, -6, 10, 11.5), 2.2, 2.2)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#c8102e"))
    p.drawRect(QRectF(-5, -1.5, 10, 2.2))                       # полоска на кружке
    p.setBrush(COFFEE)
    p.drawEllipse(QPointF(0, -5.6), 4.2, 1.2)
    p.setBrush(Qt.NoBrush)
    for i in range(2):                                          # пар
        ph = (t * 0.8 + i * 0.5) % 1.0
        a = int(160 * math.sin(ph * math.pi))
        p.setPen(_pen(QColor(255, 255, 255, a), 1.1))
        path = QPainterPath(QPointF(-1.5 + 3 * i, -7.5))
        y0 = -7.5 - 9 * ph
        path.cubicTo(QPointF(-4 + 3 * i, y0 + 2), QPointF(1 + 3 * i, y0 - 1), QPointF(-1.5 + 3 * i, y0 - 4))
        p.drawPath(path)
    p.restore()


def draw_pillow(p, wrist, ang, hs):
    """Подушка в кулаке — продолжение предплечья."""
    p.save()
    p.translate(*wrist)
    p.rotate(ang)
    p.scale(hs, hs)
    path = QPainterPath(QPointF(5, -9))
    path.cubicTo(QPointF(14, -11), QPointF(24, -11), QPointF(29, -9))
    path.cubicTo(QPointF(31, -3), QPointF(31, 3), QPointF(29, 9))
    path.cubicTo(QPointF(24, 11), QPointF(14, 11), QPointF(5, 9))
    path.cubicTo(QPointF(7, 3), QPointF(7, -3), QPointF(5, -9))
    g = QLinearGradient(5, -10, 30, 10)
    g.setColorAt(0, QColor("#ffffff"))
    g.setColorAt(1, QColor("#c9d6f2"))
    p.setPen(_pen(QColor("#3b4a6b"), 1.4))
    p.setBrush(g)
    p.drawPath(path)
    p.setPen(_pen(QColor(59, 74, 107, 110), 0.7))
    p.drawLine(QPointF(17, -9), QPointF(17, 9))
    p.restore()


def draw_foot(p, ankle, sx, q, view="front", hs=1.0):
    """Сапог. Спереди — носок вперёд, со спины — пятка и подошва (стопа смотрит от зрителя)."""
    cx, cy = ankle[0], ankle[1] + 3.5 * hs
    p.save()
    p.translate(cx, cy)
    p.scale(hs, hs)
    g = QRadialGradient(QPointF(-2 * sx, -1.5), 8)
    g.setColorAt(0, q["mainL"])
    g.setColorAt(0.6, q["main"])
    g.setColorAt(1, q["mainD"])
    if view == "front":
        p.translate(2 * sx, 0)
        p.setPen(_pen(q["rim"], 1.6))
        p.setBrush(q["mainD"])
        p.drawEllipse(QPointF(0, 1.6), 7.0, 4.4)      # подошва
        p.setPen(Qt.NoPen)
        p.setBrush(g)
        p.drawEllipse(QPointF(-0.4 * sx, 0.2), 5.9, 3.2)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(q["web"], 0.45))
        p.drawArc(QRectF(-0.4 * sx - 4, -2.4, 8, 5), 20 * 16, 140 * 16)
        p.drawLine(QPointF(-0.4 * sx, -2.8), QPointF(-0.4 * sx, 3.2))
    else:
        p.setPen(_pen(q["rim"], 1.6))
        p.setBrush(g)
        p.drawRoundedRect(QRectF(-4.3, -3.6, 8.6, 7.2), 3.6, 3.4)   # пятка
        p.setPen(Qt.NoPen)
        p.setBrush(q["mainD"])
        p.drawRoundedRect(QRectF(-4.3, 1.6, 8.6, 2.0), 1.0, 1.0)     # подошва
        p.setPen(_pen(q["rimA"], 0.6))
        p.drawLine(QPointF(0, -3.4), QPointF(0, 1.4))                  # задний шов
    p.restore()

# ----------------------------------------------------------------------------- голова и торс
def _mask_line():
    ln = QPainterPath(QPointF(-34, 49))
    ln.cubicTo(QPointF(-24, 45), QPointF(-12, 44.5), QPointF(-5, 45.5))
    ln.cubicTo(QPointF(-2, 46), QPointF(2, 46), QPointF(5, 45.5))
    ln.cubicTo(QPointF(12, 44.5), QPointF(24, 45), QPointF(34, 49))
    return ln


MASK_LINE = _mask_line()
_SKIN = QPainterPath(MASK_LINE)
_SKIN.lineTo(QPointF(34, 70))
_SKIN.lineTo(QPointF(-34, 70))
_SKIN.closeSubpath()
CIG_TIP = QPointF(21.0, 59.6)


def _stubble():
    pts, seed = [], 7
    for _ in range(170):
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        x = (seed % 3400) / 100.0 - 17.0
        seed = (seed * 1103515245 + 12345) & 0x7FFFFFFF
        y = 49.0 + (seed % 900) / 100.0
        if abs(x) < 6 and y < 51.5:
            continue
        if (x / 17.0) ** 2 + ((y - 48) / 11.0) ** 2 < 1.0:
            pts.append((x, y))
    return pts


STUBBLE = _stubble()


def _draw_lowface(p, q):
    """Маска поднята до носа: видны нос, рот, подбородок в щетине."""
    g = QLinearGradient(0, 44, 0, 60)
    g.setColorAt(0, QColor("#d3c2ad"))
    g.setColorAt(1, QColor("#a6927e"))
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawPath(_SKIN)
    sh = QLinearGradient(-32, 0, 32, 0)                 # скулы и щёки темнее к краям
    sh.setColorAt(0, QColor(40, 30, 25, 120))
    sh.setColorAt(0.28, QColor(40, 30, 25, 0))
    sh.setColorAt(0.72, QColor(40, 30, 25, 0))
    sh.setColorAt(1, QColor(40, 30, 25, 120))
    p.setBrush(sh)
    p.drawPath(_SKIN)
    p.setBrush(QColor(55, 46, 40, 55))                  # тень щетины на подбородке
    p.drawEllipse(QPointF(0, 55.5), 15.5, 7.5)
    p.setBrush(QColor(45, 38, 32, 120))
    for x, y in STUBBLE:
        p.drawEllipse(QPointF(x, y), 0.38, 0.38)
    p.setBrush(QColor("#b49f8b"))                       # нос
    p.drawEllipse(QPointF(0, 47.2), 3.5, 2.5)
    p.setBrush(QColor(60, 40, 35, 190))
    for sx in (-1.5, 1.5):
        p.drawEllipse(QPointF(sx, 48.4), 0.75, 0.55)
    p.setBrush(QColor(255, 255, 255, 80))
    p.drawEllipse(QPointF(-0.9, 46.2), 1.1, 0.7)
    p.setBrush(QColor("#a87d72"))                       # нижняя губа и рот
    p.drawEllipse(QPointF(-0.5, 55.2), 4.2, 1.2)
    mouth = QPainterPath(QPointF(-7.5, 52.6))
    mouth.cubicTo(QPointF(-3, 54.2), QPointF(3, 54.2), QPointF(7.5, 52.2))
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(QColor(70, 42, 38), 0.9))
    p.drawPath(mouth)
    p.setPen(_pen(q["rim"], 2.3))                       # край маски и валик
    p.drawPath(MASK_LINE)
    p.setPen(_pen(_alpha(q["mainL"], 150), 0.8))
    p.drawPath(MASK_LINE.translated(0, -1.7))


def _draw_cigarette(p):
    p.save()
    p.translate(5.5, 52.6)
    p.rotate(math.degrees(math.atan2(CIG_TIP.y() - 52.6, CIG_TIP.x() - 5.5)))
    ln = math.hypot(CIG_TIP.x() - 5.5, CIG_TIP.y() - 52.6)
    p.setPen(_pen(QColor("#4a3a30"), 0.9))
    p.setBrush(QColor("#f2eee4"))
    p.drawRoundedRect(QRectF(0, -1.25, ln, 2.5), 1.0, 1.0)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#c78b4b"))                       # фильтр
    p.drawRect(QRectF(0.3, -1.1, 4.4, 2.2))
    p.setBrush(QColor("#9a9a9a"))                       # пепел
    p.drawRect(QRectF(ln - 3.6, -1.1, 2.2, 2.2))
    g = QRadialGradient(QPointF(ln - 0.4, 0), 2.4)
    g.setColorAt(0, QColor("#fff2a8"))
    g.setColorAt(0.5, QColor("#ff8a1e"))
    g.setColorAt(1, QColor("#b81f0a"))
    p.setBrush(g)
    p.drawEllipse(QPointF(ln - 0.6, 0), 1.5, 1.35)
    p.restore()


def draw_smoke(p, t, boost=0.0):
    """Дым от сигареты (координаты головы), анимирован временем t; boost > 0 — густой клуб (кашель)."""
    tx, ty = CIG_TIP.x(), CIG_TIP.y()
    glow = QRadialGradient(CIG_TIP, 4.5)
    glow.setColorAt(0, QColor(255, 150, 40, int(120 + 40 * math.sin(t * 9))))
    glow.setColorAt(1, QColor(255, 120, 20, 0))
    p.setPen(Qt.NoPen)
    p.setBrush(glow)
    p.drawEllipse(CIG_TIP, 4.5, 4.5)
    n = 6 + int(8 * boost)
    for i in range(n):
        ph = (t * (0.42 + 0.5 * boost) + i / n) % 1.0
        x = tx + 4 * ph + 5.5 * math.sin(ph * 7 + i * 1.9) * (0.4 + ph)
        y = ty - 4 - 66 * ph
        r = 1.6 + 6.5 * ph + 2.5 * boost
        a = int((150 + 70 * boost) * (1 - ph) ** 1.5 * min(1.0, ph * 9))
        g = QRadialGradient(QPointF(x, y), r)
        g.setColorAt(0, QColor(222, 222, 228, a))
        g.setColorAt(1, QColor(222, 222, 228, 0))
        p.setBrush(g)
        p.drawEllipse(QPointF(x, y), r, r)


def draw_head(p, c, eyes="open", view="front", hat=None):
    q = c["q"]
    if "mohawk" in q and not hat:
        p.setPen(_pen(q["rim"], 1.8))
        g = QLinearGradient(0, -12, 0, 8)
        g.setColorAt(0, mix(q["mohawk"], WHITE, 0.35))
        g.setColorAt(1, mix(q["mohawk"], BLACK, 0.3))
        p.setBrush(g)
        p.drawPath(MOHAWK)
    g = QRadialGradient(QPointF(-11, 12), 50)
    g.setColorAt(0, q["mainL"])
    g.setColorAt(0.5, q["main"])
    g.setColorAt(1, q["mainD"])
    p.setPen(Qt.NoPen)
    p.setBrush(g)
    p.drawPath(HEAD)
    p.save()
    p.setClipPath(HEAD, Qt.IntersectClip)
    side = view == "side"
    web = WEB_TOP if eyes == "bowed" else {"front": WEB, "back": WEB_BACK, "top": WEB_TOP, "side": WEB}[view]
    if side:
        p.setTransform(FACE_SIDE, True)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(q["web"], 1.0))
    p.drawPath(web)
    p.setPen(_pen(_alpha(q["mainL"], 110), 0.4))        # выпуклые нити: светлая грань
    p.drawPath(web.translated(-0.45, -0.45))
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(0, 0, 0, 38))
    p.drawEllipse(QPointF(4, 58), 34, 12)
    if view == "back":
        p.setPen(_pen(q["rim"], 3.2))
        p.setBrush(q["eye"])
        p.drawPath(EYE_SLIVER)
    if view in ("front", "side") and c.get("lowface"):
        _draw_lowface(p, q)
    p.restore()
    p.setPen(_pen(q["rim"], 2.2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(HEAD)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 255, 255, 85))
    p.drawPath(GLOSS)
    p.drawPath(GLOSS2)
    if view in ("front", "side"):
        if side:
            p.save()
            p.setTransform(FACE_SIDE, True)
        eg = QLinearGradient(0, 19, 0, 46)
        eg.setColorAt(0, q["eye"])
        eg.setColorAt(0.55, q["eye"])
        eg.setColorAt(1, q["eyeD"])
        if eyes == "bowed":
            p.save()
            p.setClipPath(HEAD, Qt.IntersectClip)
        low = bool(c.get("lowface"))
        if low:                                  # усталый прищур: глаза ниже и приплюснуты
            p.save()
            p.translate(0, 27)
            p.scale(1, 0.8)
            p.translate(0, -27)
        for e in EYES["open" if eyes == "dizzy" else eyes]:
            if side and e.boundingRect().center().x() < 0:      # боком дальний глаз не виден
                continue
            p.setPen(_pen(q["rim"], 4.2))
            p.setBrush(eg)
            p.drawPath(e)
            if c.get("hooded") and eyes in ("open", "squint", "dizzy"):    # тяжёлое веко
                sxe = 1 if e.boundingRect().center().x() > 0 else -1
                p.save()
                p.setClipPath(e)
                p.setPen(Qt.NoPen)
                p.setBrush(q["rim"])
                p.drawPolygon(_poly((2 * sxe, 10), (40 * sxe, 10), (40 * sxe, 29), (2 * sxe, 35)))
                p.restore()
        if low:
            p.restore()
        if eyes == "bowed":
            p.restore()
        if eyes == "open":
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(255, 255, 255, 220))
            for sx in ((1,) if side else (1, -1)):
                p.drawEllipse(QPointF(21 * sx, 25), 2.6, 1.6)
        if eyes == "dizzy":                      # глаза-спирали
            p.setBrush(Qt.NoBrush)
            p.setPen(_pen(q["rim"], 1.3))
            for sx in ((1,) if side else (1, -1)):
                sp = QPainterPath(QPointF(15 * sx, 32))
                for i in range(1, 46):
                    a = i * 0.36
                    r = 0.17 * i
                    sp.lineTo(15 * sx + sx * r * math.cos(a), 32 + r * math.sin(a))
                p.drawPath(sp)
        if side:
            p.restore()
    if view in ("front", "side") and c.get("lowface"):
        p.save()
        if side:
            p.setTransform(FACE_SIDE, True)
        _draw_cigarette(p)
        p.restore()
    if hat:
        draw_hat(p, hat, "front" if side else view, q)


# ----------------------------------------------------------------------------- головные уборы
# (ключ, название, группа меню); рисуются в координатах головы chibi: макушка y=0, центр (0, 29), 64x58
HATS = [("santa", "Santa hat", "Festive"), ("party", "Party cone", "Festive"),
        ("crown", "Crown", "Festive"),
        ("cap", "Cap", "Casual"), ("ushanka", "Ushanka", "Casual"),
        ("bandana", "Bandana", "Casual"), ("nightcap", "Nightcap", "Casual"),
        ("tophat", "Top hat", "Hats"), ("fedora", "Fedora", "Hats"), ("cowboy", "Cowboy hat", "Hats"), ("sombrero", "Sombrero", "Hats"),
        ("pumpkin", "Pumpkin", "Silly"), ("propeller", "Propeller cap", "Silly"),
        ("viking", "Viking helmet", "Silly"), ("hardhat", "Hard hat", "Silly")]
_INK = QColor("#2a2018")


def _poly(*pts):
    return QPolygonF([QPointF(*pt) for pt in pts])


def _vgrad(c, y0, y1, k=0.3):
    g = QLinearGradient(0, y0, 0, y1)
    g.setColorAt(0, mix(c, WHITE, k))
    g.setColorAt(1, mix(c, BLACK, k))
    return g


def _dome(y, w, h):
    d = QPainterPath(QPointF(-w, y))
    d.cubicTo(QPointF(-w, y - h), QPointF(w, y - h), QPointF(w, y))
    d.closeSubpath()
    return d


def draw_hat(p, hat, view, q):
    p.save()
    p.setPen(_pen(_INK, 1.6))
    front = view == "front"
    if hat in ("santa", "nightcap"):
        red = QColor("#d1202f") if hat == "santa" else QColor("#3f6fb5")
        cone = QPainterPath(QPointF(-23, 7))
        if hat == "santa":
            cone.cubicTo(QPointF(-16, -14), QPointF(4, -27), QPointF(20, -22))
            cone.cubicTo(QPointF(27, -20), QPointF(31, -14), QPointF(32, -6))
            cone.lineTo(QPointF(27, -9))
            cone.cubicTo(QPointF(19, -13), QPointF(14, -5), QPointF(23, 7))
            tip = QPointF(32, -5)
        else:
            cone.cubicTo(QPointF(-14, -16), QPointF(8, -26), QPointF(24, -16))
            cone.cubicTo(QPointF(34, -8), QPointF(38, 4), QPointF(37, 14))
            cone.lineTo(QPointF(33, 13))
            cone.cubicTo(QPointF(30, 2), QPointF(22, -4), QPointF(23, 7))
            tip = QPointF(36, 16)
        cone.closeSubpath()
        p.setBrush(_vgrad(red, -25, 8, 0.25))
        p.drawPath(cone)
        if hat == "nightcap":                       # полоски
            p.save()
            p.setClipPath(cone)
            p.setPen(_pen(QColor(255, 255, 255, 200), 3.0))
            for i in range(-6, 8):
                p.drawLine(QPointF(-30 + i * 9, 10), QPointF(-10 + i * 9, -30))
            p.restore()
        p.setBrush(QColor("#fbfbf7"))
        p.drawEllipse(QPointF(0, 8), 25, 5.5)
        p.drawEllipse(tip, 5, 5)
    elif hat == "party":
        cone = QPainterPath()
        cone.addPolygon(_poly((-14, 6), (14, 6), (3, -30), (-14, 6)))
        p.setBrush(QColor("#7b2cbf"))
        p.drawPath(cone)
        p.save()
        p.setClipPath(cone)
        for i, col in enumerate(("#ffbe0b", "#3a86ff", "#ff006e", "#8ac926") * 3):
            p.setPen(_pen(QColor(col), 3.2))
            p.drawLine(QPointF(-20, 2 - i * 6), QPointF(20, 8 - i * 6))
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.drawPath(cone)
        p.setBrush(QColor("#ffbe0b"))
        p.drawEllipse(QPointF(3, -30), 4, 4)
    elif hat == "crown":
        p.setBrush(_vgrad(QColor("#f2c230"), -20, 8, 0.35))
        p.drawPolygon(_poly((-21, 7), (-21, -3), (-17, -16), (-10, -5), (0, -21), (10, -5), (17, -16), (21, -3), (21, 7)))
        for (x, y, r, col) in ((0, 2, 2.6, "#d00000"), (-12, 2, 2, "#1d4fb6"), (12, 2, 2, "#2a9d8f"),
                               (-17, -16, 1.8, "#fff3b0"), (0, -21, 2, "#fff3b0"), (17, -16, 1.8, "#fff3b0")):
            p.setBrush(QColor(col))
            p.drawEllipse(QPointF(x, y), r, r)
    elif hat in ("cap", "propeller"):
        dome = _dome(10, 25, 22)
        if hat == "cap":
            p.setBrush(_vgrad(QColor("#2b6cb0"), -6, 10))
            p.drawPath(dome)
            p.setPen(_pen(QColor(0, 0, 0, 90), 0.8))
            for x in (-12, 12):
                p.drawLine(QPointF(0, -5.5), QPointF(x, 9))
            p.setPen(_pen(_INK, 1.6))
        else:
            p.setBrush(QColor("#ffbe0b"))
            p.drawPath(dome)
            p.save()
            p.setClipPath(dome)
            p.setPen(Qt.NoPen)
            for i, col in enumerate(("#e63946", "#2a9d8f", "#1d4fb6")):
                p.setBrush(QColor(col))
                p.drawPolygon(_poly((0, -6), (-30 + i * 20, 12), (-20 + i * 20, 12)))
            p.restore()
            p.setBrush(Qt.NoBrush)
            p.drawPath(dome)
        if front:
            p.setBrush(QColor("#1e4e85") if hat == "cap" else QColor("#e63946"))
            p.drawEllipse(QPointF(0, 11), 22, 4.5)       # козырёк
        p.setBrush(QColor("#ffffff") if hat == "cap" else QColor("#444444"))
        p.drawEllipse(QPointF(0, -6), 2.2, 1.6)
        if hat == "propeller":
            p.drawLine(QPointF(0, -6), QPointF(0, -11))
            p.setBrush(QColor("#e63946"))
            p.drawEllipse(QPointF(-9, -12), 9, 2.3)
            p.setBrush(QColor("#1d4fb6"))
            p.drawEllipse(QPointF(9, -12), 9, 2.3)
            p.setBrush(QColor("#ffbe0b"))
            p.drawEllipse(QPointF(0, -12), 2, 2)
    elif hat == "ushanka":
        fur = QColor("#6b4a2b")
        p.setBrush(_vgrad(fur, -8, 30, 0.2))
        p.drawRoundedRect(QRectF(-35, 6, 10, 24), 4, 4)
        p.drawRoundedRect(QRectF(25, 6, 10, 24), 4, 4)
        p.drawPath(_dome(10, 28, 24))
        p.setBrush(_vgrad(QColor("#9a7550"), 1, 12, 0.2))
        p.drawRoundedRect(QRectF(-29, 1, 58, 11), 5, 5)
        p.setPen(_pen(QColor(255, 255, 255, 60), 0.7))
        for x in range(-24, 26, 5):
            p.drawLine(QPointF(x, 3), QPointF(x + 1.5, 10))
        p.setPen(_pen(_INK, 1.2))
        if front:
            p.setBrush(QColor("#d4af37"))
            p.drawEllipse(QPointF(0, 6.5), 2.6, 2.6)
    elif hat == "bandana":
        cloth = _dome(15, 31, 30)
        p.setBrush(QColor("#d62828"))
        p.drawPolygon(_poly((27, 10), (41, 18), (37, 25), (30, 15)))
        p.drawPolygon(_poly((28, 12), (34, 27), (28, 29), (26, 16)))
        p.drawPath(cloth)
        p.save()
        p.setClipPath(cloth)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        for i in range(-30, 31, 8):
            for j in range(-12, 16, 7):
                p.drawEllipse(QPointF(i + (j % 2) * 4, j), 1.4, 1.4)
        p.restore()
        p.setBrush(QColor("#a61b1b"))
        p.drawEllipse(QPointF(29, 13), 3.4, 3.0)
    elif hat == "fedora":
        p.save()
        p.translate(0, 6.5)
        p.rotate(-5)
        p.setBrush(_vgrad(QColor("#2b2b30"), -3, 4, 0.2))
        p.drawEllipse(QPointF(0, 0), 31.5, 5.8)             # поля
        p.restore()
        crown = QPainterPath(QPointF(-17.5, 5.5))
        crown.cubicTo(QPointF(-19, -7), QPointF(-14.5, -17), QPointF(-7.5, -17.5))
        crown.quadTo(QPointF(0, -12.5), QPointF(7.5, -17.5))
        crown.cubicTo(QPointF(14.5, -17), QPointF(19, -7), QPointF(17.5, 5.5))
        crown.cubicTo(QPointF(8, 8.5), QPointF(-8, 8.5), QPointF(-17.5, 5.5))
        p.setBrush(_vgrad(QColor("#34343a"), -18, 8, 0.28))
        p.drawPath(crown)
        p.save()
        p.setClipPath(crown)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#0e0e11"))                        # лента
        p.drawRect(QRectF(-20, -1.5, 40, 6.2))
        p.setBrush(QColor(255, 255, 255, 38))                # блик на тулье
        p.drawEllipse(QPointF(-9, -10), 4.2, 2.2)
        p.restore()
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(QColor("#15151a"), 1.1))                # вмятина и заломы
        dent = QPainterPath(QPointF(-7.5, -17))
        dent.quadTo(QPointF(0, -11.5), QPointF(7.5, -17))
        p.drawPath(dent)
        p.drawLine(QPointF(-11, -12), QPointF(-6, -6))
        p.drawLine(QPointF(11, -12), QPointF(6, -6))
    elif hat == "tophat":
        p.setBrush(_vgrad(QColor("#26262b"), -32, 6, 0.25))
        p.drawEllipse(QPointF(0, 6), 28, 4.5)
        p.drawRect(QRectF(-16, -30, 32, 36))
        p.setBrush(QColor("#7a1020"))
        p.drawRect(QRectF(-16, -2, 32, 5))
        p.setBrush(QColor("#3a3a42"))
        p.drawEllipse(QPointF(0, -30), 16, 3)
    elif hat == "cowboy":
        brown = QColor("#8b5a2b")
        p.setBrush(_vgrad(brown, -18, 8, 0.25))
        crown = QPainterPath(QPointF(-18, 7))
        crown.cubicTo(QPointF(-20, -14), QPointF(-10, -20), QPointF(0, -14))
        crown.cubicTo(QPointF(10, -20), QPointF(20, -14), QPointF(18, 7))
        crown.closeSubpath()
        p.drawPath(crown)
        p.setBrush(QColor("#3b2412"))
        p.drawRect(QRectF(-18.5, 0, 37, 4))
        brim = QPainterPath(QPointF(-45, 1))
        brim.cubicTo(QPointF(-32, 14), QPointF(32, 14), QPointF(45, 1))
        brim.cubicTo(QPointF(40, 7), QPointF(28, 7), QPointF(0, 7))
        brim.cubicTo(QPointF(-28, 7), QPointF(-40, 7), QPointF(-45, 1))
        p.setBrush(_vgrad(brown, 0, 12, 0.2))
        p.drawPath(brim)
    elif hat == "sombrero":
        straw = QColor("#e9c46a")
        p.setBrush(_vgrad(straw, -2, 14, 0.2))
        p.drawEllipse(QPointF(0, 7), 56, 10)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(QColor("#d00000"), 1.6))
        p.drawEllipse(QPointF(0, 7), 51, 8)
        p.setPen(_pen(_INK, 1.6))
        p.setBrush(_vgrad(straw, -24, 6, 0.25))
        p.drawPath(_dome(7, 17, 38))
        p.setBrush(QColor("#2a9d8f"))
        p.drawRect(QRectF(-16, 0, 32, 4))
        p.setPen(_pen(QColor("#d00000"), 1.0))
        for x in range(-14, 15, 4):
            p.drawLine(QPointF(x, 0.5), QPointF(x + 2, 3.5))
    elif hat == "pumpkin":
        orange = QColor("#f77f00")
        g = QRadialGradient(QPointF(-10, 15), 50)
        g.setColorAt(0, mix(orange, WHITE, 0.3))
        g.setColorAt(0.6, orange)
        g.setColorAt(1, mix(orange, BLACK, 0.35))
        p.setBrush(QColor("#2d6a4f"))
        p.drawRoundedRect(QRectF(-3, -9, 6, 10), 2, 2)
        p.setBrush(g)
        p.drawEllipse(QPointF(0, 29), 36, 32)
        p.setBrush(Qt.NoBrush)
        p.setPen(_pen(QColor(120, 50, 0, 150), 1.0))
        for rx in (12, 24):
            p.drawEllipse(QPointF(0, 29), rx, 31.5)
        if front:
            p.setPen(_pen(_INK, 1.2))
            p.setBrush(QColor("#ffd166"))
            p.drawPolygon(_poly((-19, 30), (-7, 30), (-13, 18)))
            p.drawPolygon(_poly((7, 30), (19, 30), (13, 18)))
            p.drawPolygon(_poly((-18, 41), (-12, 46), (-6, 42), (0, 47), (6, 42), (12, 46), (18, 41), (12, 50),
                                (0, 52), (-12, 50)))
    elif hat == "viking":
        horn = QPainterPath(QPointF(-24, 3))
        horn.cubicTo(QPointF(-36, 0), QPointF(-44, -10), QPointF(-44, -26))
        horn.cubicTo(QPointF(-38, -14), QPointF(-30, -6), QPointF(-21, -4))
        horn.closeSubpath()
        p.setBrush(_vgrad(QColor("#efe6cf"), -26, 4, 0.2))
        p.drawPath(horn)
        p.drawPath(_mirror(horn))
        p.setBrush(_vgrad(QColor("#9aa3ad"), -10, 12, 0.3))
        p.drawPath(_dome(12, 27, 30))
        p.setBrush(QColor("#6c757d"))
        p.drawRect(QRectF(-27, 6, 54, 6))
        p.setBrush(QColor("#ced4da"))
        for x in range(-22, 23, 9):
            p.drawEllipse(QPointF(x, 9), 1.2, 1.2)
    elif hat == "hardhat":
        yel = QColor("#f4c20d")
        p.setBrush(_vgrad(yel, -10, 10, 0.25))
        p.drawPath(_dome(10, 27, 28))
        p.setBrush(mix(yel, WHITE, 0.3))
        p.drawRoundedRect(QRectF(-4, -10, 8, 19), 3, 3)
        p.setBrush(mix(yel, BLACK, 0.12))
        p.drawEllipse(QPointF(0, 10), 32, 4.5)
    p.restore()


def draw_emblem(p, color, cy=61.5, s=1.0, rim=None, long_legs=False):
    p.save()
    p.translate(0, cy)
    p.scale(s, s)
    legs = QPainterPath()
    if long_legs:      # паук на спине: длинные изогнутые лапы
        for sx in (1, -1):
            for (mx, my), (ex, ey) in (((5, -5), (8, -12)), ((6.5, -1.5), (12, -4)),
                                       ((6.5, 2), (12, 6)), ((5, 5), (7.5, 12))):
                legs.moveTo(0, 0)
                legs.quadTo(mx * sx, my, ex * sx, ey)
    else:
        for sx in (1, -1):
            for (mx, my), (ex, ey) in (((4, -4), (7.5, -7.5)), ((5, -1.5), (9, -2.5)),
                                       ((5, 1.5), (9, 3.5)), ((4, 3.5), (6.5, 7.5))):
                legs.moveTo(0, 0)
                legs.lineTo(mx * sx, my)
                legs.lineTo(ex * sx, ey)
    body = QPainterPath()
    body.addEllipse(QPointF(0, 1.4), 2.3, 3.8)
    body.addEllipse(QPointF(0, -3.1), 1.7, 1.7)
    p.setBrush(Qt.NoBrush)
    if rim is not None:
        p.setPen(_pen(rim, 2.4))
        p.drawPath(legs)
        p.setPen(_pen(rim, 1.0))
        p.setBrush(rim)
        p.drawPath(body)
    p.setPen(_pen(color, 1.1))
    p.setBrush(Qt.NoBrush)
    p.drawPath(legs)
    p.setPen(Qt.NoPen)
    p.setBrush(color)
    p.drawPath(body)
    p.restore()


def _grad(q, key):
    g = QLinearGradient(-16, 50, 16, 80)
    g.setColorAt(0, q[key + "L"])
    g.setColorAt(0.45, q[key])
    g.setColorAt(1, q[key + "D"])
    return g


def draw_torso(p, q, view):
    front = view == "front"
    p.setPen(Qt.NoPen)
    p.setBrush(_grad(q, "second"))
    p.drawPath(TORSO)
    p.save()
    p.setClipPath(TORSO, Qt.IntersectClip)
    p.setBrush(_grad(q, "main"))
    if front:
        p.drawPath(RED_FRONT)
    else:
        p.drawPath(RED_BACK)
        p.drawPath(BELT_BACK)
    p.save()
    p.setClipPath(RED_FRONT if front else RED_BACK, Qt.IntersectClip)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(q["web"], 0.6))
    p.drawPath(TORSO_WEB if front else TORSO_WEB_BACK)
    p.restore()
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(q["fold"], 0.8))
    p.drawPath(MUSCLES_FRONT if front else MUSCLES_BACK)
    p.setPen(_pen(q["rimA"], 0.9))                      # швы между цветами
    p.drawPath(SEAMS_FRONT if front else SEAMS_BACK)
    if not front:
        p.drawPath(BELT_BACK)
    if "scuff" in q:                                    # потёртости на костюме
        p.setPen(_pen(_alpha(q["scuff"], 55), 0.6))
        for x0, y0, x1, y1 in ((-8, 55, -4, 61), (6, 66, 10, 71), (-3, 72, 1, 75), (9, 53, 12, 58), (-11, 68, -9, 73)):
            p.drawLine(QPointF(x0, y0), QPointF(x1, y1))
    p.setPen(Qt.NoPen)                                  # тень под головой и по бокам
    p.setBrush(QColor(0, 0, 0, 45))
    p.drawEllipse(QPointF(0, 49), 17, 4.5)
    p.restore()
    p.setPen(_pen(q["rim"], 2.0))
    p.setBrush(Qt.NoBrush)
    p.save()
    p.setClipRect(QRectF(-30, 40, 60, 37))          # контур — только по плечам и талии; таз и ноги — один силуэт
    p.drawPath(TORSO)
    p.restore()
    if front:
        draw_emblem(p, q["emblem"], 61.5, 1.0)
    else:                      # паук на спине — в пределах спины, не больше торса
        p.save()
        p.setClipPath(TORSO, Qt.IntersectClip)
        draw_emblem(p, q["back"], 65, 0.85, rim=q["rim"], long_legs=True)
        p.restore()


# ----------------------------------------------------------------------------- кэш картинок
_CACHE = {}


def _cached(p, key, box, fn, oversample=2.0):
    """Нарисовать fn(painter) один раз в картинку (под текущий масштаб ×oversample) и перенести."""
    t = p.worldTransform()
    dev = p.device()
    dpr = dev.devicePixelRatioF() if dev is not None else 1.0
    s = max(0.5, round(math.hypot(t.m21(), t.m22()) * dpr * oversample * 4) / 4)
    k = key + (s,)
    pm = _CACHE.get(k)
    if pm is None:
        if len(_CACHE) > 160:
            _CACHE.clear()
        pm = QPixmap(int(box.width() * s) + 2, int(box.height() * s) + 2)
        pm.fill(Qt.transparent)
        qp = QPainter(pm)
        qp.setRenderHint(QPainter.Antialiasing)
        qp.scale(s, s)
        qp.translate(-box.x(), -box.y())
        fn(qp)
        qp.end()
        _CACHE[k] = pm
    p.save()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.drawPixmap(QRectF(box.x(), box.y(), pm.width() / s, pm.height() / s), pm, QRectF(pm.rect()))
    p.restore()


HEAD_BOX = QRectF(-60, -36, 120, 98)     # с запасом под шляпы


def draw_head_cached(p, c, eyes, view="front", hat=None, style="chibi"):
    _cached(p, ("head", c["key"], eyes, view, hat), HEAD_BOX, lambda qp: draw_head(qp, c, eyes, view, hat))


def draw_torso_cached(p, c, view, style="chibi"):
    v = "front" if view == "front" else "back"
    _cached(p, ("torso", c["key"], v), TORSO_BOX, lambda qp: draw_torso(qp, c["q"], v))


# ----------------------------------------------------------------------------- персонаж целиком
LEG_FILLS = ((0, 0, 1, "second"), (1, 0, 0.32, "second"), (1, 0.32, 1, "main"))
LEG_WEBS = ((1, 0.32, 1),)
ARM_FILLS = ((0, 0, 1, "main"), (1, 0, 1, "main"))
ARM_WEBS = ((0, 0.15, 1), (1, 0, 1))


def draw_spider(p, c, pose, eyes="open", view="front", part="all", style="chibi", hat=None, t=0.0, J=None):
    """Рисует персонажа в координатах модели (painter уже преобразован).
    part: all — целиком; base — без рук из pose[front]; arms — только эти руки (для кэша мема)."""
    q = c["q"]
    st = STYLES[style]
    J = J or fk(style, pose)
    ow = 2.6
    back = view in ("back", "top")
    side = view == "side"
    if side:      # боком: таз и ноги ближе к оси, плечи тоже; руки — полной длины (тянутся в плоскости картинки)
        J = dict(J)
        for key in ("rp", "rk", "rn", "lp", "lk", "ln"):
            J[key] = (J[key][0] * SIDE_X, J[key][1])
        for sd in "rl":
            dx = J[sd + "s"][0] * (SIDE_X - 1)
            for n in "sewh":
                J[sd + n] = (J[sd + n][0] + dx, J[sd + n][1])
        J["feet"] = ((J["rn"][0] + J["ln"][0]) / 2, J["feet"][1])

    def torso():
        if side:
            p.save()
            p.scale(SIDE_X, 1)
            draw_torso_cached(p, c, "front", style)
            p.restore()
        else:
            draw_torso_cached(p, c, view, style)

    def leg(s, phase):
        sx = 1 if s == "r" else -1
        hp, kn, an = J[s + "p"], J[s + "k"], J[s + "n"]
        draw_limb(p, [hp, kn, an], PROFILES[style]["leg"], LEG_FILLS, LEG_WEBS, q, sx, ow=ow)
        bx, by = _pt(kn, an, 0.32)                     # кромка сапога уголком
        r = PROFILES[style]["leg"][1][0][1]
        p.setPen(_pen(q["rimA"], 0.8 * r / 4.6))
        p.drawLine(QPointF(bx - r * 0.9, by), QPointF(bx, by + r * (0.35 if back else -0.35)))
        p.drawLine(QPointF(bx, by + r * (0.35 if back else -0.35)), QPointF(bx + r * 0.9, by))
        p.setPen(Qt.NoPen)
        if back:                                       # подколенная складка и икра
            p.setPen(_pen(q["fold2"], 0.8 * r / 4.6))
            p.drawLine(QPointF(kn[0] - r * 0.6, kn[1] + 0.3), QPointF(kn[0] + r * 0.6, kn[1] + 0.3))
        else:                                          # блик на колене
            p.setBrush(QColor(255, 255, 255, 55))
            p.drawEllipse(QPointF(kn[0] - r * 0.15, kn[1] - r * 0.1), r * 0.55, r * 0.45)
        draw_foot(p, an, sx, q, "back" if back else "front", st["hs"])

    def legs():
        # ноги растут из-под таза: сначала ноги, потом торс поверх (паховая линия — край таза)
        if pose["legsfront"]:                          # колени к груди — ноги поверх торса
            torso()
            for s in "rl":
                leg(s, "all")
            return
        for s in ("lr" if side else "rl"):             # боком: дальняя (левая) нога первой
            leg(s, "all")
        torso()

    def arm(s):
        el, wr = J[s + "e"], J[s + "w"]
        draw_limb(p, [J[s + "s"], el, wr], PROFILES[style]["arm"], ARM_FILLS, ARM_WEBS, q,
                  1 if s == "r" else -1, stripe=(0, 0.08, 0.95, "second", 1 if back else -1), ow=ow)
        draw_hand(p, wr, el, pose["h" + s], q, st["hs"], t)

    def cover(s, head):
        # корень руки прячем под торс (и голову): рука растёт из тела, а не наклеена поверх контура
        path = QPainterPath()
        path.addEllipse(QPointF(*J[s + "s"]), 8.5, 8.5)
        p.save()
        p.setClipPath(path, Qt.IntersectClip)
        torso()
        if head:
            draw_head_cached(p, c, eyes, view, hat, style)
        p.restore()

    if part != "arms":
        for s in pose.get("under", ""):      # рука за телом (вид со спины) — почти не видна
            arm(s)
        legs()
        if pose.get("item") == "guitar":
            draw_guitar(p, t)
        for s in "rl":
            if s not in pose["front"] and s not in pose.get("under", ""):
                arm(s)
                cover(s, False)
        draw_head_cached(p, c, eyes, view, hat, style)
    if part != "base":
        for s in "rl":
            if s in pose["front"]:
                arm(s)
                cover(s, True)


def _arc_point(pts, dist):
    """Точка на ломаной pts на расстоянии dist от начала и направление в ней."""
    acc = 0.0
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        ln = math.hypot(b[0] - a[0], b[1] - a[1])
        if ln > 1e-6 and acc + ln >= dist:
            t = (dist - acc) / ln
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)
        acc += ln
    a, b = pts[-2], pts[-1]
    ln = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    return b, ((b[0] - a[0]) / ln, (b[1] - a[1]) / ln)


def draw_web_rope(p, pts, w=1.0, alpha=255, cone=0.0, phase=0.0):
    """Паутина по точкам физической нити pts (от крепления к руке): плавная кривая через середины звеньев,
    мягкая тень, шёлковая нить с бликом и тонкая вторая нить, обвивающая основную; у крепления — конус
    из пяти нитей с провисающей перемычкой."""
    if len(pts) < 2:
        return
    total = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1]) for i in range(len(pts) - 1))
    cone = min(cone, total * 0.4)
    a0 = pts[0]
    if cone > 2:
        j, (ux, uy) = _arc_point(pts, cone)
        body = [j] + [q_ for q_ in pts if math.hypot(q_[0] - a0[0], q_[1] - a0[1]) > cone * 1.05]
    else:
        body = list(pts)
    if len(body) < 2:
        body = [pts[0], pts[-1]]
    path = QPainterPath(QPointF(*body[0]))
    for i in range(1, len(body) - 1):
        m = ((body[i][0] + body[i + 1][0]) / 2, (body[i][1] + body[i + 1][1]) / 2)
        path.quadTo(QPointF(*body[i]), QPointF(*m))
    path.lineTo(QPointF(*body[-1]))
    fan = QPainterPath()
    if cone > 2:
        nx, ny = -uy, ux
        ends = [(a0[0] + nx * cone * 0.85 * k_, a0[1] + ny * cone * 0.85 * k_) for k_ in (-1, -0.5, 0, 0.5, 1)]
        for e in ends:
            fan.moveTo(QPointF(*j))
            fan.quadTo(QPointF(lerp(j[0], e[0], 0.5) + ux * cone * 0.06, lerp(j[1], e[1], 0.5) + uy * cone * 0.06),
                       QPointF(*e))
        mids = [QPointF(lerp(e[0], j[0], 0.42), lerp(e[1], j[1], 0.42)) for e in ends]
        fan.moveTo(mids[0])
        for i, m in enumerate(mids[1:]):
            c = (mids[i] + m) / 2
            fan.quadTo(QPointF(c.x() + ux * cone * 0.1, c.y() + uy * cone * 0.1), m)
    # вторая тонкая нить обвивает основную (синусоида вдоль нормали)
    twist = QPainterPath()
    acc = 0.0
    for i, q_ in enumerate(body):
        if i:
            acc += math.hypot(q_[0] - body[i - 1][0], q_[1] - body[i - 1][1])
        a_ = body[max(0, i - 1)]
        b_ = body[min(len(body) - 1, i + 1)]
        dl = math.hypot(b_[0] - a_[0], b_[1] - a_[1]) or 1.0
        off = 0.9 * w * math.sin(acc / (7.0 * w) + phase)
        pt = QPointF(q_[0] - (b_[1] - a_[1]) / dl * off, q_[1] + (b_[0] - a_[0]) / dl * off)
        if i == 0:
            twist.moveTo(pt)
        else:
            twist.lineTo(pt)
    p.setBrush(Qt.NoBrush)
    sh = QTransform().translate(0.8 * w, 1.4 * w)
    p.setPen(_pen(QColor(0, 0, 0, int(55 * alpha / 255)), 2.6 * w))         # мягкая тень
    p.drawPath(sh.map(path))
    if cone > 2:
        p.setPen(_pen(QColor(0, 0, 0, int(45 * alpha / 255)), 1.6 * w))
        p.drawPath(sh.map(fan))
        p.setPen(_pen(QColor(205, 210, 222, alpha), 1.0 * w))
        p.drawPath(fan)
        p.setPen(_pen(QColor(255, 255, 255, int(220 * alpha / 255)), 0.45 * w))
        p.drawPath(fan)
    p.setPen(_pen(QColor(120, 126, 140, int(150 * alpha / 255)), 2.0 * w))  # край нити
    p.drawPath(path)
    p.setPen(_pen(QColor(226, 230, 238, alpha), 1.45 * w))                   # шёлк
    p.drawPath(path)
    p.setPen(_pen(QColor(255, 255, 255, int(235 * alpha / 255)), 0.6 * w))   # блик
    p.drawPath(path)
    p.setPen(_pen(QColor(250, 250, 255, int(150 * alpha / 255)), 0.45 * w))  # вторая нить
    p.drawPath(twist)


def draw_web_line(p, a, b, w=1.0, slack=0.0, alpha=255, cone=0.0):
    """Нить паутины от точки крепления a к b. cone > 0 — длина «конуса» у точки крепления: нить там
    расходится веером из пяти нитей, прилепленных к поверхности, с поперечной перемычкой (как настоящая паутина)."""
    dx, dy = b.x() - a.x(), b.y() - a.y()
    ln = math.hypot(dx, dy)
    cone = min(cone, ln * 0.45)
    start = a
    fan = QPainterPath()
    if cone > 2:
        ux, uy = dx / ln, dy / ln
        nx, ny = -uy, ux
        start = QPointF(a.x() + ux * cone, a.y() + uy * cone)       # где нить расходится
        ends = [QPointF(a.x() + nx * cone * 0.8 * s, a.y() + ny * cone * 0.8 * s) for s in (-1, -0.5, 0, 0.5, 1)]
        for e in ends:
            fan.moveTo(start)
            fan.lineTo(e)
        mids = [QPointF(lerp(e.x(), start.x(), 0.4), lerp(e.y(), start.y(), 0.4)) for e in ends]
        fan.moveTo(mids[0])
        for i, m in enumerate(mids[1:]):                            # провисающая перемычка между нитями
            c = (mids[i] + m) / 2
            fan.quadTo(QPointF(c.x() + ux * cone * 0.08, c.y() + uy * cone * 0.08), m)
    path = QPainterPath(start)
    if slack > 1:
        m = (start + b) / 2
        path.quadTo(QPointF(m.x(), m.y() + slack), b)
    else:
        path.lineTo(b)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(QColor(0, 0, 0, int(80 * alpha / 255)), 2.8 * w))
    p.drawPath(path)
    if cone > 2:
        p.setPen(_pen(QColor(0, 0, 0, int(60 * alpha / 255)), 1.9 * w))
        p.drawPath(fan)
        p.setPen(_pen(QColor(246, 246, 252, alpha), 0.75 * w))
        p.drawPath(fan)
    p.setPen(_pen(QColor(246, 246, 252, alpha), 1.3 * w))
    p.drawPath(path)


def draw_splat(p, x, y, r, alpha):
    if r < 1:
        return
    path = _web_pattern(x, y, 8, (0.4 * r, 0.75 * r), r, rot=0.3)
    p.setBrush(Qt.NoBrush)
    p.setPen(_pen(QColor(0, 0, 0, int(70 * alpha)), 2.6))
    p.drawPath(path)
    p.setPen(_pen(QColor(248, 248, 255, int(235 * alpha)), 1.2))
    p.drawPath(path)
