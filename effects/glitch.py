# -*- coding: utf-8 -*-
"""
Глитч (VHS) — хроматическая аберрация + случайное смещение полос.
"""

import numpy as np
from PIL import Image

from effects.core import (
    EffectBase, EffectContext, ParamSpec,
    CTRL_CHECKBOX, CTRL_INT,
)


class Glitch(EffectBase):
    id = "glitch"
    label_key = "glitch"
    stage = "post"
    params = [
        ParamSpec("enabled",         "glitch",                 CTRL_CHECKBOX, False),
        ParamSpec("rgb_shift",       "glitch_rgb_shift",       CTRL_INT, 4, 0, 30),
        ParamSpec("slice_intensity", "glitch_slice_intensity", CTRL_INT, 30, 0, 100),
        ParamSpec("seed",            "glitch_seed",            CTRL_INT, 0),
    ]

    def apply(self, ctx: EffectContext):
        if not self._enabled(ctx):
            return ctx.image
        rgb_shift = int(self._get(ctx, "rgb_shift", 4))
        slice_intensity = int(self._get(ctx, "slice_intensity", 30))
        seed = int(self._get(ctx, "seed", 0))
        index = int(ctx.extra.get("spec_index", 0))
        return apply_glitch_effect(ctx.image, rgb_shift, slice_intensity,
                                    seed=(seed + index) & 0xFFFFFFFF)


# ============================================================
#  Старая функция — копия прежней версии (с теми же правками
#  edge-clamp, что и в вашем старом glitch.py).
# ============================================================

def apply_glitch_effect(image, rgb_shift=4, slice_intensity=30, seed=0):
    """Применяет глитч-эффект (хроматическая аберрация + разбиение на полосы)."""
    if image.mode != "RGBA":
        image = image.convert("RGBA")

    w, h = image.size
    if w <= 0 or h <= 0 or (rgb_shift <= 0 and slice_intensity <= 0):
        return image

    arr = np.array(image)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    # 1. Хроматическая аберрация
    if rgb_shift > 0:
        shift = min(rgb_shift, w)
        r_shifted = np.roll(r, shift, axis=1)
        b_shifted = np.roll(b, -shift, axis=1)
        a_shifted_r = np.roll(a, shift, axis=1)
        a_shifted_b = np.roll(a, -shift, axis=1)

        if shift > 0:
            r_shifted[:, :shift] = r[:, :shift]
            a_shifted_r[:, :shift] = a[:, :shift]
            b_shifted[:, w - shift:] = b[:, w - shift:]
            a_shifted_b[:, w - shift:] = a[:, w - shift:]

        a = np.maximum(np.maximum(a, a_shifted_r), a_shifted_b)
        r, b = r_shifted, b_shifted

    arr = np.dstack([r, g, b, a])

    # 2. Разбиение на полосы
    intensity = max(0.0, min(100.0, slice_intensity)) / 100.0
    if intensity > 0:
        rng = np.random.RandomState(seed)
        max_offset = max(1, int(w * 0.15 * intensity))
        min_band_frac, max_band_frac = 0.02, 0.12
        y_frac = 0.0
        while y_frac < 1.0:
            band_h_frac = rng.uniform(min_band_frac, max_band_frac)
            y = int(round(y_frac * h))
            band_h = max(1, int(round(band_h_frac * h)))
            band_h = min(band_h, h - y)

            if band_h > 0 and rng.random_sample() < (0.15 + 0.5 * intensity):
                offset = rng.randint(-max_offset, max_offset + 1)
                if offset != 0:
                    original_band = arr[y:y + band_h].copy()
                    band = np.roll(original_band, offset, axis=1)
                    if offset > 0:
                        band[:, :offset] = original_band[:, :offset]
                    else:
                        band[:, offset:] = original_band[:, offset:]
                    arr[y:y + band_h] = band
            y_frac += band_h_frac

    return Image.fromarray(arr)