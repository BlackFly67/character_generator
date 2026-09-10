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
        # ИСПРАВЛЕНО (баг №3): раньше цикл шёл в АБСОЛЮТНЫХ пикселях
        # (y += band_h, где band_h - целое число пикселей, зависящее
        # от h). Превью пересчитывает эффект на холсте, размер
        # которого меняется вместе с ползунком зума (disp_w/disp_h), и
        # при том же seed, но другом h, цикл "while y < h" делал ДРУГОЕ
        # число итераций - вся последовательность значений,
        # вынимаемых из rng (позиция/высота полосы, решение
        # рисовать/не рисовать, величина сдвига), сбивалась, и рисунок
        # полос визуально "прыгал" при каждом движении ползунка зума,
        # хотя пользователь не менял настройки глитча. Ведём прогресс
        # цикла по ДОЛЕ высоты (0..1) - она одинакова для любого
        # размера холста при одном seed, поэтому число и порядок
        # обращений к rng больше не зависят от w/h. Конкретные
        # пиксельные y/band_h/offset по-прежнему пересчитываются под
        # текущий размер холста, так что сила эффекта продолжает
        # корректно масштабироваться вместе с остальными эффектами
        # превью - меняется только "разрешение" отрисовки, а не сам
        # случайный узор.
        min_band_frac, max_band_frac = 0.02, 0.12
        y_frac = 0.0
        while y_frac < 1.0:
            band_h_frac = rng.uniform(min_band_frac, max_band_frac)
            y = int(round(y_frac * h))
            band_h = max(1, int(round(band_h_frac * h)))
            band_h = min(band_h, h - y)
            
            if band_h > 0 and rng.random_sample() < (0.15 + 0.5 * intensity):
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
            y_frac += band_h_frac
    
    return Image.fromarray(arr)
