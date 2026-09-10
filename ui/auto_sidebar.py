# -*- coding: utf-8 -*-
"""
Автоматическая генерация секций сайдбара из ParamSpec эффектов.

Идея: у каждого эффекта в PIPELINE есть .params — список ParamSpec.
Из него строим виджеты (checkbox / entry+slider / color picker /
blend / option / dir / file). Значения читаем и пишем через settings
по соглашению f"{effect.id}_{param.key}".

Особые случаи (gradient_stops, pattern_image_path, цветовые пикеры
со своим диалогом) оставлены «ручными» — см. sidebar.py.
"""

import os
import customtkinter as ctk

from effects.core import (
    CTRL_CHECKBOX, CTRL_INT, CTRL_FLOAT, CTRL_COLOR,
    CTRL_BLEND, CTRL_OPTION, CTRL_DIR
)
from effects.registry import PIPELINE
from constants import BLEND_MODES


# Эффекты, для которых UI строится ВРУЧНУЮ в sidebar.py
# (gradient_stops, texture picker — это особые контролы).
MANUAL_EFFECT_IDS = {
    "color_fill",   # использует text_color, отдельный UI не нужен
    "gradient",     # редактор точек градиента
    "pattern",      # выбор файла текстуры + специфичный UI
}


def build_effect_sections(parent, sidebar, settings, i18n):
    """
    Проходит по PIPELINE и строит секции для каждого эффекта
    в указанном родителе.

    sidebar — сам Sidebar (для колбэков вроде _on_change).

    Возвращает dict {effect_id: {"section": Frame, "body_frame": Frame,
                                  "widgets": {...}}}
    """
    result = {}
    for cls in PIPELINE:
        if cls.id in MANUAL_EFFECT_IDS:
            continue
        eff = cls()
        widgets = _build_one_effect(parent, sidebar, settings, i18n, eff)
        result[eff.id] = widgets
    return result


def _build_one_effect(parent, sidebar, settings, i18n, effect):
    section = ctk.CTkFrame(parent)
    section.pack(fill="x", padx=10, pady=5)

    enabled_key = f"{effect.id}_enabled"
    enabled = bool(getattr(settings, enabled_key, False))

    has_checkbox = True   # у всех наших эффектов есть *_enabled

    body_frame = ctk.CTkFrame(section, fg_color="transparent")

    widgets = {}

    # --- Чекбокс "включено" ---
    if has_checkbox:
        enabled_var = ctk.BooleanVar(value=enabled)

        def on_toggle():
            new_val = bool(enabled_var.get())
            setattr(settings, enabled_key, new_val)
            if new_val:
                body_frame.pack(fill="x")
            else:
                body_frame.pack_forget()
            sidebar._on_change()

        ctk.CTkCheckBox(
            section,
            text=i18n.tr(effect.label_key),
            variable=enabled_var,
            command=on_toggle,
            checkbox_height=18, checkbox_width=18,
        ).pack(anchor="w", padx=10, pady=2)

        widgets["__enabled_var__"] = enabled_var

        if enabled:
            body_frame.pack(fill="x")
    else:
        body_frame.pack(fill="x")

    # --- Остальные параметры ---
    for p in effect.params:
        if p.key == "enabled":
            continue
        _build_param_row(body_frame, sidebar, settings, i18n, effect, p, widgets)

    return {"section": section, "body_frame": body_frame, "widgets": widgets}


def _build_param_row(parent, sidebar, settings, i18n, effect, param, widgets_out):
    full_key = f"{effect.id}_{param.key}"
    label = i18n.tr(param.label_key)

    if param.ctrl == CTRL_COLOR:
        _build_color_row(parent, sidebar, settings, i18n,
                          full_key, label, param, widgets_out)
    elif param.ctrl in (CTRL_INT, CTRL_FLOAT):
        _build_int_float_row(parent, sidebar, settings,
                              full_key, label, param, widgets_out)
    elif param.ctrl == CTRL_BLEND:
        _build_option_row(parent, sidebar, settings, BLEND_MODES,
                           full_key, label, param, widgets_out)
    elif param.ctrl == CTRL_OPTION:
        _build_option_row(parent, sidebar, settings, param.values or [],
                           full_key, label, param, widgets_out)
    elif param.ctrl == CTRL_DIR:
        _build_dir_row(parent, sidebar, settings,
                        full_key, label, param, widgets_out)
    elif param.ctrl == CTRL_FILE:
        _build_file_row(parent, sidebar, settings, i18n,
                         full_key, label, param, widgets_out)
    elif param.ctrl == CTRL_STOPS:
        # Не поддерживается — оставляем ручным (см. MANUAL_EFFECT_IDS)
        pass
    else:
        print(f"auto_sidebar: unknown ctrl {param.ctrl!r} for {full_key}")


