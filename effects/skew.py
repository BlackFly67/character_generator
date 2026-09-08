# -*- coding: utf-8 -*-
"""
Скос (аффинное искажение)
"""

import math
from PIL import Image


def apply_skew_effect(image, skew_x=0, skew_y=0, fill_color_rgb=(0, 0, 0)):
    """
    Применяет эффект скоса (аффинное искажение).
    """
    if image.mode != "RGBA":
        image = image.convert("RGBA")
    
    def shear_axis(img, angle_deg, horizontal):
        angle_deg = max(-85.0, min(85.0, angle_deg))
        if angle_deg == 0:
            return img
        
        m = math.tan(math.radians(angle_deg))
        iw, ih = img.size
        
        if horizontal:
            extra = int(math.ceil(abs(m) * (ih - 1))) if ih > 1 else 0
            new_w = iw + extra
            offset = extra if m < 0 else 0
            data = (1, -m, -offset, 0, 1, 0)
            new_size = (new_w, ih)
        else:
            extra = int(math.ceil(abs(m) * (iw - 1))) if iw > 1 else 0
            new_h = ih + extra
            offset = extra if m < 0 else 0
            data = (1, 0, 0, -m, 1, -offset)
            new_size = (iw, new_h)
        
        r, g, b, a = img.split()
        r = r.transform(new_size, Image.AFFINE, data, resample=Image.BICUBIC, 
                       fillcolor=fill_color_rgb[0])
        g = g.transform(new_size, Image.AFFINE, data, resample=Image.BICUBIC, 
                       fillcolor=fill_color_rgb[1])
        b = b.transform(new_size, Image.AFFINE, data, resample=Image.BICUBIC, 
                       fillcolor=fill_color_rgb[2])
        a = a.transform(new_size, Image.AFFINE, data, resample=Image.BICUBIC, fillcolor=0)
        
        return Image.merge("RGBA", (r, g, b, a))
    
    out = image
    if skew_x != 0:
        out = shear_axis(out, skew_x, horizontal=True)
    if skew_y != 0:
        out = shear_axis(out, skew_y, horizontal=False)
    
    return out