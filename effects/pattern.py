# -*- coding: utf-8 -*-
"""
Заливка узором/текстурой
"""

import math
import numpy as np
from PIL import Image


def load_pattern_image(path):
    """
    Безопасно загружает изображение-текстуру.
    """
    try:
        return Image.open(path).convert("RGBA")
    except Exception:
        return None


def apply_pattern_fill(image, mask, pattern_img, scale=100, offset_x=0, offset_y=0, 
                       angle=0, blend_mode="normal"):
    """
    Применяет заливку узором.
    """
    from utils import blend_layers
    
    if mask is None or pattern_img is None:
        return image
    
    w, h = mask.size
    if w <= 0 or h <= 0:
        return image
    
    pw, ph = pattern_img.size
    if pw <= 0 or ph <= 0:
        return image
    
    scale_factor = max(0.01, scale / 100.0)
    eff_pw = max(1.0, pw * scale_factor)
    eff_ph = max(1.0, ph * scale_factor)
    
    cx, cy = w / 2.0, h / 2.0
    theta = math.radians(angle)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    
    y_idx, x_idx = np.mgrid[0:h, 0:w]
    dx = x_idx.astype(np.float64) - cx - offset_x
    dy = y_idx.astype(np.float64) - cy - offset_y
    
    u = dx * cos_t + dy * sin_t
    v = -dx * sin_t + dy * cos_t
    
    tile_x = np.mod(u, eff_pw) / scale_factor
    tile_y = np.mod(v, eff_ph) / scale_factor
    
    src_x = np.clip(tile_x.astype(np.int32), 0, pw - 1)
    src_y = np.clip(tile_y.astype(np.int32), 0, ph - 1)
    
    pattern_arr = np.asarray(pattern_img, dtype=np.uint8)
    rgba = pattern_arr[src_y, src_x]
    
    mask_arr = np.asarray(mask, dtype=np.float32) / 255.0
    pat_alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    combined_alpha = np.clip(mask_arr * pat_alpha * 255.0, 0, 255).astype(np.uint8)
    
    pattern_layer = Image.fromarray(np.dstack([rgba[:, :, :3], combined_alpha]))
    
    return blend_layers(image, pattern_layer, blend_mode)