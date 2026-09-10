# -*- coding: utf-8 -*-
import os
import numpy as np

from render.composer import (
    CharSpec, compose_full, compute_batch_geometry,
)
from utils import parse_characters, format_filename


def render_characters(characters, settings, progress_callback=None):
    if settings.icon_mode:
        from render.icons import render_icons
        return render_icons(characters, settings, progress_callback)
    return render_text_characters(characters, settings, progress_callback)


def render_text_characters(characters, settings, progress_callback=None):
    os.makedirs("output", exist_ok=True)
    used_filenames = set()
    generated = []
    total = len(characters)

    # ОБЩИЙ ХОЛСТ ДЛЯ ВСЕГО БАТЧА: считаем один раз по максимальным
    # метрикам всех символов — узкая буква центрируется в слоте
    # широкой, базовая линия общая.
    specs = [CharSpec(text=ch, index=i) for i, ch in enumerate(characters, 1)]
    batch_geom = compute_batch_geometry(specs, settings)

    for spec in specs:
        img = compose_full(spec, settings, geom=batch_geom)
        out_path = _save_one(img, settings, spec.index, spec.text, used_filenames)
        generated.append(out_path)
        if progress_callback:
            progress_callback(spec.index, total)

    return generated


def _save_one(img, settings, index, char, used_filenames):
    base_name = format_filename(settings.filename_template,
                                 settings.font_size, index, char)
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

    return out_path


def render_arc_characters(characters, settings, progress_callback=None):
    old = settings.arc_text_enabled
    settings.arc_text_enabled = True
    try:
        return render_text_characters(characters, settings, progress_callback)
    finally:
        settings.arc_text_enabled = old