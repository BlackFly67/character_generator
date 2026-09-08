# -*- coding: utf-8 -*-
"""
Растровая заливка точками (Halftone)
"""

import math
import numpy as np
from PIL import Image, ImageDraw


def apply_halftone(mask, cell_size, dot_scale, angle_degrees=0, supersample=3):
    """
    Превращает маску в растр из точек.
    """
    if cell_size <= 0:
        return mask
    
    w, h = mask.size
    angle_degrees = angle_degrees % 360
    
    # Поворот маски для учёта угла
    if angle_degrees != 0:
        rotated = mask.rotate(-angle_degrees, resample=Image.BICUBIC, expand=True, fillcolor=0)
    else:
        rotated = mask
    
    rw, rh = rotated.size
    arr = np.asarray(rotated, dtype=np.float32)
    
    ss = max(1, int(supersample))
    max_radius_ss = (cell_size * max(0.0, dot_scale) / 100.0) / 2.0 * ss
    out_ss = Image.new("L", (rw * ss, rh * ss), 0)
    draw = ImageDraw.Draw(out_ss)
    
    y = 0
    while y < rh:
        y0, y1 = y, min(rh, y + cell_size)
        cy_ss = (y + cell_size / 2.0) * ss
        x = 0
        while x < rw:
            x0, x1 = x, min(rw, x + cell_size)
            cx_ss = (x + cell_size / 2.0) * ss
            cell = arr[y0:y1, x0:x1]
            coverage = float(cell.mean()) / 255.0 if cell.size else 0.0
            radius = max_radius_ss * coverage
            if radius >= 0.5:
                draw.ellipse([cx_ss - radius, cy_ss - radius, 
                             cx_ss + radius, cy_ss + radius], fill=255)
            x += cell_size
        y += cell_size
    
    out = out_ss.resize((rw, rh), Image.Resampling.LANCZOS)
    
    # Обратный поворот
    if angle_degrees != 0:
        out = out.rotate(angle_degrees, resample=Image.BICUBIC, expand=True, fillcolor=0)
        ow, oh = out.size
        left = max(0, (ow - w) // 2)
        top = max(0, (oh - h) // 2)
        out = out.crop((left, top, left + w, top + h))
        if out.size != (w, h):
            canvas = Image.new("L", (w, h), 0)
            canvas.paste(out, ((w - out.width) // 2, (h - out.height) // 2))
            out = canvas
    
    return out