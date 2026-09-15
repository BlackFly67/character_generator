# -*- coding: utf-8 -*-
"""
Автоматическая генерация секций сайдбара из ParamSpec эффектов.

Стиль контролов СОВПАДАЕТ с ручными секциями sidebar.py:
  - внешний CTkFrame(parent, fg_color="transparent") + pack(fill="x", pady=5)
  - чекбокс-заголовок с padx=10, pady=2
  - строка параметра: CTkFrame(fg_color="transparent") + pack(padx=10, pady=2)
  - цветная кнопка: 40x24, padx=5 справа
  - entry: width=40, padx=(5,0) справа
  - slider: expand=True, padx=5
  - option/combobox: width=100, padx=5
  - direction grid: label с padx=10, pady=(5,2); grid с padx=10, pady=2
  - file row: label (basename пути или label_key) слева + кнопка справа
  - stops row: canvas 40px + редактор точек
  - seed row: entry + кнопка 🎲 (рандом 0..9999)
"""

import os
import random
import customtkinter as ctk

from effects.core import (
    CTRL_CHECKBOX, CTRL_INT, CTRL_FLOAT, CTRL_COLOR,
    CTRL_BLEND, CTRL_OPTION, CTRL_DIR, CTRL_STOPS, CTRL_FILE,
    CTRL_SEED,
)
from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS
from constants import BLEND_MODES


# Эффекты, для которых UI строится ВРУЧНУЮ в sidebar.py / manual_sidebar.py
MANUAL_EFFECT_IDS = {
    "color_fill",   # UI = ручной text_color, отдельный чекбокс не нужен
}


def build_effect_sections(parent, sidebar, settings, i18n, order=None):
    """
    Строит секции для набора эффектов в parent.

    order — список id эффектов в UI-порядке. Если None — берётся
    PIPELINE + POST_COMPOSE_EFFECTS целиком. Позволяет строить
    авто-секции несколькими вызовами (например, чтобы вставить
    ручную секцию между ними).

    Пропускает эффекты из MANUAL_EFFECT_IDS — для них UI уже
    собран вручную (sidebar.py / manual_sidebar.py).

    POST_COMPOSE_EFFECTS (например, ShadowOuter) доступны здесь же,
    через order=["shadow"], хотя в PIPELINE их нет — они работают
    не с char_layer, а с final_img.
    """
    all_effects = PIPELINE + POST_COMPOSE_EFFECTS
    if order is None:
        cls_list = list(all_effects)
    else:
        by_id = {cls.id: cls for cls in all_effects}
        cls_list = [by_id[eid] for eid in order if eid in by_id]

    result = {}
    for cls in cls_list:
        if cls.id in MANUAL_EFFECT_IDS:
            continue
        eff = cls()
        widgets = _build_one_effect(parent, sidebar, settings, i18n, eff)
        result[eff.id] = widgets
    return result


def build_single_effect_panel(parent, sidebar, settings, i18n, effect_cls):
    """
    Строит панель параметров ОДНОГО эффекта — для Photoshop-style
    режима (ui/effect_rail.py + Sidebar справа показывает только
    активный эффект).

    В отличие от _build_one_effect(), используемого build_effect_sections,
    здесь чекбокс "включено" не прячет/показывает body_frame — body_frame
    всегда виден, т.к. вся панель и так посвящена одному эффекту.
    Чекбокс дублирует переключатель на самой иконке рельса (оба пишут
    в один и тот же settings.<id>_enabled) — после переключения отсюда
    вызывающая сторона (ui/sidebar.py) обязана дёрнуть EffectRail.refresh(),
    иначе рельс не подсветится: см. MainWindow._on_settings_change,
    который вызывается из sidebar._on_change().

    Параметры эффекта строятся ТЕМИ ЖЕ builder-функциями
    (_build_param_row и её ветки) — дублирования логики контролов нет.

    parent должен быть уже очищен вызывающей стороной (Sidebar
    вызывает это после self.winfo_children()... .destroy() в
    _refresh_all_widgets()).

    Возвращает dict с "widgets" (как у _build_one_effect) и отдельно
    "enabled_var" — Sidebar сохраняет её в self._current_enabled_var
    для sync_enabled_checkbox().
    """
    effect = effect_cls()
    enabled_key = f"{effect.id}_enabled"

    widgets = {}
    enabled_var = ctk.BooleanVar(value=bool(getattr(settings, enabled_key, False)))

    def on_toggle():
        setattr(settings, enabled_key, bool(enabled_var.get()))
        sidebar._on_change()

    # Тот же паттерн, что и в _build_one_effect: чекбокс подписан
    # именем самого эффекта (effect.label_key) — это единственный
    # "заголовок" панели, отдельная надпись не нужна и не дублирует
    # название эффекта неверным текстом (см. правку выше — раньше
    # здесь ошибочно всегда подставлялся "enable_shadow"/"transparent_text"
    # независимо от того, какой эффект открыт).
    ctk.CTkCheckBox(
        parent, text=i18n.tr(effect.label_key),
        variable=enabled_var, command=on_toggle,
        checkbox_height=20, checkbox_width=20,
        font=("Arial", 14, "bold"),
    ).pack(anchor="w", padx=10, pady=(10, 8))

    widgets["__enabled_var__"] = enabled_var

    body_frame = ctk.CTkFrame(parent, fg_color="transparent")
    body_frame.pack(fill="x")

    for p in effect.params:
        if p.key == "enabled":
            continue
        _build_param_row(body_frame, sidebar, settings, i18n, effect, p, widgets)

    return {"body_frame": body_frame, "widgets": widgets, "enabled_var": enabled_var}


