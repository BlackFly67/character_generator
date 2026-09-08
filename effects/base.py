# -*- coding: utf-8 -*-
"""
Базовые функции для эффектов
"""

from PIL import Image, ImageChops
from utils import (
    get_color_rgb, 
    get_color_rgba, 
    get_shadow_offset, 
    blend_layers, 
    rotate_cleanly,
    create_checkerboard_background
)


# Экспортируем всё для удобства
__all__ = [
    'get_color_rgb',
    'get_color_rgba',
    'get_shadow_offset',
    'blend_layers',
    'rotate_cleanly',
    'create_checkerboard_background',
]