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
            # ИСПРАВЛЕНО (баг №2): раньше здесь зона циклического
            # "заворота" (np.roll) зануляла ТОЛЬКО цветовые каналы
            # (r_shifted/b_shifted = 0), а итоговая альфа бралась как
            # max(a, a_shifted_r, a_shifted_b). При прозрачном фоне
            # исходная a в этой зоне была 0 и артефакт был не виден.
            # При НЕПРОЗРАЧНОМ фоне исходная a = 255 везде, и max()
            # всегда восстанавливал полную непрозрачность поверх
            # занулённого (чёрного) цвета - отсюда видимые
            # цветные (циан/жёлтая) полосы на сплошном фоне, а если
            # символ стоял у самого края холста, тем же способом
            # обрезался и реальный контент символа (баг №1).
            # Вместо зануления подставляем в wrap-зону исходные
            # (несдвинутые) пиксели канала и альфы - классический
            # edge-clamp для фильтров канального сдвига. Он не
            # протекает на фон ни при прозрачном, ни при непрозрачном
            # фоне, и не съедает контент персонажа у края холста.
            r_shifted[:, :shift] = r[:, :shift]
            a_shifted_r[:, :shift] = a[:, :shift]
            b_shifted[:, w - shift:] = b[:, w - shift:]
            a_shifted_b[:, w - shift:] = a[:, w - shift:]
        
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
                    original_band = arr[y:y + band_h].copy()
                    band = np.roll(original_band, offset, axis=1)
                    # ИСПРАВЛЕНО (баг №2): раньше wrap-зона полосы
                    # зануляла ВСЕ 4 канала сразу (band[:, :offset] = 0
                    # включая альфу), что на непрозрачном фоне
                    # пробивало прозрачную дыру прямо в сплошном фоне.
                    # Возвращаем в эту зону исходные (несдвинутые)
                    # пиксели полосы (включая альфу) вместо зануления -
                    # полоса всё так же визуально "рвётся"/сдвигается,
                    # но её wrap-край не протекает на фон и не создаёт
                    # дыр там, где их не должно быть.
                    if offset > 0:
                        band[:, :offset] = original_band[:, :offset]
                    else:
                        band[:, offset:] = original_band[:, offset:]
                    arr[y:y + band_h] = band
            y += band_h
    
    return Image.fromarray(arr)
