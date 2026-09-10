# -*- coding: utf-8 -*-
"""
Отражение (Reflection) — зеркальная затухающая копия под символом.
"""

from PIL import Image
import numpy as np

from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT,
)


class Reflection(EffectBase):
    id = "reflection"
    label_key = "reflection"
    stage = "post"
    params = [
        ParamSpec("enabled", "reflection",         CTRL_CHECKBOX, False),
        ParamSpec("gap",     "reflection_gap",     CTRL_INT,      2, -500, 500),
        ParamSpec("opacity", "reflection_opacity", CTRL_INT,      50, 0, 100),
        ParamSpec("fade",    "reflection_fade",    CTRL_INT,      100, 1, 100),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        char_layer = ctx.extra.get("char_layer")
        paste_x = ctx.extra.get("paste_x")
        paste_y = ctx.extra.get("paste_y")
        if char_layer is None or paste_x is None or paste_y is None:
            return ctx.image

        gap = int(self._get(ctx, "gap", 2))
        opacity = int(self._get(ctx, "opacity", 50)) / 100.0
        fade = int(self._get(ctx, "fade", 100)) / 100.0

        return apply_reflection(
            ctx.image, char_layer, paste_x, paste_y,
            ctx.settings.background_color,
            gap, opacity, fade,
        )


# ============================================================
#  Старая функция — копия прежней версии.
# ============================================================

def apply_reflection(final_img, content_layer, paste_x, paste_y, background_color,
                      gap, opacity, fade_fraction):
    """
    Применяет зеркальное отражение под символом.
    """
    if content_layer.width <= 0 or content_layer.height <= 0 or opacity <= 0:
        return final_img

    alpha_bbox = content_layer.split()[3].getbbox()
    if alpha_bbox is None:
        return final_img

    left, upper, right, lower = alpha_bbox
    visible = content_layer.crop((left, upper, right, lower))
    reflected = visible.transpose(Image.FLIP_TOP_BOTTOM)
    rw, rh = reflected.size

    # Вертикальный градиент затухания
    r, g, b, a = reflected.split()
    fade_h = max(1, min(rh, int(round(rh * max(0.01, min(1.0, fade_fraction))))))
    grad = np.linspace(opacity, 0.0, fade_h, dtype=np.float64)
    if rh > fade_h:
        grad = np.concatenate([grad, np.zeros(rh - fade_h, dtype=np.float64)])

    alpha_arr = np.asarray(a, dtype=np.float64)
    new_alpha = np.clip(alpha_arr * grad.reshape(-1, 1), 0, 255).astype(np.uint8)
    reflected.putalpha(Image.fromarray(new_alpha))

    # Позиция отражения
    refl_x = paste_x + left
    refl_y = max(0, paste_y + lower + gap)
    new_w = final_img.width
    new_h = max(final_img.height, refl_y + rh)

    # Создаём новый холст
    if background_color is None:
        new_canvas = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    else:
        if isinstance(background_color, str) and background_color.startswith('#'):
            bg_col = tuple(int(background_color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (255,)
        elif isinstance(background_color, str):
            bg_col = (255, 255, 255, 255) if background_color == "white" else (0, 0, 0, 255)
        else:
            bg_col = background_color
        new_canvas = Image.new("RGBA", (new_w, new_h), bg_col)

    # Вставляем оригинал и отражение
    new_canvas.paste(final_img, (0, 0), final_img)
    new_canvas.alpha_composite(reflected, (refl_x, refl_y))

    return new_canvas