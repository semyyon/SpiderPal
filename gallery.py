# -*- coding: utf-8 -*-
"""Галерея: все головные уборы, костюмы и позы -> PNG.
Запуск: .venv\\Scripts\\python.exe gallery.py [папка]   (по умолчанию — скриншоты)"""
import math
import os
import sys

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QFont
from PySide6.QtWidgets import QApplication

import art


def sheet(path, items, cols, cell=(230, 300), scale=2.0):
    rows = (len(items) + cols - 1) // cols
    img = QImage(cols * cell[0], rows * cell[1], QImage.Format_ARGB32)
    img.fill(QColor("#4a5160"))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    f = QFont("Segoe UI")
    f.setPixelSize(15)
    p.setFont(f)
    for i, (title, style, costume, pose, eyes, view, hat, mirror) in enumerate(items):
        x, y = (i % cols) * cell[0], (i // cols) * cell[1]
        p.save()
        p.translate(x + cell[0] / 2, y + 62)
        p.scale(scale * mirror, scale)
        art.draw_spider(p, art.COSTUME_BY_KEY[costume], pose, eyes, view, style=style, hat=hat, t=0.4, J=pose.get("_J"))
        p.restore()
        p.setPen(QColor("#ffffff"))
        p.drawText(x + 8, y + cell[1] - 12, title)
    p.end()
    img.save(path)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "скриншоты")
    os.makedirs(out, exist_ok=True)
    stand = lambda st: art.pose_point("mid", 0, st)
    hats = [(name, "chibi", "classic", art.get_pose("hang", "chibi"), "open", "front", key, 1)
            for key, name, _ in art.HATS]
    sheet(os.path.join(out, "галерея_головные_уборы.png"), hats, 7)
    cos = [(c["name"], "chibi", c["key"], art.get_pose("star", "chibi"), "open", "front", None, 1)
           for c in art.COSTUMES]
    sheet(os.path.join(out, "галерея_костюмы.png"), cos, 10, cell=(200, 300), scale=1.8)
    st = "chibi"

    def crawl(ph):
        pose = art.pose_crawl(st)
        pose["_J"] = art.crawl_joints(st, art.fk(st, pose), art.crawl_targets(ph))
        return pose
    poses = [("вис + кофе", st, "classic", art.pose_hang(st, 0, "mug", 0), "open", "front", None, 1),
             ("глоток", st, "classic", art.pose_hang(st, 0, "mug", 1), "open", "front", None, 1),
             ("ползёт: левая вперёд", st, "classic", crawl(math.pi / 2), "squint", "top", None, 1),
             ("ползёт: правая вперёд", st, "classic", crawl(-math.pi / 2), "squint", "top", None, 1),
             ("noir: стоит", st, "noir", art.get_pose("hang", st), "open", "front", "fedora", 1),
             ("noir: гитара", st, "classic", art.get_pose("guitar", st), "open", "front", None, 1),
             ("сон (вверх ногами)", st, "classic", art.get_pose("sleep", st), "sleep", "front", None, 1),
             ("сидит на окне", st, "pajama", art.get_pose("sit", st), "sleep", "front", "nightcap", 1),
             ("голова кругом", st, "classic", art.get_pose("star", st), "dizzy", "front", None, 1),
             ("дай пять", st, "classic", art.get_pose("five", st), "open", "front", None, 1),
             ("подушка", st, "classic", art.get_pose("pillow", st), "open", "front", None, 1),
             ("мем: левый", st, "classic", art.pose_point("left", 0, st), "open", "front", None, 1),
             ("мем: средний", st, "classic", art.pose_point("mid", 0, st), "open", "front", None, 1),
             ("мем: спиной", st, "classic", art.pose_point("back", 0, st), "open", "back", None, -1)]
    sheet(os.path.join(out, "галерея_позы.png"), poses, 10, cell=(210, 300), scale=1.9)
    print("ok", out)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    main()