def _build_color_row(parent, sidebar, settings, i18n,
                       full_key, label, param, widgets_out):
    from ui.dialogs import ask_color
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(row, text=label + ":").pack(side="left")

    current = getattr(settings, full_key, param.default or "#ffffff")

    def pick():
        c = getattr(settings, full_key, param.default or "#ffffff")
        color = ask_color(sidebar, c, label, i18n)
        if color:
            setattr(settings, full_key, color)
            btn.configure(fg_color=color)
            sidebar._on_change()

    btn = ctk.CTkButton(row, text="", width=40, height=24, command=pick)
    btn.pack(side="right", padx=5)
    btn.configure(fg_color=current)
    widgets_out[param.key] = btn


def _build_int_float_row(parent, sidebar, settings,
                          full_key, label, param, widgets_out):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(row, text=label + ":").pack(side="left")

    current = getattr(settings, full_key, param.default)

    entry = ctk.CTkEntry(row, width=45)
    entry.insert(0, str(current))
    entry.pack(side="right", padx=(5, 0))

    mn = param.min_val if param.min_val is not None else 0
    mx = param.max_val if param.max_val is not None else 100
    steps = max(1, (mx - mn) // max(1, param.step))

    slider = ctk.CTkSlider(row, from_=mn, to=mx, number_of_steps=steps)
    slider.pack(side="left", padx=5, fill="x", expand=True)
    slider.set(current)

    def clamp(v):
        if param.min_val is not None and v < param.min_val:
            v = param.min_val
        if param.max_val is not None and v > param.max_val:
            v = param.max_val
        return v

    def on_slider(v):
        val = int(v) if param.ctrl == CTRL_INT else float(v)
        val = clamp(val)
        setattr(settings, full_key, val)
        entry.delete(0, "end")
        entry.insert(0, str(val))
        sidebar._on_change()

    def on_entry(event=None):
        try:
            raw = entry.get().strip()
            if not raw:
                return
            val = int(raw) if param.ctrl == CTRL_INT else float(raw)
            val = clamp(val)
            setattr(settings, full_key, val)
            slider.set(val)
            sidebar._on_change()
        except ValueError:
            pass

    slider.configure(command=on_slider)
    entry.bind("<KeyRelease>", on_entry)
    widgets_out[param.key] = (entry, slider)


def _build_option_row(parent, sidebar, settings, values,
                       full_key, label, param, widgets_out):
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(row, text=label + ":").pack(side="left")

    current = getattr(settings, full_key,
                       param.default or (values[0] if values else ""))
    var = ctk.StringVar(value=current)

    def on_change(v):
        setattr(settings, full_key, v)
        sidebar._on_change()

    combo = ctk.CTkOptionMenu(row, values=values, variable=var,
                               width=110, command=on_change)
    combo.pack(side="left", padx=5)
    widgets_out[param.key] = combo


def _build_dir_row(parent, sidebar, settings,
                    full_key, label, param, widgets_out):
    symbols = ["↖", "↑", "↗", "←", "●", "→", "↙", "↓", "↘"]
    values = [5, 1, 6, 3, 0, 4, 7, 2, 8]

    wrap = ctk.CTkFrame(parent, fg_color="transparent")
    wrap.pack(fill="x", padx=10, pady=(5, 2))
    ctk.CTkLabel(wrap, text=label + ":", anchor="w").pack(anchor="w")

    grid = ctk.CTkFrame(wrap, fg_color="transparent")
    grid.pack(pady=2)

    current = getattr(settings, full_key, param.default or 8)
    var = ctk.IntVar(value=int(current))

    def on_pick(v):
        setattr(settings, full_key, int(v))
        sidebar._on_change()

    for i in range(3):
        for j in range(3):
            idx = i * 3 + j
            ctk.CTkRadioButton(
                grid, text=symbols[idx],
                variable=var, value=values[idx],
                command=lambda v=values[idx]: on_pick(v),
                width=24, radiobutton_width=16, radiobutton_height=16,
            ).grid(row=i, column=j, padx=4, pady=2)

    widgets_out[param.key] = var


def _build_file_row(parent, sidebar, settings, i18n,
                     full_key, label, param, widgets_out):
    from tkinter import filedialog
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=10, pady=2)

    current = getattr(settings, full_key, param.default or "")
    text = os.path.basename(current) if current else label

    lbl = ctk.CTkLabel(row, text=text, font=("Arial", 10))
    lbl.pack(side="left")

    def pick():
        path = filedialog.askopenfilename(
            title=i18n.tr("choose_texture"),
            filetypes=[("Image files", "*.png *.bmp *.gif *.jpg *.jpeg *.webp"),
                        ("All files", "*.*")],
        )
        if path:
            setattr(settings, full_key, path)
            lbl.configure(text=os.path.basename(path))
            sidebar._on_change()

    btn = ctk.CTkButton(row, text=i18n.tr("choose_texture"),
                         width=100, height=24, command=pick)
    btn.pack(side="right", padx=(5, 0))
    widgets_out[param.key] = (lbl, btn)