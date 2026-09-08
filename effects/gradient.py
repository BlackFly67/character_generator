# -*- coding: utf-8 -*-
"""
Градиентная заливка
"""

import numpy as np
import math
from PIL import Image
from utils import get_color_rgba


def sample_gradient_color(sorted_stops, t):
    """
    Возвращает RGBA-цвет градиента в точке t (0..1).
    """
    if t <= sorted_stops[0]["pos"]:
        return get_color_rgba(sorted_stops[0]["color"])
    if t >= sorted_stops[-1]["pos"]:
        return get_color_rgba(sorted_stops[-1]["color"])
    
    for i in range(len(sorted_stops) - 1):
        s0, s1 = sorted_stops[i], sorted_stops[i + 1]
        if s0["pos"] <= t <= s1["pos"]:
            span = s1["pos"] - s0["pos"]
            local_t = 0.0 if span <= 0 else (t - s0["pos"]) / span
            c0 = get_color_rgba(s0["color"])
            c1 = get_color_rgba(s1["color"])
            return (
                int(c0[0] + (c1[0] - c0[0]) * local_t),
                int(c0[1] + (c1[1] - c0[1]) * local_t),
                int(c0[2] + (c1[2] - c0[2]) * local_t),
                int(c0[3] + (c1[3] - c0[3]) * local_t),
            )
    return get_color_rgba(sorted_stops[-1]["color"])


def build_gradient_lut(sorted_stops, steps=256):
    """
    Строит таблицу цветов для градиента.
    """
    return np.array(
        [sample_gradient_color(sorted_stops, i / (steps - 1)) for i in range(steps)],
        dtype=np.uint8,
    )


def apply_gradient_fill(image, mask, stops, gradient_type, angle_degrees=0):
    """
    Применяет градиентную заливку к изображению.
    """
    if mask is None or not stops:
        return image
    
    w, h = mask.size
    sorted_stops = sorted(stops, key=lambda s: s["pos"])
    cx, cy = w / 2.0, h / 2.0
    theta = math.radians(angle_degrees)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    
    y_idx, x_idx = np.mgrid[0:h, 0:w]
    dx = x_idx.astype(np.float64) - cx
    dy = y_idx.astype(np.float64) - cy
    u = dx * cos_t + dy * sin_t
    v = -dx * sin_t + dy * cos_t
    
    # Вычисление границ для нормализации
    corners_dx = np.array([0.0, w, 0.0, w]) - cx
    corners_dy = np.array([0.0, 0.0, h, h]) - cy
    corners_u = corners_dx * cos_t + corners_dy * sin_t
    corners_v = -corners_dx * sin_t + corners_dy * cos_t
    u_min, u_max = float(corners_u.min()), float(corners_u.max())
    half_u = max(abs(u_min), abs(u_max)) or 1.0
    half_v = max(abs(float(corners_v.min())), abs(float(corners_v.max()))) or 1.0
    
    # Вычисление t в зависимости от типа градиента
    if gradient_type == "radial":
        radial_max_radius = math.hypot(cx, cy) or 1.0
        t = np.hypot(dx, dy) / radial_max_radius
    elif gradient_type == "angle":
        phi = (np.degrees(np.arctan2(dy, dx)) - angle_degrees) % 360
        t = phi / 360.0
    elif gradient_type == "reflected":
        t = np.abs(u) / half_u
    elif gradient_type == "diamond":
        t = (np.abs(u) / half_u + np.abs(v) / half_v) / 2.0
    else:  # linear
        t = (u - u_min) / (u_max - u_min) if u_max != u_min else np.zeros_like(u)
    
    t = np.clip(t, 0.0, 1.0)
    lut = build_gradient_lut(sorted_stops)
    idx = np.clip((t * (len(lut) - 1)).astype(np.int32), 0, len(lut) - 1)
    rgba = lut[idx]
    
    # Комбинируем альфу из градиента и маски
    mask_arr = np.asarray(mask, dtype=np.float32) / 255.0
    stop_alpha = rgba[:, :, 3].astype(np.float32) / 255.0
    combined_alpha = np.clip(mask_arr * stop_alpha * 255.0, 0, 255).astype(np.uint8)
    
    gradient = Image.fromarray(np.dstack([rgba[:, :, :3], combined_alpha]))
    return Image.alpha_composite(image, gradient)