# -*- coding: utf-8 -*-
"""
Обводка (внешняя и внутренняя)
"""

from PIL import Image, ImageFilter, ImageChops
from utils import get_color_rgb


def apply_outer_outline(image, mask, color, width):
    """
    Применяет внешнюю обводку к изображению.
    Возвращает (изображение, расширенная_маска).
    """
    if width <= 0:
        return image, mask
    
    outline_rgb = get_color_rgb(color)
    
    # Расширяем маску с помощью фильтра максимума
    kernel_size = int(width * 2) + 1
    expanded = mask.filter(ImageFilter.MaxFilter(size=kernel_size))
    
    # Вычитаем исходную маску из расширенной
    outline_mask = ImageChops.subtract(expanded, mask)
    
    # Создаём слой обводки
    outline_layer = Image.new("RGBA", image.size, outline_rgb + (255,))
    outline_layer.putalpha(outline_mask)
    
    # Композитим
    result = Image.alpha_composite(outline_layer, image)
    
    return result, expanded


def apply_inner_outline(image, mask, color, width):
    """
    Применяет внутреннюю обводку к изображению.
    """
    if width <= 0:
        return image
    
    pad = int(width * 2)
    w, h = image.size
    padded_size = (w + 2 * pad, h + 2 * pad)
    
    # Создаём отступы
    padded_image = Image.new("RGBA", padded_size, (0, 0, 0, 0))
    padded_image.paste(image, (pad, pad))
    
    padded_mask = Image.new("L", padded_size, 0)
    padded_mask.paste(mask, (pad, pad))
    
    outline_rgb = get_color_rgb(color)
    
    # Сужаем маску с помощью фильтра минимума
    kernel_size = int(width * 2) + 1
    shrunk_alpha = padded_mask.filter(ImageFilter.MinFilter(size=kernel_size))
    
    # Вычитаем суженную маску из исходной
    outline_mask = ImageChops.subtract(padded_mask, shrunk_alpha)
    
    # Создаём слой обводки
    outline_layer = Image.new("RGBA", padded_size, outline_rgb + (0,))
    outline_layer.putalpha(outline_mask)
    
    # Композитим
    padded_image.paste(outline_layer, (0, 0), outline_mask)
    
    # Обрезаем обратно
    return padded_image.crop((pad, pad, w + pad, h + pad))