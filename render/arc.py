# -*- coding: utf-8 -*-
"""
Рендер текста по дуге/окружности
"""

import math
from PIL import Image, ImageDraw, ImageChops


def render_arc_text_mask(text, font, radius, start_angle_deg, clockwise=True, 
                         flip=False, alignment="center", letter_spacing=0):
    """
    Строит маску текста, расположенного по дуге/окружности.
    
    Args:
        text: строка для рендера
        font: шрифт (ImageFont)
        radius: радиус окружности в пикселях
        start_angle_deg: начальный угол в градусах (0 = верх, 12 часов)
        clockwise: True = купол (центр снизу), False = чаша (центр сверху)
        flip: перевернуть текст на 180°
        alignment: "left", "center", "right" - выравнивание относительно start_angle
        letter_spacing: дополнительный межбуквенный интервал в пикселях
    
    Returns:
        tuple: (mask, anchor_x, anchor_y)
            mask: Image в режиме 'L' с маской текста
            anchor_x, anchor_y: координаты центра окружности в системе координат маски
    """
    if not text or radius <= 0:
        return Image.new("L", (1, 1), 0), 0, 0
    
    if flip:
        text = text[::-1]
    
    temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    
    # Собираем метрики букв
    widths = []
    max_asc = 0
    max_desc = 0
    
    for ch in text:
        bbox = temp_draw.textbbox((0, 0), ch, font=font, anchor="ls")
        widths.append(max(1, bbox[2] - bbox[0]))
        max_asc = max(max_asc, -bbox[1])
        max_desc = max(max_desc, bbox[3])
    
    # Угловой шаг от letter_spacing
    spacing_angle = math.degrees(letter_spacing / radius) if radius > 0 else 0
    total_arc_len = sum(widths) + max(0, len(text) - 1) * letter_spacing
    total_angle = math.degrees(total_arc_len / radius) if radius > 0 else 0
    
    # Начальный угол в зависимости от выравнивания
    if alignment == "center":
        angle_cursor = start_angle_deg - total_angle / 2.0
    elif alignment == "left":
        angle_cursor = start_angle_deg
    else:  # right
        angle_cursor = start_angle_deg - total_angle
    
    # Первый проход: вычисляем позиции всех букв
    placements = []
    min_x = min_y = float("inf")
    max_x = max_y = float("-inf")
    
    for ch, ch_width in zip(text, widths):
        char_angle_span = math.degrees(ch_width / radius) if radius > 0 else 0
        char_center_angle = angle_cursor + char_angle_span / 2.0
        
        # 0° = верх (12 часов), по часовой стрелке
        theta_math = math.radians(90 - char_center_angle)
        px = radius * math.cos(theta_math)
        
        if clockwise:
            # Купол: центр окружности снизу текста
            py = -radius * math.sin(theta_math)
            base_rotation = char_center_angle
        else:
            # Чаша: центр окружности сверху текста
            py = radius * math.sin(theta_math)
            base_rotation = -char_center_angle
        
        # Создаём глиф буквы
        glyph_bbox = temp_draw.textbbox((0, 0), ch, font=font, anchor="ls")
        gw = glyph_bbox[2] - glyph_bbox[0]
        pad = 4
        
        glyph_img = Image.new("L", (gw + pad * 2, max_asc + max_desc + pad * 2), 0)
        gdraw = ImageDraw.Draw(glyph_img)
        gdraw.text((pad - glyph_bbox[0], pad + max_asc), ch, 
                   font=font, anchor="ls", fill=255)
        
        rotation_deg = base_rotation + (180 if flip else 0)
        rotated = glyph_img.rotate(-rotation_deg, resample=Image.BICUBIC, 
                                   expand=True, fillcolor=0)
        
        placements.append((rotated, px, py))
        min_x = min(min_x, px - rotated.width / 2)
        max_x = max(max_x, px + rotated.width / 2)
        min_y = min(min_y, py - rotated.height / 2)
        max_y = max(max_y, py + rotated.height / 2)
        
        angle_cursor += char_angle_span + spacing_angle
    
    # Второй проход: создаём холст и вставляем буквы
    canvas_w = max(1, int(math.ceil(max_x - min_x)))
    canvas_h = max(1, int(math.ceil(max_y - min_y)))
    canvas = Image.new("L", (canvas_w, canvas_h), 0)
    
    for rotated, px, py in placements:
        paste_x = int(round(px - min_x - rotated.width / 2))
        paste_y = int(round(py - min_y - rotated.height / 2))
        
        # Соседние буквы могут перекрываться - берём максимум
        region = canvas.crop((paste_x, paste_y, 
                             paste_x + rotated.width, 
                             paste_y + rotated.height))
        canvas.paste(ImageChops.lighter(region, rotated), (paste_x, paste_y))
    
    # Координаты центра окружности в системе координат маски
    anchor_x = int(round(-min_x))
    anchor_y = int(round(-min_y))
    
    return canvas, anchor_x, anchor_y