# -*- coding: utf-8 -*-
"""
Свечение (внешнее и внутреннее)
"""

from PIL import Image, ImageFilter, ImageChops
from utils import get_color_rgb, blend_layers


def apply_outer_glow(image, mask, color, radius, intensity, blend_mode="normal"):
    """
    Применяет внешнее свечение.
    """
    glow_rgb = get_color_rgb(color)
    glow_mask = mask.filter(ImageFilter.GaussianBlur(radius=radius))
    
    intensity_factor = intensity / 10.0
    if intensity_factor != 1.0:
        glow_mask = glow_mask.point(lambda p: min(255, int(p * intensity_factor)))
    
    glow_mask = ImageChops.subtract(glow_mask, mask)
    glow_layer = Image.new("RGBA", image.size, glow_rgb + (255,))
    glow_layer.putalpha(glow_mask)
    
    return Image.alpha_composite(glow_layer, image)


def apply_inner_glow(image, mask, color, radius, intensity, blend_mode="normal"):
    """
    Применяет внутреннее свечение.
    """
    blurred = mask.filter(ImageFilter.GaussianBlur(radius=radius))
    glow_mask = ImageChops.invert(blurred)
    glow_mask = ImageChops.multiply(glow_mask, mask)
    
    if intensity != 10:
        factor = intensity / 10.0
        glow_mask = glow_mask.point(lambda p: min(255, int(p * factor)))
    
    glow_rgb = get_color_rgb(color)
    glow_layer = Image.new("RGBA", image.size, glow_rgb + (255,))
    glow_layer.putalpha(glow_mask)
    
    return blend_layers(image, glow_layer, blend_mode)


def apply_outer_glow_with_source(image, mask, color, radius, intensity, 
                                 transparent_text, outline_outer_drawn, outline_mask=None):
    """
    Применяет внешнее свечение с учётом источника (заливка или обводка).
    """
    if not transparent_text or outline_outer_drawn:
        source_mask = outline_mask if outline_outer_drawn else mask
        return apply_outer_glow(image, source_mask, color, radius, intensity)
    return image