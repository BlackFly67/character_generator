# -*- coding: utf-8 -*-
"""
Внешняя тень
"""

from PIL import Image, ImageFilter, ImageChops
from utils import get_color_rgb, get_shadow_offset, blend_layers


def apply_shadow(char_layer, canvas_w, canvas_h, offset_x, offset_y, rot_base_w, rot_base_h,
                 shadow_enabled, shadow_color, shadow_distance, shadow_direction, shadow_blur,
                 shadow_blend_mode, transparent_text, background_color):
    """
    Применяет внешнюю тень к символу.
    Возвращает кортеж (shadow_layer, paste_x, paste_y, effective_blend) или
    (None, 0, 0, "normal") если тень отключена.
    """
    if not shadow_enabled:
        # ИСПРАВЛЕНО (ошибка №6): раньше здесь возвращался тюпл из 3
        # элементов (None, 0, 0), а "успешная" ветка ниже возвращает 4
        # элемента (..., effective_blend). Любая распаковка вида
        # "a, b, c, d = apply_shadow(...)" падала с ValueError при
        # shadow_enabled=False. Выравниваем арность возврата.
        return None, 0, 0, "normal"
    
    shadow_rgb = get_color_rgb(shadow_color)
    transp_shadow_bg = shadow_rgb + (0,) if not transparent_text else (0, 0, 0, 0)
    
    shadow_mask = char_layer.split()[3]
    shadow_layer = Image.new("RGBA", char_layer.size, shadow_rgb + (255,))
    shadow_layer.putalpha(shadow_mask)
    
    if shadow_blur > 0:
        shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
    
    shadow_offset_x, shadow_offset_y = get_shadow_offset(shadow_direction, shadow_distance)
    
    paste_x = offset_x + (rot_base_w - char_layer.width) // 2
    paste_y = offset_y + (rot_base_h - char_layer.height) // 2
    
    shadow_final = Image.new("RGBA", (canvas_w, canvas_h), transp_shadow_bg)
    shadow_final.paste(shadow_layer, (paste_x + shadow_offset_x, paste_y + shadow_offset_y))
    
    # Определяем эффективный режим смешивания
    effective_blend = shadow_blend_mode
    if background_color is None and shadow_blend_mode in ("multiply", "overlay"):
        effective_blend = "normal"
    
    return shadow_final, paste_x, paste_y, effective_blend
