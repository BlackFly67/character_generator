# -*- coding: utf-8 -*-
"""
Перспектива (Perspective) — настоящее проективное искажение.
"""

import math
from PIL import Image

from utils import get_color_rgb
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT,
)


class Perspective(EffectBase):
    id = "perspective"
    label_key = "perspective"
    stage = "geometry"
    params = [
        ParamSpec("enabled", "perspective",   CTRL_CHECKBOX, False),
        ParamSpec("x",       "perspective_x", CTRL_INT,      0, -50, 50),
        ParamSpec("y",       "perspective_y", CTRL_INT,      0, -50, 50),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        px = int(self._get(ctx, "x", 0))
        py = int(self._get(ctx, "y", 0))
        if px == 0 and py == 0:
            return ctx.image
        rgb = get_color_rgb(ctx.settings.text_color)
        return apply_perspective_effect(ctx.image, px, py, rgb)


# ============================================================
#  Старая функция — оставляем как есть (копия прежнего кода).
# ============================================================

def find_coeffs(pa, pb):
    matrix = []
    for p1, p2 in zip(pa, pb):
        matrix.append([p1[0], p1[1], 1, 0, 0, 0, -p2[0]*p1[0], -p2[0]*p1[1]])
        matrix.append([0, 0, 0, p1[0], p1[1], 1, -p2[1]*p1[0], -p2[1]*p1[1]])

    A = [matrix[i] for i in range(8)]

    def gauss(A, B):
        n = len(B)
        for i in range(n):
            maxEl = abs(A[i][i])
            maxRow = i
            for k in range(i + 1, n):
                if abs(A[k][i]) > maxEl:
                    maxEl = abs(A[k][i])
                    maxRow = k
            for k in range(i, n):
                A[maxRow][k], A[i][k] = A[i][k], A[maxRow][k]
            B[maxRow], B[i] = B[i], B[maxRow]
            for k in range(i + 1, n):
                c = -A[k][i] / A[i][i]
                for j in range(i, n):
                    if i == j:
                        A[k][j] = 0
                    else:
                        A[k][j] += c * A[i][j]
                B[k] += c * B[i]
        x = [0 for _ in range(n)]
        for i in range(n - 1, -1, -1):
            x[i] = B[i] / A[i][i]
            for k in range(i - 1, -1, -1):
                B[k] -= A[k][i] * x[i]
        return x

    B = [val for pair in zip((p[0] for p in pb), (p[1] for p in pb)) for val in pair]
    return gauss(A, B)


def apply_perspective_effect(image, perspective_x=0, perspective_y=0, fill_color_rgb=(0, 0, 0)):
    """Копия из прежней версии — без изменений."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    p_x = max(-50.0, min(50.0, perspective_x)) / 100.0
    p_y = max(-50.0, min(50.0, perspective_y)) / 100.0
    if p_x == 0 and p_y == 0:
        return image
    iw, ih = image.size
    if iw <= 0 or ih <= 0:
        return image
    src_points = [(0, 0), (0, ih), (iw, ih), (iw, 0)]
    tl_x, tl_y = 0.0, 0.0
    bl_x, bl_y = 0.0, float(ih)
    br_x, br_y = float(iw), float(ih)
    tr_x, tr_y = float(iw), 0.0
    inset_x = abs(p_x) * (iw / 2.0)
    inset_y = abs(p_y) * (ih / 2.0)
    if p_x > 0:
        tl_x += inset_x
        tr_x -= inset_x
    elif p_x < 0:
        bl_x += inset_x
        br_x -= inset_x
    if p_y > 0:
        tr_y += inset_y
        br_y -= inset_y
    elif p_y < 0:
        tl_y += inset_y
        bl_y -= inset_y
    dst_points = [(tl_x, tl_y), (bl_x, bl_y), (br_x, br_y), (tr_x, tr_y)]
    coeffs = find_coeffs(dst_points, src_points)
    r, g, b, a = image.split()
    r = r.transform((iw, ih), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC, fillcolor=fill_color_rgb[0])
    g = g.transform((iw, ih), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC, fillcolor=fill_color_rgb[1])
    b = b.transform((iw, ih), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC, fillcolor=fill_color_rgb[2])
    a = a.transform((iw, ih), Image.PERSPECTIVE, coeffs, resample=Image.BICUBIC, fillcolor=0)
    return Image.merge("RGBA", (r, g, b, a))