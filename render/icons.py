# -*- coding: utf-8 -*-
import os
import numpy as np

from render.composer import (
    CharSpec, compose_full,
    get_icon_mask, default_icon_font_size,
)
from utils import format_filename


def render_icons(icon_paths, settings, progress_callback=None):
    os.makedirs("output", exist_ok=True)
    used_filenames = set()
    total = len(icon_paths)

    for index, icon_path in enumerate(icon_paths, 1):
        icon_name = os.path.splitext(os.path.basename(icon_path))[0]
        spec = CharSpec(icon_path=icon_path, index=index)
        img = compose_full(spec, settings)
        _save_one(img, settings, index, icon_name, used_filenames)
        if progress_callback:
            progress_callback(index, total)

    return total


def _save_one(img, settings, index, name, used_filenames):
    base_name = format_filename(settings.filename_template,
                                 settings.font_size, index, name)
    suffix = "_cutout" if (settings.transparent_text and settings.cutout_mode) else ""
    candidate = base_name + suffix
    final_name = candidate
    n = 2
    while final_name in used_filenames:
        final_name = f"{candidate}_{n}"
        n += 1
    used_filenames.add(final_name)

    out_path = os.path.join("output", f"{final_name}.png")
    img.save(out_path, "PNG")

    if settings.create_bin:
        from render.lvgl import save_lvgl_v8_bin
        bin_dir = os.path.join("output", "bin")
        os.makedirs(bin_dir, exist_ok=True)
        bin_path = os.path.join(bin_dir, f"{final_name}.bin")
        save_lvgl_v8_bin(np.array(img.convert("RGBA")), bin_path,
                         color_depth=32, has_alpha=True, swap_16=False)