def _build_one_effect(parent, sidebar, settings, i18n, effect):
    # Секции авто-эффектов — ПРОЗРАЧНЫЕ (без серой подложки), как
    # ручные секции. padx снят — style_section уже даёт 10px по бокам.
    # Оставлен только pady=5 как вертикальный разделитель.
    section = ctk.CTkFrame(parent, fg_color="transparent")
    section.pack(fill="x", pady=5)

    enabled_key = f"{effect.id}_enabled"
    enabled = bool(getattr(settings, enabled_key, False))

    body_frame = ctk.CTkFrame(section, fg_color="transparent")

    widgets = {}

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
        _build_stops_row(parent, sidebar, settings, i18n,
                          full_key, label, param, widgets_out)
    elif param.ctrl == CTRL_SEED:
        _build_seed_row(parent, sidebar, settings,
                         full_key, label, param, widgets_out)
    else:
        print(f"auto_sidebar: unknown ctrl {param.ctrl!r} for {full_key}")


# ============================================================
#  Конкретные строки
# ============================================================

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

    entry = ctk.CTkEntry(row, width=40)
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
                               width=100, command=on_change)
    combo.pack(side="left", padx=5)
    widgets_out[param.key] = combo


def _build_dir_row(parent, sidebar, settings,
                    full_key, label, param, widgets_out):
    symbols = ["↖", "↑", "↗", "←", "●", "→", "↙", "↓", "↘"]
    values = [5, 1, 6, 3, 0, 4, 7, 2, 8]

    ctk.CTkLabel(parent, text=label + ":").pack(anchor="w", padx=10, pady=(5, 2))

    grid = ctk.CTkFrame(parent, fg_color="transparent")
    grid.pack(padx=10, pady=2)

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


