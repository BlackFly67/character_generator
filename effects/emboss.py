# -*- coding: utf-8 -*-
"""
Тиснение (Emboss)
"""

from PIL import Image, ImageFilter, ImageChops
from utils import get_color_rgb


def apply_emboss(image, mask, depth, blur, highlight_color, shadow_color):
    """
    Применяет эффект тиснения.
    """
    hl_rgb = get_color_rgb(highlight_color)
    sh_rgb = get_color_rgb(shadow_color)
    
    # Смещение для подсветки
    shifted_down_right = Image.new("L", mask.size, 0)
    shifted_down_right.paste(mask, (depth, depth))
    hl_mask = ImageChops.subtract(mask, shifted_down_right)
    
    # Смещение для тени
    shifted_up_left = Image.new("L", mask.size, 0)
    shifted_up_left.paste(mask, (-depth, -depth))
    sh_mask = ImageChops.subtract(mask, shifted_up_left)
    
    # Размытие
    if blur > 0:
        hl_mask = hl_mask.filter(ImageFilter.GaussianBlur(radius=blur))
        sh_mask = sh_mask.filter(ImageFilter.GaussianBlur(radius=blur))
        hl_mask = Image.composite(hl_mask, Image.new('L', mask.size, 0), mask)
        sh_mask = Image.composite(sh_mask, Image.new('L', mask.size, 0), mask)
    
    # Создаём слои
    hl_layer = Image.new("RGBA", image.size, hl_rgb + (255,))
    sh_layer = Image.new("RGBA", image.size, sh_rgb + (255,))
    hl_layer.putalpha(hl_mask)
    sh_layer.putalpha(sh_mask)
    
    # Композитим
    out = Image.alpha_composite(image, hl_layer)
    out = Image.alpha_composite(out, sh_layer)
    
    return out