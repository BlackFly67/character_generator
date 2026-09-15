# -*- coding: utf-8 -*-
"""
Внешняя тень (Outer Shadow).

Особенность: этот эффект работает не с char_layer, а с final_img —
итоговым холстом (фон + тень + текст). Поэтому он НЕ участвует в
_run_stage() и НЕ входит в PIPELINE. Он зарегистрирован в
POST_COMPOSE_EFFECTS (effects/registry.py) и вызывается вручную из
compose_full (шаг 14).

UI строится автоматически через auto_sidebar.build_effect_sections —
см. ui/sidebar.py, вызов build_effect_sections(..., order=["shadow"]).
"""

from PIL import Image, ImageFilter

from utils import get_color_rgb, get_shadow_offset, blend_layers
from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT, CTRL_COLOR, CTRL_BLEND, CTRL_DIR,
)


class ShadowOuter(EffectBase):
    """Внешняя тень (Outer Shadow)."""

    id = "shadow"
    label_key = "shadow"
    stage = "post_compose"
    params = [
        ParamSpec("enabled",    "shadow",           CTRL_CHECKBOX, False),
        ParamSpec("color",      "shadow_color",     CTRL_COLOR,    "#000000"),
        ParamSpec("distance",   "shadow_distance",  CTRL_INT,      5, 0, 50),
        ParamSpec("direction",  "shadow_direction", CTRL_DIR,      8),
        ParamSpec("blur",       "shadow_blur",      CTRL_INT,      0, 0, 30),
        ParamSpec("blend_mode", "blend_mode",       CTRL_BLEND,    "normal"),
    ]

    def apply(self, ctx: EffectContext):
        """
        Ожидает:
          ctx.image — final_img (холст с фоном)
          ctx.mask  — base_mask (не используется, оставлен для симметрии)
          ctx.extra — {
              "char_layer": Image,  # RGBA-слой символа с эффектами
              "paste_x":    int,    # позиция char_layer на холсте
              "paste_y":    int,
              "canvas_w":   int,    # размеры холста (cw, ch)
              "canvas_h":   int,
          }

        Возвращает обновлённый final_img.
        """
        if not self._enabled(ctx):
            return ctx.image

        s = ctx.settings
        char_layer = ctx.extra["char_layer"]
        paste_x = ctx.extra["paste_x"]
        paste_y = ctx.extra["paste_y"]
        cw = ctx.extra["canvas_w"]
        ch = ctx.extra["canvas_h"]

        color = self._get(ctx, "color", "#000000")
        distance = int(self._get(ctx, "distance", 5))
        direction = int(self._get(ctx, "direction", 8))
        blur = int(self._get(ctx, "blur", 0))
        blend_mode = self._get(ctx, "blend_mode", "normal")

        shadow_rgb = get_color_rgb(color)
        shadow_bg = (0, 0, 0, 0) if s.transparent_text else shadow_rgb + (0,)

        sh_mask = char_layer.split()[3]
        sh_layer = Image.new("RGBA", char_layer.size, shadow_rgb + (255,))
        sh_layer.putalpha(sh_mask)
        if blur > 0:
            sh_layer = sh_layer.filter(ImageFilter.GaussianBlur(radius=blur))

        dx, dy = get_shadow_offset(direction, distance)
        sh_final = Image.new("RGBA", (cw, ch), shadow_bg)
        sh_final.paste(sh_layer, (paste_x + dx, paste_y + dy))

        # На прозрачном фоне multiply/overlay дают мусор — принудительно normal.
        if s.transparent_background and blend_mode in ("multiply", "overlay"):
            blend_mode = "normal"

        return blend_layers(ctx.image, sh_final, blend_mode)