def _build_stops_row(parent, sidebar, settings, i18n,
                      full_key, label, param, widgets_out):
    """
    Редактор цветовых точек градиента.
    Читает/пишет список точек в getattr(settings, full_key) —
    для GradientFill это settings.gradient_stops.

    Взаимодействие:
      - клик по свободному месту — добавить точку
      - клик по существующей — выделить
      - драг — переместить выделенную
      - дабл-клик — сменить цвет
      - правый клик — удалить (если точек > 2)
    """
    import tkinter as tk
    from PIL import Image, ImageTk
    from utils import create_checkerboard_background
    from effects.gradient import sample_gradient_color

    ctk.CTkLabel(parent, text=label + ":",
                 font=("Arial", 11)).pack(anchor="w", padx=10, pady=(5, 0))

    stops_canvas = tk.Canvas(
        parent, height=40, highlightthickness=1,
        highlightbackground="#555555", bg="#2b2b2b",
    )
    stops_canvas.pack(fill="x", padx=10, pady=(2, 8))

    state = {"selected_idx": None, "photo": None}

    def redraw_stops():
        canvas = stops_canvas
        canvas.delete("all")
        w = max(canvas.winfo_width(), 10)
        h = max(canvas.winfo_height(), 30)
        ramp_h = max(1, int(h * 0.6))

        stops = getattr(settings, full_key, None)
        if not stops:
            stops = [{"pos": 0.0, "color": "#ff0000"},
                     {"pos": 1.0, "color": "#0000ff"}]

        sorted_stops = sorted(stops, key=lambda s: s["pos"])
        ramp_w = max(w, 2)
        ramp_h2 = max(ramp_h, 2)

        row = [sample_gradient_color(sorted_stops, x / max(1, ramp_w - 1))
               for x in range(ramp_w)]
        ramp_rgba = Image.new("RGBA", (ramp_w, ramp_h2))
        ramp_rgba.putdata(row * ramp_h2)
        checker = create_checkerboard_background(ramp_w, ramp_h2, cell_size=6)
        ramp = Image.alpha_composite(checker, ramp_rgba).convert("RGB")

        state["photo"] = ImageTk.PhotoImage(ramp)
        canvas.create_image(0, 0, anchor="nw", image=state["photo"])

        for i, stop in enumerate(stops):
            x = int(stop["pos"] * w)
            color_str = stop["color"]
            if color_str == "transparent" or color_str is None:
                r, g, b, a = 0, 0, 0, 0
            else:
                hex_color = color_str.lstrip('#')
                if len(hex_color) == 6:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    a = 255
                elif len(hex_color) == 8:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    a = int(hex_color[6:8], 16)
                else:
                    r, g, b, a = 255, 255, 255, 255

            fill = "" if a == 0 else "#{:02x}{:02x}{:02x}".format(r, g, b)
            canvas.create_polygon(
                x - 6, h, x + 6, h, x, ramp_h + 2,
                fill=fill, outline="#ffffff", width=2,
                dash=(None if a == 255 else (3, 2)),
            )

    def get_stop_at(x, w):
        stops = getattr(settings, full_key, None)
        if not stops:
            return None
        best_idx, best_dist = None, None
        for i, stop in enumerate(stops):
            dist = abs(stop["pos"] * w - x)
            if best_dist is None or dist < best_dist:
                best_idx, best_dist = i, dist
        return best_idx if best_dist is not None and best_dist <= 10 else None

    def on_click(event):
        w = max(stops_canvas.winfo_width(), 1)
        idx = get_stop_at(event.x, w)
        if idx is not None:
            state["selected_idx"] = idx
        else:
            t = max(0.0, min(1.0, event.x / w))
            stops = getattr(settings, full_key, None)
            if not stops:
                stops = [
                    {"pos": 0.0, "color": "#ff0000"},
                    {"pos": 1.0, "color": "#0000ff"},
                ]
                setattr(settings, full_key, stops)
            sorted_stops = sorted(stops, key=lambda s: s["pos"])
            r, g, b, a = sample_gradient_color(sorted_stops, t)
            color = "#{:02x}{:02x}{:02x}".format(r, g, b)
            if a < 255:
                color += "{:02x}".format(a)
            stops.append({"pos": t, "color": color})
            state["selected_idx"] = len(stops) - 1
            sidebar._on_change()
            redraw_stops()

    def on_drag(event):
        idx = state["selected_idx"]
        if idx is None:
            return
        stops = getattr(settings, full_key, None)
        if not stops:
            return
        w = max(stops_canvas.winfo_width(), 1)
        t = max(0.0, min(1.0, event.x / w))
        if 0 <= idx < len(stops):
            stops[idx]["pos"] = t
            redraw_stops()

    def on_release(event):
        redraw_stops()
        sidebar._on_change()

    def on_double_click(event):
        w = max(stops_canvas.winfo_width(), 1)
        idx = get_stop_at(event.x, w)
        if idx is None:
            return
        stops = getattr(settings, full_key, None)
        if not stops or idx >= len(stops):
            return
        color = stops[idx]["color"]
        from ui.dialogs import ask_color
        new_color = ask_color(sidebar, color, i18n.tr("select_gradient_color"), i18n)
        if new_color:
            stops[idx]["color"] = new_color
            sidebar._on_change()
            redraw_stops()

    def on_right_click(event):
        stops = getattr(settings, full_key, None)
        if not stops or len(stops) <= 2:
            return
        w = max(stops_canvas.winfo_width(), 1)
        idx = get_stop_at(event.x, w)
        if idx is None:
            return
        del stops[idx]
        state["selected_idx"] = None
        sidebar._on_change()
        redraw_stops()

    stops_canvas.bind("<Button-1>", on_click)
    stops_canvas.bind("<B1-Motion>", on_drag)
    stops_canvas.bind("<ButtonRelease-1>", on_release)
    stops_canvas.bind("<Double-Button-1>", on_double_click)
    stops_canvas.bind("<Button-3>", on_right_click)
    stops_canvas.bind("<Configure>", lambda e: redraw_stops())

    widgets_out[param.key] = {
        "canvas": stops_canvas,
        "state": state,
        "redraw": redraw_stops,
    }


def _build_seed_row(parent, sidebar, settings,
                     full_key, label, param, widgets_out):
    """
    Seed: поле ввода (0..9999) + кнопка 🎲 (рандом).

    Значение хранится в settings.<full_key> (для Glitch —
    settings.glitch_seed). Кнопка 🎲 генерирует новое случайное
    значение, обновляет поле и уведомляет sidebar.
    """
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", padx=10, pady=2)
    ctk.CTkLabel(row, text=label + ":").pack(side="left")

    mn = param.min_val if param.min_val is not None else 0
    mx = param.max_val if param.max_val is not None else 9999

    current = getattr(settings, full_key, param.default or 0)
    try:
        current = int(current)
    except (TypeError, ValueError):
        current = mn
    current = max(mn, min(mx, current))

    entry = ctk.CTkEntry(row, width=55)
    entry.insert(0, str(current))
    entry.pack(side="right", padx=(5, 0))

    def clamp(v):
        return max(mn, min(mx, v))

    def on_entry(event=None):
        try:
            raw = entry.get().strip()
            if not raw:
                return
            val = clamp(int(raw))
            setattr(settings, full_key, val)
            sidebar._on_change()
        except ValueError:
            pass

    def on_random():
        val = random.randint(mn, mx)
        setattr(settings, full_key, val)
        entry.delete(0, "end")
        entry.insert(0, str(val))
        sidebar._on_change()

    dice_btn = ctk.CTkButton(row, text="🎲", width=32, height=24,
                              font=("Segoe UI Symbol", 14),
                              command=on_random)
    dice_btn.pack(side="right", padx=(2, 0))

    entry.bind("<KeyRelease>", on_entry)
    widgets_out[param.key] = (entry, dice_btn)