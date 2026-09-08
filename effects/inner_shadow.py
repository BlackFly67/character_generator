# -*- coding: utf-8 -*-
"""
Внутренняя тень (Inner Shadow)
"""

from PIL import Image, ImageFilter, ImageChops
from utils import get_color_rgb, get_shadow_offset, blend_layers


def apply_inner_shadow(image, mask, color, distance, direction, blur, blend_mode="normal"):
    """
    Применяет внутреннюю тень.
    """
    if distance == 0:
        return image
    
    shadow_rgb = get_color_rgb(color)
    shadow_offset_x, shadow_offset_y = get_shadow_offset(direction, distance)
    
    # Создаём смещённую маску
    shifted_mask = Image.new("L", mask.size, 0)
    shifted_mask.paste(mask, (shadow_offset_x, shadow_offset_y))
    
    # Вычитаем смещённую маску из оригинальной
    shadow_mask = ImageChops.subtract(mask, shifted_mask)
    
    # Размытие
    if blur > 0:
        shadow_mask = shadow_mask.filter(ImageFilter.GaussianBlur(radius=blur))
    
    # Ограничиваем тень внутри маски
    shadow_mask = ImageChops.multiply(shadow_mask, mask)
    
    # Создаём слой тени
    shadow_layer = Image.new("RGBA", image.size, shadow_rgb + (255,))
    shadow_layer.putalpha(shadow_mask)
    
    return blend_layers(image, shadow_layer, blend_mode)