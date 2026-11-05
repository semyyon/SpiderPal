# -*- coding: utf-8 -*-
"""Галерея: головные уборы, костюмы, позы, мем в трёх видах, муха/фонарь/дождь -> PNG.
Запуск: .venv\\Scripts\\python.exe gallery.py [папка]   (по умолчанию — скриншоты)"""
import math
import os
import sys

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication

import art


def _font(p, px=15):
    f = QFont("Segoe UI")
    f.setPixelSize(px)
    p.setFont(f)


def sheet(path, items, cols, cell=(230, 300), scale=2.0):
    """items: (подпись, стиль, костюм, поза, глаза, вид, шляпа, зеркало)."""
    rows = (len(items) + cols - 1) // cols
    img = QImage(cols * cell[0], rows * cell[1], QImage.Format_ARGB32)
    img.fill(QColor("#4a5160"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    _font(p)
    for i, (title, style, costume, pose, eyes, view, hat, mirror) in enumerate(items):
        x, y = (i % cols) * cell[0], (i // cols) * cell[1]
        p.save()
        p.translate(x + cell[0] / 2, y + cell[1] * 0.2)
        p.scale(scale * mirror, scale)
        art.draw_spider(p, art.COSTUME_BY_KEY[costume], pose, eyes, view, style=style, hat=hat, t=0.4, J=pose.get("_J"))
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.drawText(x + 8, y + cell[1] - 12, title)
    p.end()
    img.save(path)


def meme_sheet(path, scale):
    """Трое мема как в игре: левый боком (side), средний дальше и меньше (front), правый спиной (back, mirror=-1).
    Руки проверяются на анатомический сгиб (joint_bends > 0)."""
    st = "chibi"
    H = 104 * scale
    W, Hh = int(H * 4.2), int(H * 1.9)
    img = QImage(W, Hh, QImage.Format_ARGB32)
    img.fill(QColor("#4a5160"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    _font(p, max(10, int(6 * scale)))
    base = Hh * 0.82
    figs = [("mid", "front", 1, W * 0.5, base - H * 0.3, 0.82, "gold"),
            ("left", "side", 1, W * 0.17, base, 1.0, "classic"),
            ("back", "back", -1, W * 0.83, base, 1.0, "black")]
    for var, view, mirror, x, floor, sc, key in figs:
        pose = art.pose_point(var, 0.4, st)
        J = art.fk(st, pose)
        bends = art.joint_bends(J, pose)
        bad = {k: round(v, 1) for k, v in bends.items() if v <= 0}
        assert not bad, (var, bad)
        p.save()
        p.translate(x, floor)
        p.scale(scale * sc * mirror, scale * sc)
        p.translate(0, -105)
        art.draw_spider(p, art.COSTUME_BY_KEY[key], pose, "open", view, style=st, t=0.4)
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.drawText(QPointF(x - H * 0.45, Hh - 6), "%s/%s %s" % (var, view, " ".join("%d" % round(v) for v in bends.values())))
    p.end()
    img.save(path)


def props_sheet(path, scale):
    """Муха, фонарь, дождь — образцы."""
    W, Hh = int(520 * scale), int(260 * scale)
    img = QImage(W, Hh, QImage.Format_ARGB32)
    img.fill(QColor("#2b303a"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    _font(p)
    art.draw_rain(p, QRectF(0, 0, W * 0.55, Hh), 0.3, 0.6)
    art.draw_lamp(p, W * 0.72, Hh * 0.9, Hh * 0.75, 0.3)
    for i, t in enumerate((0.0, 0.01, 0.02)):
        p.save()
        p.translate(W * 0.12 + i * 40 * scale, Hh * 0.3)
        p.scale(4 * scale, 4 * scale)
        art.draw_fly(p, t)
        p.restore()
    p.save()
    p.translate(W * 0.4, Hh * 0.6)
    p.scale(scale, scale)
    art.draw_fly(p, 0.0)
    p.restore()
    p.setPen(QColor("#ffffff"))
    p.drawText(8, Hh - 10, "дождь (density 0.6) | муха ×4 и ×1 | фонарь")
    p.end()
    img.save(path)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "скриншоты")
    os.makedirs(out, exist_ok=True)
    st = "chibi"
    hats = [(name, st, "classic", art.get_pose("hang", st), "open", "front", key, 1) for key, name, _ in art.HATS]
    sheet(os.path.join(out, "галерея_головные_уборы.png"), hats, 7)
    cos = [(c["name"], st, c["key"], art.get_pose("star", st), "open", "front", None, 1) for c in art.COSTUMES]
    sheet(os.path.join(out, "галерея_костюмы.png"), cos, 10, cell=(200, 300), scale=1.8)

    def crawl(ph):
        pose = art.pose_crawl(st)
        pose["_J"] = art.crawl_joints(st, art.fk(st, pose), art.crawl_targets(ph))
        return pose
    poses = [("вис + кофе", st, "classic", art.pose_hang(st, 0, "mug", 0), "open", "front", None, 1),
             ("глоток", st, "classic", art.pose_hang(st, 0, "mug", 1), "open", "front", None, 1),
             ("ползёт: левая вперёд", st, "classic", crawl(math.pi / 2), "squint", "top", None, 1),
             ("ползёт: правая вперёд", st, "classic", crawl(-math.pi / 2), "squint", "top", None, 1),
             ("noir: стоит", st, "noir", art.get_pose("hang", st), "open", "front", "fedora", 1),
             ("гитара", st, "classic", art.get_pose("guitar", st), "open", "front", None, 1),
             ("сон (вверх ногами)", st, "classic", art.get_pose("sleep", st), "sleep", "front", None, 1),
             ("сидит на окне", st, "pajama", art.get_pose("sit", st), "sleep", "front", "nightcap", 1),
             ("голова кругом", st, "classic", art.get_pose("star", st), "dizzy", "front", None, 1),
             ("дай пять", st, "classic", art.get_pose("five", st), "open", "front", None, 1),
             ("подушка", st, "classic", art.get_pose("pillow", st), "open", "front", None, 1),
             ("палец вверх (thumbs)", st, "classic", art.get_pose("thumbs", st), "open", "front", None, 1),
             ("виноват (guilty)", st, "classic", art.get_pose("guilty", st), "squint", "front", None, 1),
             ("пришпилен (pin)", st, "classic", art.get_pose("pin", st), "squint", "front", None, 1),
             ("мем: левый боком", st, "classic", art.pose_point("left", 0, st), "open", "side", None, 1),
             ("мем: средний", st, "classic", art.pose_point("mid", 0, st), "open", "front", None, 1),
             ("мем: правый спиной", st, "classic", art.pose_point("back", 0, st), "open", "back", None, -1),
             ("стоит боком (hang)", st, "classic", dict(art.get_pose("hang", st), lsx=1), "open", "side", None, 1)]
    sheet(os.path.join(out, "галерея_позы.png"), poses, 9, cell=(210, 300), scale=1.9)
    for sc, name in ((0.7, "мини"), (1.0, "норма"), (2.0, "крупно")):
        meme_sheet(os.path.join(out, "галерея_мем_%s.png" % name), sc)
        props_sheet(os.path.join(out, "галерея_реквизит_%s.png" % name), sc)
    # стык кисть/предплечье и стопа/голень крупно: мини (0.7) и крупно (2.0) — не должно быть тёмных щелей
    for sc, name in ((0.7, "мини"), (2.0, "крупно")):
        items = [("hang", st, "classic", art.get_pose("hang", st), "open", "front", None, 1),
                 ("crawl", st, "classic", crawl(math.pi / 2), "squint", "top", None, 1),
                 ("point side", st, "classic", art.pose_point("left", 0, st), "open", "side", None, 1)]
        sheet(os.path.join(out, "галерея_стыки_%s.png" % name), items, 3, cell=(int(120 * sc) + 60, int(130 * sc) + 40), scale=sc)
    print("ok", out, "cache", art.cache_stats())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main()
