# -*- coding: utf-8 -*-
"""
Глитч / VHS-эффект
"""

import numpy as np
from PIL import Image


def apply_glitch_effect(image, rgb_shift=4, slice_intensity=30, seed=0):
    """
    Применяет глитч-эффект (хроматическая аберрация + разбиение на полосы).
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    w, h = image.size
    if w <= 0 or h <= 0 or (rgb_shift <= 0 and slice_intensity <= 0):
        return image
    
    arr = np.array(image)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]
    
    # 1. Хроматическая аберрация
    if rgb_shift > 0:
        shift = min(rgb_shift, w)
        r_shifted = np.roll(r, shift, axis=1)
        b_shifted = np.roll(b, -shift, axis=1)
        a_shifted_r = np.roll(a, shift, axis=1)
        a_shifted_b = np.roll(a, -shift, axis=1)
        
        if shift > 0:
            r_shifted[:, :shift] = 0
            a_shifted_r[:, :shift] = 0
            b_shifted[:, w - shift:] = 0
            a_shifted_b[:, w - shift:] = 0
        
        a = np.maximum(np.maximum(a, a_shifted_r), a_shifted_b)
        r, b = r_shifted, b_shifted
    
    arr = np.dstack([r, g, b, a])
    
    # 2. Разбиение на полосы
    intensity = max(0.0, min(100.0, slice_intensity)) / 100.0
    if intensity > 0:
        rng = np.random.RandomState(seed)
        max_offset = max(1, int(w * 0.15 * intensity))
        y = 0
        while y < h:
            band_h = rng.randint(max(2, int(h * 0.02)), max(3, int(h * 0.12)) + 1)
            band_h = min(band_h, h - y)
            
            if rng.random_sample() < (0.15 + 0.5 * intensity):
                offset = rng.randint(-max_offset, max_offset + 1)
                if offset != 0:
                    band = np.roll(arr[y:y + band_h], offset, axis=1)
                    if offset > 0:
                        band[:, :offset] = 0
                    else:
                        band[:, offset:] = 0
                    arr[y:y + band_h] = band
            y += band_h
    
    return Image.fromarray(arr)