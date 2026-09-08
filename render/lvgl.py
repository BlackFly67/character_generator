# -*- coding: utf-8 -*-
"""
Экспорт в формат LVGL (.bin)
"""

import struct
import numpy as np


def save_lvgl_v8_bin(rgba_array, filename, color_depth=32, has_alpha=True, swap_16=False):
    """
    Сохраняет изображение в формате LVGL v8/v9 .bin.
    """
    # PIL отдаёт RGBA - переводим в BGRA
    img = rgba_array[:, :, [2, 1, 0, 3]].copy()
    height, width = img.shape[:2]
    
    cf = 5 if has_alpha else 4  # LV_IMG_CF_TRUE_COLOR_ALPHA или LV_IMG_CF_TRUE_COLOR
    
    # Формирование заголовка
    header_int = (cf & 0x1F) | ((width & 0x7FF) << 10) | ((height & 0x7FF) << 21)
    header = struct.pack('<I', header_int)
    
    with open(filename, "wb") as f:
        f.write(header)
        
        if color_depth == 16:
            b = img[:, :, 0].astype(np.uint16)
            g = img[:, :, 1].astype(np.uint16)
            r = img[:, :, 2].astype(np.uint16)
            a = img[:, :, 3].astype(np.uint8)
            
            rgb565 = (((r >> 3) & 0x1F) << 11) | (((g >> 2) & 0x3F) << 5) | ((b >> 3) & 0x1F)
            
            if has_alpha:
                out_img = np.empty((height, width, 3), dtype=np.uint8)
                if swap_16:
                    out_img[:, :, 0] = (rgb565 >> 8) & 0xFF
                    out_img[:, :, 1] = rgb565 & 0xFF
                else:
                    out_img[:, :, 0] = rgb565 & 0xFF
                    out_img[:, :, 1] = (rgb565 >> 8) & 0xFF
                out_img[:, :, 2] = a
            else:
                out_img = np.empty((height, width, 2), dtype=np.uint8)
                if swap_16:
                    out_img[:, :, 0] = (rgb565 >> 8) & 0xFF
                    out_img[:, :, 1] = rgb565 & 0xFF
                else:
                    out_img[:, :, 0] = rgb565 & 0xFF
                    out_img[:, :, 1] = (rgb565 >> 8) & 0xFF
            
            f.write(out_img.tobytes())
        
        elif color_depth == 32:
            if not has_alpha:
                img[:, :, 3] = 0xFF
            f.write(img.tobytes())