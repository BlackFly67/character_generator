# -*- coding: utf-8 -*-
"""
Боковая панель с настройками.

Эффекты из PIPELINE (GlowInner, GlowOuter, OutlineInner, OutlineOuter,
ShadowInner, Emboss, Skew, Perspective, Reflection, Glitch, Halftone)
строятся АВТОМАТИЧЕСКИ из ParamSpec — см. ui/auto_sidebar.py.

Ручными остаются:
  - шапка (reset / presets),
  - Font,
  - Text color + transparent_text + cutout_mode,
  - Gradient (редактор точек — спец-контрол),
  - Pattern (выбор файла текстуры),
  - Rotation,
  - Outer Shadow (не в реестре, работает с paste_x/paste_y),
  - Arc text (меняет способ построения маски, не эффект),
  - Opacity,
  - Background.
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk, ImageFilter, ImageChops
import os
import json
import sys
import math
import numpy as np

from fonts import SYSTEM_FONTS
from constants import *
from ui.widgets import IntSliderRow, ColorPickerButton, DirectionSelector

from effects.gradient import sample_gradient_color
from utils import create_checkerboard_background

from ui.auto_sidebar import build_effect_sections

# Направления для теней (используются в ручной секции Outer Shadow)
direction_symbols = ["↖", "↑", "↗", "←", "●", "→", "↙", "↓", "↘"]
direction_values = [5, 1, 6, 3, 0, 4, 7, 2, 8]


class Sidebar(ctk.CTkScrollableFrame):
    """Боковая панель с настройками."""

    def __init__(self, parent, settings, i18n):
        super().__init__(parent, width=320, corner_radius=0)
        self.settings = settings
        self.i18n = i18n
        self._on_change_callbacks = []

        # --- Переменные ручных секций ---

        # Шрифт
        self.font_size_entry = None
        self.font_size_slider = None
        self.text_alignment = None
        self.scale_entry = None
        self.scale_slider = None
        self.spacing_entry = None
        self.spacing_slider = None

        # Стиль (цвет текста + флаги)
        self.text_color_button = None
        self.transparent_text_var = ctk.BooleanVar(value=self.settings.transparent_text)
        self.cutout_mode_var = ctk.BooleanVar(value=self.settings.cutout_mode)

        # Градиент
        self.gradient_enabled_var = ctk.BooleanVar(value=self.settings.gradient_enabled)
        self.gradient_type_var = ctk.StringVar(value=self.settings.gradient_type)
        self.gradient_angle_entry = None
        self.gradient_angle_slider = None
        self.gradient_stops_canvas = None
        self.gradient_stops_photo = None

        # Паттерн
        self.pattern_enabled_var = ctk.BooleanVar(value=self.settings.pattern_enabled)
        self.pattern_texture_label = None
        self.pattern_scale_entry = None
        self.pattern_scale_slider = None
        self.pattern_offset_x_entry = None
        self.pattern_offset_y_entry = None
        self.pattern_angle_entry = None
        self.pattern_angle_slider = None
        self.pattern_blend_mode_var = ctk.StringVar(value=self.settings.pattern_blend_mode)

        # Тень внешняя (ручная — не в PIPELINE)
        self.shadow_var = ctk.BooleanVar(value=self.settings.shadow_enabled)
        self.shadow_color_button = None
        self.shadow_distance_entry = None
        self.shadow_blur_entry = None
        self.shadow_blend_mode_var = ctk.StringVar(value=self.settings.shadow_blend_mode)
        self.shadow_direction_var = ctk.IntVar(value=self.settings.shadow_direction)

        # Поворот (ручная — не в PIPELINE)
        self.rotation_entry = None
        self.rotation_slider = None

        # Текст по дуге (ручная — не эффект, а способ маски)
        self.arc_text_enabled_var = ctk.BooleanVar(value=self.settings.arc_text_enabled)
        self.arc_radius_entry = None
        self.arc_radius_slider = None
        self.arc_start_angle_entry = None
        self.arc_start_angle_slider = None
        self.arc_clockwise_var = ctk.BooleanVar(value=self.settings.arc_clockwise)
        self.arc_flip_var = ctk.BooleanVar(value=self.settings.arc_flip)

        # Прозрачность (глобальная, не эффект)
        self.opacity_entry = None
        self.opacity_slider = None

        # Фон
        self.transparent_background_var = ctk.BooleanVar(value=self.settings.transparent_background)
        self.background_color_button = None

        # Заголовок
        self.settings_label = None
        self.style_presets_button = None

        # Секции авто-эффектов
        self.effect_sections = {}

        # --- СОЗДАЁМ ИНТЕРФЕЙС ---
        self._create_sidebar()

    def _on_change(self):
        """
        НЕ сохраняем config.json на каждое движение слайдера — сохранение
        делает MainWindow._on_generate (по кнопке) и _on_close (при
        выходе). Обновляем только превью через колбэки.
        """
        for callback in self._on_change_callbacks:
            callback()

    def add_change_callback(self, callback):
        self._on_change_callbacks.append(callback)

    def _refresh_all_widgets(self):
        """Обновляет все виджеты после сброса."""
        for widget in self.winfo_children():
            widget.destroy()
        self._create_sidebar()

    def _reset_settings(self):
        if messagebox.askyesno(
            self.i18n.tr("warning"),
            self.i18n.tr("reset_warning") + "\n\n" + self.i18n.tr("reset_confirm")
        ):
            self.settings.reset()
            self._refresh_all_widgets()
            self._on_change()
            messagebox.showinfo(self.i18n.tr("done"), self.i18n.tr("settings_reset"))

    def _open_presets(self):
        from ui.dialogs import StylePresetsDialog
        dialog = StylePresetsDialog(self, self.settings, self.i18n)
        dialog.wait_window()
        self._refresh_all_widgets()
        self._on_change()

    # ============================================================
    #  Gradient stops (ручной редактор)
    # ============================================================

    def _redraw_gradient_stops(self):
        if not hasattr(self, 'gradient_stops_canvas') or self.gradient_stops_canvas is None:
            return

        canvas = self.gradient_stops_canvas
        canvas.delete("all")
        w = max(canvas.winfo_width(), 10)
        h = max(canvas.winfo_height(), 30)
        ramp_h = max(1, int(h * 0.6))

        stops = self.settings.gradient_stops
        if not stops:
            stops = [{"pos": 0.0, "color": "#ff0000"}, {"pos": 1.0, "color": "#0000ff"}]

        sorted_stops = sorted(stops, key=lambda s: s["pos"])
        ramp_w = max(w, 2)
        ramp_h2 = max(ramp_h, 2)

        row = [sample_gradient_color(sorted_stops, x / max(1, ramp_w - 1)) for x in range(ramp_w)]
        ramp_rgba = Image.new("RGBA", (ramp_w, ramp_h2))
        ramp_rgba.putdata(row * ramp_h2)
        checker = create_checkerboard_background(ramp_w, ramp_h2, cell_size=6)
        ramp = Image.alpha_composite(checker, ramp_rgba).convert("RGB")

        self.gradient_stops_photo = ImageTk.PhotoImage(ramp)
        canvas.create_image(0, 0, anchor="nw", image=self.gradient_stops_photo)

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
                dash=(None if a == 255 else (3, 2))
            )

    def _get_stop_at(self, x, w):
        stops = self.settings.gradient_stops
        if not stops:
            return None
        best_idx, best_dist = None, None
        for i, stop in enumerate(stops):
            dist = abs(stop["pos"] * w - x)
            if best_dist is None or dist < best_dist:
                best_idx, best_dist = i, dist
        return best_idx if best_dist is not None and best_dist <= 10 else None

    def _on_gradient_stops_click(self, event):
        w = max(self.gradient_stops_canvas.winfo_width(), 1)
        idx = self._get_stop_at(event.x, w)
        if idx is not None:
            self._gradient_selected_idx = idx
        else:
            t = max(0.0, min(1.0, event.x / w))
            if not self.settings.gradient_stops:
                self.settings.gradient_stops = [
                    {"pos": 0.0, "color": "#ff0000"},
                    {"pos": 1.0, "color": "#0000ff"},
                ]
            stops = self.settings.gradient_stops
            sorted_stops = sorted(stops, key=lambda s: s["pos"])
            r, g, b, a = sample_gradient_color(sorted_stops, t)
            color = "#{:02x}{:02x}{:02x}".format(r, g, b)
            if a < 255:
                color += "{:02x}".format(a)
            stops.append({"pos": t, "color": color})
            self._gradient_selected_idx = len(stops) - 1
            self._on_change()
            self._redraw_gradient_stops()

    def _on_gradient_stops_drag(self, event):
        if not hasattr(self, '_gradient_selected_idx') or self._gradient_selected_idx is None:
            return
        stops = self.settings.gradient_stops
        if not stops:
            return
        w = max(self.gradient_stops_canvas.winfo_width(), 1)
        t = max(0.0, min(1.0, event.x / w))
        if 0 <= self._gradient_selected_idx < len(stops):
            stops[self._gradient_selected_idx]["pos"] = t
            self._redraw_gradient_stops()

    def _on_gradient_stops_release(self, event):
        self._redraw_gradient_stops()
        self._on_change()

    def _on_gradient_stops_double_click(self, event):
        w = max(self.gradient_stops_canvas.winfo_width(), 1)
        idx = self._get_stop_at(event.x, w)
        if idx is None:
            return
        stops = self.settings.gradient_stops
        if not stops or idx >= len(stops):
            return
        color = stops[idx]["color"]
        from ui.dialogs import ask_color
        new_color = ask_color(self, color, self.i18n.tr("select_gradient_color"), self.i18n)
        if new_color:
            stops[idx]["color"] = new_color
            self._on_change()
            self._redraw_gradient_stops()

    def _on_gradient_stops_right_click(self, event):
        stops = self.settings.gradient_stops
        if not stops or len(stops) <= 2:
            return
        w = max(self.gradient_stops_canvas.winfo_width(), 1)
        idx = self._get_stop_at(event.x, w)
        if idx is None:
            return
        del stops[idx]
        self._gradient_selected_idx = None
        self._on_change()
        self._redraw_gradient_stops()

    # ============================================================
    #  Сборка сайдбара
    # ============================================================

    def _create_sidebar(self):
        """Создаёт весь sidebar."""

        # ============================================================
        # 1. ЗАГОЛОВОК С КНОПКОЙ СБРОСА
        # ============================================================
        settings_header = ctk.CTkFrame(self, fg_color="transparent")
        settings_header.pack(fill="x", padx=10, pady=(15, 10))

        self.settings_label = ctk.CTkLabel(settings_header, text=self.i18n.tr("settings"),
                                            font=("Arial", 18, "bold"))
        self.settings_label.pack(side="left")

        reset_button = ctk.CTkButton(
            settings_header, text="↺", width=28, height=28,
            font=("Segoe UI Symbol", 16, "bold"),
            fg_color="#8B0000", hover_color="#5C0000",
            command=self._reset_settings,
        )
        reset_button.pack(side="right")

        self.style_presets_button = ctk.CTkButton(
            settings_header, text="🎨 " + self.i18n.tr("style_presets"),
            command=self._open_presets,
        )
        self.style_presets_button.pack(side="right", padx=5)

        # ============================================================
        # 2. СЕКЦИЯ: ШРИФТ
        # ============================================================
        font_section = ctk.CTkFrame(self)
        font_section.pack(fill="x", padx=10, pady=5)

        font_choice_frame = ctk.CTkFrame(font_section, fg_color="transparent")
        font_choice_frame.pack(fill="x")

        self.font_label = ctk.CTkLabel(
            font_choice_frame,
            text=f"{self.i18n.tr('font')}: "
                 f"{os.path.basename(self.settings.font_path) if self.settings.font_path else self.i18n.tr('no_font')}",
            font=("Arial", 12, "bold"),
        )
        self.font_label.pack(anchor="w", padx=10, pady=5)

        system_font_button = ctk.CTkButton(
            font_choice_frame, text=self.i18n.tr("system_font"),
            command=self._open_system_font_picker,
        )
        system_font_button.pack(fill="x", padx=10, pady=5)

        font_button = ctk.CTkButton(
            font_choice_frame, text=self.i18n.tr("choose_font"),
            command=self._select_font,
        )
        font_button.pack(fill="x", padx=10, pady=5)

        font_props_frame = ctk.CTkFrame(font_section, fg_color="transparent")
        font_props_frame.pack(fill="x", padx=10, pady=5)

        size_row = ctk.CTkFrame(font_props_frame, fg_color="transparent")
        size_row.pack(fill="x")

        size_label = ctk.CTkLabel(size_row, text=self.i18n.tr("size") + ":")
        size_label.pack(side="left")

        self.font_size_entry = ctk.CTkEntry(size_row, width=55)
        self.font_size_entry.insert(0, str(self.settings.font_size))
        self.font_size_entry.pack(side="left", padx=5)
        self.font_size_entry.bind("<KeyRelease>", self._on_font_size_change)

        reset_icon_size_button = ctk.CTkButton(
            size_row, text="⟲", width=28, height=28,
            font=("Segoe UI Symbol", 14),
            command=self._reset_icon_size_to_native,
            state="disabled",
        )
        reset_icon_size_button.pack(side="right", padx=(5, 0))

        self.font_size_slider = ctk.CTkSlider(
            size_row, from_=FONT_SIZE_MIN, to=FONT_SIZE_MAX,
            number_of_steps=FONT_SIZE_MAX - FONT_SIZE_MIN,
            command=self._on_font_size_slider,
        )
        self.font_size_slider.set(self.settings.font_size)
        self.font_size_slider.pack(side="left", padx=5, fill="x", expand=True)

        alignment_frame = ctk.CTkFrame(font_props_frame, fg_color="transparent")
        alignment_frame.pack(fill="x", pady=(5, 0))

        alignment_label = ctk.CTkLabel(alignment_frame, text=self.i18n.tr("align") + ":")
        alignment_label.pack(side="left")

        self.text_alignment = ctk.StringVar(value=self.settings.text_alignment)
        alignment_menu = ctk.CTkOptionMenu(
            alignment_frame, values=["left", "center", "right"],
            variable=self.text_alignment, width=90,
            command=self._on_alignment_change,
        )
        alignment_menu.pack(side="left", padx=5)

        scale_section = ctk.CTkFrame(font_section, fg_color="transparent")
        scale_section.pack(fill="x", padx=10, pady=5)

        scale_label = ctk.CTkLabel(scale_section, text=self.i18n.tr("text_scale") + " (%):",
                                    font=("Arial", 11))
        scale_label.pack(side="left")

        self.scale_entry = ctk.CTkEntry(scale_section, width=40)
        scale_init = int(round((self.settings.text_scale_x - 1.0) * 100))
        self.scale_entry.insert(0, str(scale_init))
        self.scale_entry.pack(side="right", padx=(5, 0))
        self.scale_entry.bind("<KeyRelease>", self._on_scale_change)

        self.scale_slider = ctk.CTkSlider(scale_section, from_=-50, to=50, number_of_steps=100)
        self.scale_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.scale_slider.set(scale_init)
        self.scale_slider.configure(command=self._on_scale_slider)

        spacing_section = ctk.CTkFrame(font_section, fg_color="transparent")
        spacing_section.pack(fill="x", padx=10, pady=5)

        spacing_label = ctk.CTkLabel(spacing_section, text=self.i18n.tr("letter_spacing") + " (px):",
                                      font=("Arial", 11))
        spacing_label.pack(side="left")

        self.spacing_entry = ctk.CTkEntry(spacing_section, width=40)
        self.spacing_entry.insert(0, str(self.settings.letter_spacing))
        self.spacing_entry.pack(side="right", padx=(5, 0))
        self.spacing_entry.bind("<KeyRelease>", self._on_spacing_change)

        self.spacing_slider = ctk.CTkSlider(spacing_section, from_=-20, to=20, number_of_steps=40)
        self.spacing_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.spacing_slider.set(self.settings.letter_spacing)
        self.spacing_slider.configure(command=self._on_spacing_slider)

        # ============================================================
        # 3. СЕКЦИЯ: СТИЛЬ СИМВОЛОВ (ручная — цвет/флаги + gradient + pattern)
        # ============================================================
        style_section = ctk.CTkFrame(self)
        style_section.pack(fill="x", padx=10, pady=5)

        text_style_label = ctk.CTkLabel(style_section, text=self.i18n.tr("text_style"),
                                         font=("Arial", 12, "bold"))
        text_style_label.pack(anchor="w", padx=10, pady=5)

        # --- Цвет текста ---
        color_flow1 = ctk.CTkFrame(style_section, fg_color="transparent")
        color_flow1.pack(fill="x", padx=10, pady=2)

        text_color_label = ctk.CTkLabel(color_flow1, text=self.i18n.tr("text_color") + ":")
        text_color_label.pack(side="left")

        self.text_color_button = ctk.CTkButton(color_flow1, text="",
                                                 command=self._select_text_color,
                                                 width=40, height=24)
        self.text_color_button.pack(side="right", padx=5)
        self.text_color_button.configure(fg_color=self.settings.text_color)

        transparent_text_check = ctk.CTkCheckBox(
            style_section, text=self.i18n.tr("transparent"),
            variable=self.transparent_text_var,
            command=self._toggle_transparent_text,
            checkbox_height=18, checkbox_width=18,
        )
        transparent_text_check.pack(anchor="w", padx=10, pady=2)

        cutout_check = ctk.CTkCheckBox(
            style_section, text=self.i18n.tr("cutout"),
            variable=self.cutout_mode_var,
            command=self._toggle_cutout_mode,
            checkbox_height=18, checkbox_width=18,
        )
        cutout_check.pack(anchor="w", padx=10, pady=2)

        # --- ГРАДИЕНТ (ручной: редактор точек) ---
        # FIX: приведено к auto-стилю — корневой CTkFrame без fg_color,
        # чекбокс с padx=10. Так эта секция визуально совпадает с
        # auto-секциями (Outline Inner, Glow Outer и т.п.).
        gradient_section = ctk.CTkFrame(style_section)
        gradient_section.pack(fill="x", padx=10, pady=5)

        gradient_check = ctk.CTkCheckBox(
            gradient_section, text=self.i18n.tr("gradient_fill"),
            variable=self.gradient_enabled_var,
            command=self._toggle_gradient,
            checkbox_height=18, checkbox_width=18,
        )
        gradient_check.pack(anchor="w", padx=10, pady=2)

        gradient_frame = ctk.CTkFrame(gradient_section, fg_color="transparent")
        if not self.settings.gradient_enabled:
            gradient_frame.pack_forget()
        else:
            gradient_frame.pack(fill="x")
        self.gradient_frame = gradient_frame

        gradient_type_flow = ctk.CTkFrame(gradient_frame, fg_color="transparent")
        gradient_type_flow.pack(fill="x", padx=10, pady=2)

        gradient_type_label = ctk.CTkLabel(gradient_type_flow, text=self.i18n.tr("gradient_type") + ":")
        gradient_type_label.pack(side="left")

        gradient_type_combo = ctk.CTkOptionMenu(
            gradient_type_flow, values=GRADIENT_TYPES,
            variable=self.gradient_type_var, width=110,
            command=self._on_gradient_type_change,
        )
        gradient_type_combo.pack(side="left", padx=5)

        gradient_angle_flow = ctk.CTkFrame(gradient_frame, fg_color="transparent")
        gradient_angle_flow.pack(fill="x", padx=10, pady=2)

        gradient_angle_label = ctk.CTkLabel(gradient_angle_flow, text=self.i18n.tr("gradient_angle") + " (°):")
        gradient_angle_label.pack(side="left")

        self.gradient_angle_entry = ctk.CTkEntry(gradient_angle_flow, width=40)
        self.gradient_angle_entry.insert(0, str(self.settings.gradient_angle))
        self.gradient_angle_entry.pack(side="right", padx=(5, 0))
        self.gradient_angle_entry.bind("<KeyRelease>", self._on_gradient_angle_change)

        self.gradient_angle_slider = ctk.CTkSlider(gradient_angle_flow, from_=0, to=360, number_of_steps=360)
        self.gradient_angle_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.gradient_angle_slider.set(self.settings.gradient_angle)
        self.gradient_angle_slider.configure(command=self._on_gradient_angle_slider)

        gradient_stops_label = ctk.CTkLabel(gradient_frame, text=self.i18n.tr("gradient_stops") + ":",
                                             font=("Arial", 11))
        gradient_stops_label.pack(anchor="w", padx=10, pady=(5, 0))

        self.gradient_stops_canvas = tk.Canvas(
            gradient_frame, height=40, highlightthickness=1,
            highlightbackground="#555555", bg="#2b2b2b",
        )
        self.gradient_stops_canvas.pack(fill="x", padx=10, pady=(2, 8))

        self.gradient_stops_canvas.bind("<Button-1>", self._on_gradient_stops_click)
        self.gradient_stops_canvas.bind("<B1-Motion>", self._on_gradient_stops_drag)
        self.gradient_stops_canvas.bind("<ButtonRelease-1>", self._on_gradient_stops_release)
        self.gradient_stops_canvas.bind("<Double-Button-1>", self._on_gradient_stops_double_click)
        self.gradient_stops_canvas.bind("<Button-3>", self._on_gradient_stops_right_click)
        self.gradient_stops_canvas.bind("<Configure>", lambda e: self._redraw_gradient_stops())

        # --- ПАТТЕРН (ручной: выбор файла) ---
        # FIX: приведено к auto-стилю — корневой CTkFrame без fg_color,
        # чекбокс с padx=10.
        pattern_section = ctk.CTkFrame(style_section)
        pattern_section.pack(fill="x", padx=10, pady=5)

        pattern_check = ctk.CTkCheckBox(
            pattern_section, text=self.i18n.tr("pattern_fill"),
            variable=self.pattern_enabled_var,
            command=self._toggle_pattern,
            checkbox_height=18, checkbox_width=18,
        )
        pattern_check.pack(anchor="w", padx=10, pady=2)

        pattern_frame = ctk.CTkFrame(pattern_section, fg_color="transparent")
        if not self.settings.pattern_enabled:
            pattern_frame.pack_forget()
        else:
            pattern_frame.pack(fill="x")
        self.pattern_frame = pattern_frame

        pattern_texture_row = ctk.CTkFrame(pattern_frame, fg_color="transparent")
        pattern_texture_row.pack(fill="x", padx=10, pady=2)

        pattern_texture_text = self.i18n.tr("no_texture")
        if self.settings.pattern_image_path:
            pattern_texture_text = os.path.basename(self.settings.pattern_image_path)
        self.pattern_texture_label = ctk.CTkLabel(pattern_texture_row, text=pattern_texture_text,
                                                    font=("Arial", 10))
        self.pattern_texture_label.pack(side="left")

        pattern_texture_button = ctk.CTkButton(
            pattern_texture_row, text=self.i18n.tr("choose_texture"),
            width=100, height=24, command=self._select_pattern_texture,
        )
        pattern_texture_button.pack(side="right", padx=(5, 0))

        pattern_scale_flow = ctk.CTkFrame(pattern_frame, fg_color="transparent")
        pattern_scale_flow.pack(fill="x", padx=10, pady=2)

        pattern_scale_label = ctk.CTkLabel(pattern_scale_flow, text=self.i18n.tr("pattern_scale") + " (%):")
        pattern_scale_label.pack(side="left")

        self.pattern_scale_entry = ctk.CTkEntry(pattern_scale_flow, width=45)
        self.pattern_scale_entry.insert(0, str(self.settings.pattern_scale))
        self.pattern_scale_entry.pack(side="right", padx=(5, 0))
        self.pattern_scale_entry.bind("<KeyRelease>", self._on_pattern_scale_change)

        self.pattern_scale_slider = ctk.CTkSlider(pattern_scale_flow, from_=5, to=500, number_of_steps=495)
        self.pattern_scale_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.pattern_scale_slider.set(self.settings.pattern_scale)
        self.pattern_scale_slider.configure(command=self._on_pattern_scale_slider)

        pattern_offset_flow = ctk.CTkFrame(pattern_frame, fg_color="transparent")
        pattern_offset_flow.pack(fill="x", padx=10, pady=2)

        pattern_offset_x_label = ctk.CTkLabel(pattern_offset_flow, text=self.i18n.tr("pattern_offset_x") + ":")
        pattern_offset_x_label.pack(side="left")

        self.pattern_offset_x_entry = ctk.CTkEntry(pattern_offset_flow, width=40)
        self.pattern_offset_x_entry.insert(0, str(self.settings.pattern_offset_x))
        self.pattern_offset_x_entry.pack(side="left", padx=5)
        self.pattern_offset_x_entry.bind("<KeyRelease>", self._on_pattern_offset_x_change)

        pattern_offset_y_label = ctk.CTkLabel(pattern_offset_flow, text=self.i18n.tr("pattern_offset_y") + ":")
        pattern_offset_y_label.pack(side="left", padx=(10, 5))

        self.pattern_offset_y_entry = ctk.CTkEntry(pattern_offset_flow, width=40)
        self.pattern_offset_y_entry.insert(0, str(self.settings.pattern_offset_y))
        self.pattern_offset_y_entry.pack(side="left")
        self.pattern_offset_y_entry.bind("<KeyRelease>", self._on_pattern_offset_y_change)

        pattern_angle_flow = ctk.CTkFrame(pattern_frame, fg_color="transparent")
        pattern_angle_flow.pack(fill="x", padx=10, pady=2)

        pattern_angle_label = ctk.CTkLabel(pattern_angle_flow, text=self.i18n.tr("pattern_angle") + " (°):")
        pattern_angle_label.pack(side="left")

        self.pattern_angle_entry = ctk.CTkEntry(pattern_angle_flow, width=40)
        self.pattern_angle_entry.insert(0, str(self.settings.pattern_angle))
        self.pattern_angle_entry.pack(side="right", padx=(5, 0))
        self.pattern_angle_entry.bind("<KeyRelease>", self._on_pattern_angle_change)

        self.pattern_angle_slider = ctk.CTkSlider(pattern_angle_flow, from_=0, to=360, number_of_steps=360)
        self.pattern_angle_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.pattern_angle_slider.set(self.settings.pattern_angle)
        self.pattern_angle_slider.configure(command=self._on_pattern_angle_slider)

        pattern_blend_flow = ctk.CTkFrame(pattern_frame, fg_color="transparent")
        pattern_blend_flow.pack(fill="x", padx=10, pady=(2, 8))

        pattern_blend_label = ctk.CTkLabel(pattern_blend_flow, text=self.i18n.tr("blend_mode") + ":")
        pattern_blend_label.pack(side="left")

        pattern_blend_combo = ctk.CTkOptionMenu(
            pattern_blend_flow, values=BLEND_MODES,
            variable=self.pattern_blend_mode_var, width=100,
            command=self._on_pattern_blend_change,
        )
        pattern_blend_combo.pack(side="left", padx=5)

        # ============================================================
        # 4. ЭФФЕКТЫ ИЗ PIPELINE (АВТО-ГЕНЕРАЦИЯ)
        # ============================================================
        self.effect_sections = build_effect_sections(
            style_section, self, self.settings, self.i18n
        )

        # ============================================================
        # 5. СЕКЦИЯ: ТЕНЬ (внешняя, ручная — не в PIPELINE)
        # ============================================================
        shadow_section = ctk.CTkFrame(self)
        shadow_section.pack(fill="x", padx=10, pady=5)

        shadow_check = ctk.CTkCheckBox(
            shadow_section, text=self.i18n.tr("shadow"),
            variable=self.shadow_var, command=self._toggle_shadow,
            checkbox_height=18, checkbox_width=18,
        )
        shadow_check.pack(anchor="w", padx=10, pady=2)

        shadow_frame = ctk.CTkFrame(shadow_section, fg_color="transparent")
        if not self.settings.shadow_enabled:
            shadow_frame.pack_forget()
        else:
            shadow_frame.pack(fill="x")
        self.shadow_frame = shadow_frame

        shadow_color_flow = ctk.CTkFrame(shadow_frame, fg_color="transparent")
        shadow_color_flow.pack(fill="x", padx=10, pady=2)

        shadow_color_label = ctk.CTkLabel(shadow_color_flow, text=self.i18n.tr("shadow_color") + ":")
        shadow_color_label.pack(side="left")

        self.shadow_color_button = ctk.CTkButton(
            shadow_color_flow, text="", command=self._select_shadow_color,
            width=40, height=24,
        )
        self.shadow_color_button.pack(side="right", padx=5)
        self.shadow_color_button.configure(fg_color=self.settings.shadow_color)

        shadow_prop_flow = ctk.CTkFrame(shadow_frame, fg_color="transparent")
        shadow_prop_flow.pack(fill="x", padx=10, pady=2)

        shadow_distance_label = ctk.CTkLabel(shadow_prop_flow, text=self.i18n.tr("shadow_distance") + ":")
        shadow_distance_label.pack(side="left")

        self.shadow_distance_entry = ctk.CTkEntry(shadow_prop_flow, width=40)
        self.shadow_distance_entry.insert(0, str(self.settings.shadow_distance))
        self.shadow_distance_entry.pack(side="left", padx=5)
        self.shadow_distance_entry.bind("<KeyRelease>", self._on_shadow_distance_change)

        shadow_blur_label = ctk.CTkLabel(shadow_prop_flow, text=self.i18n.tr("shadow_blur") + ":")
        shadow_blur_label.pack(side="left", padx=(10, 5))

        self.shadow_blur_entry = ctk.CTkEntry(shadow_prop_flow, width=40)
        self.shadow_blur_entry.insert(0, str(self.settings.shadow_blur))
        self.shadow_blur_entry.pack(side="left")
        self.shadow_blur_entry.bind("<KeyRelease>", self._on_shadow_blur_change)

        shadow_blend_flow = ctk.CTkFrame(shadow_frame, fg_color="transparent")
        shadow_blend_flow.pack(fill="x", padx=10, pady=2)

        shadow_blend_label = ctk.CTkLabel(shadow_blend_flow, text=self.i18n.tr("blend_mode") + ":")
        shadow_blend_label.pack(side="left")

        shadow_blend_combo = ctk.CTkOptionMenu(
            shadow_blend_flow, values=BLEND_MODES,
            variable=self.shadow_blend_mode_var, width=100,
            command=self._on_shadow_blend_change,
        )
        shadow_blend_combo.pack(side="left", padx=5)

        direction_label = ctk.CTkLabel(shadow_frame, text=self.i18n.tr("shadow_direction") + ":")
        direction_label.pack(anchor="w", padx=10, pady=(5, 2))

        direction_frame = ctk.CTkFrame(shadow_frame, fg_color="transparent")
        direction_frame.pack(pady=2)

        for i in range(3):
            for j in range(3):
                idx = i * 3 + j
                btn = ctk.CTkRadioButton(
                    direction_frame, text=direction_symbols[idx],
                    variable=self.shadow_direction_var,
                    value=direction_values[idx],
                    command=lambda: self._on_shadow_direction_change(self.shadow_direction_var.get()),
                    width=24, radiobutton_width=16, radiobutton_height=16,
                )
                btn.grid(row=i, column=j, padx=4, pady=2)

        direction_note = ctk.CTkLabel(
            shadow_frame, text=self.i18n.tr("center_shadow"),
            font=("Arial", 10), text_color="gray",
        )
        direction_note.pack(anchor="w", padx=10, pady=(0, 5))

        # ============================================================
        # 6. СЕКЦИЯ: ПОВОРОТ (ручная — не в PIPELINE)
        # ============================================================
        rotation_section = ctk.CTkFrame(self)
        rotation_section.pack(fill="x", padx=10, pady=5)

        rotation_entry_frame = ctk.CTkFrame(rotation_section, fg_color="transparent")
        rotation_entry_frame.pack(fill="x", pady=2)

        rotation_label = ctk.CTkLabel(rotation_entry_frame, text=self.i18n.tr("rotation") + " (°):",
                                       font=("Arial", 11))
        rotation_label.pack(side="left", padx=10, pady=5)

        self.rotation_entry = ctk.CTkEntry(rotation_entry_frame, width=40)
        self.rotation_entry.insert(0, str(self.settings.rotation_angle))
        self.rotation_entry.pack(side="right", padx=10, pady=5)
        self.rotation_entry.bind("<KeyRelease>", self._on_rotation_change)

        rotation_slider_frame = ctk.CTkFrame(rotation_section, fg_color="transparent")
        rotation_slider_frame.pack(fill="x", pady=2)

        self.rotation_slider = ctk.CTkSlider(
            rotation_slider_frame, from_=-180, to=180, number_of_steps=360,
            command=self._on_rotation_slider,
        )
        self.rotation_slider.pack(fill="x", padx=10, pady=5)
        self.rotation_slider.set(self.settings.rotation_angle)

        # ============================================================
        # 7. СЕКЦИЯ: ТЕКСТ ПО ДУГЕ (ручная — не эффект)
        # ============================================================
        arc_section = ctk.CTkFrame(self)
        arc_section.pack(fill="x", padx=10, pady=5)

        arc_check = ctk.CTkCheckBox(
            arc_section, text=self.i18n.tr("arc_text"),
            variable=self.arc_text_enabled_var,
            command=self._toggle_arc_text,
            checkbox_height=18, checkbox_width=18,
        )
        arc_check.pack(anchor="w", padx=10, pady=2)

        arc_frame = ctk.CTkFrame(arc_section, fg_color="transparent")
        if not self.settings.arc_text_enabled:
            arc_frame.pack_forget()
        else:
            arc_frame.pack(fill="x")
        self.arc_frame = arc_frame

        arc_radius_flow = ctk.CTkFrame(arc_frame, fg_color="transparent")
        arc_radius_flow.pack(fill="x", padx=10, pady=2)

        arc_radius_label = ctk.CTkLabel(arc_radius_flow, text=self.i18n.tr("arc_radius") + ":")
        arc_radius_label.pack(side="left")

        self.arc_radius_entry = ctk.CTkEntry(arc_radius_flow, width=50)
        self.arc_radius_entry.insert(0, str(self.settings.arc_radius))
        self.arc_radius_entry.pack(side="right", padx=(5, 0))
        self.arc_radius_entry.bind("<KeyRelease>", self._on_arc_radius_change)

        self.arc_radius_slider = ctk.CTkSlider(arc_radius_flow, from_=1, to=2000, number_of_steps=1990)
        self.arc_radius_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.arc_radius_slider.set(self.settings.arc_radius)
        self.arc_radius_slider.configure(command=self._on_arc_radius_slider)

        arc_angle_flow = ctk.CTkFrame(arc_frame, fg_color="transparent")
        arc_angle_flow.pack(fill="x", padx=10, pady=2)

        arc_start_angle_label = ctk.CTkLabel(arc_angle_flow, text=self.i18n.tr("arc_start_angle") + " (°):")
        arc_start_angle_label.pack(side="left")

        self.arc_start_angle_entry = ctk.CTkEntry(arc_angle_flow, width=50)
        self.arc_start_angle_entry.insert(0, str(self.settings.arc_start_angle))
        self.arc_start_angle_entry.pack(side="right", padx=(5, 0))
        self.arc_start_angle_entry.bind("<KeyRelease>", self._on_arc_angle_change)

        self.arc_start_angle_slider = ctk.CTkSlider(arc_angle_flow, from_=0, to=360, number_of_steps=360)
        self.arc_start_angle_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.arc_start_angle_slider.set(self.settings.arc_start_angle)
        self.arc_start_angle_slider.configure(command=self._on_arc_angle_slider)

        arc_options_flow = ctk.CTkFrame(arc_frame, fg_color="transparent")
        arc_options_flow.pack(fill="x", padx=10, pady=(2, 8))

        arc_clockwise_check = ctk.CTkCheckBox(
            arc_options_flow, text=self.i18n.tr("arc_clockwise"),
            variable=self.arc_clockwise_var,
            command=self._on_arc_clockwise_change,
            checkbox_height=18, checkbox_width=18,
        )
        arc_clockwise_check.pack(side="left", padx=(0, 15))

        arc_flip_check = ctk.CTkCheckBox(
            arc_options_flow, text=self.i18n.tr("arc_flip"),
            variable=self.arc_flip_var,
            command=self._on_arc_flip_change,
            checkbox_height=18, checkbox_width=18,
        )
        arc_flip_check.pack(side="left")

        # ============================================================
        # 8. СЕКЦИЯ: ПРОЗРАЧНОСТЬ (глобальная, не эффект)
        # ============================================================
        opacity_section = ctk.CTkFrame(self)
        opacity_section.pack(fill="x", padx=10, pady=5)

        opacity_entry_frame = ctk.CTkFrame(opacity_section, fg_color="transparent")
        opacity_entry_frame.pack(fill="x", pady=2)

        opacity_label = ctk.CTkLabel(opacity_entry_frame, text=self.i18n.tr("opacity") + " (%):",
                                      font=("Arial", 11))
        opacity_label.pack(side="left", padx=10, pady=5)

        self.opacity_entry = ctk.CTkEntry(opacity_entry_frame, width=50)
        self.opacity_entry.insert(0, str(int(round(self.settings.text_opacity * 100))))
        self.opacity_entry.pack(side="right", padx=10, pady=5)
        self.opacity_entry.bind("<KeyRelease>", self._on_opacity_change)

        opacity_slider_frame = ctk.CTkFrame(opacity_section, fg_color="transparent")
        opacity_slider_frame.pack(fill="x", pady=2)

        self.opacity_slider = ctk.CTkSlider(opacity_slider_frame, from_=0, to=100, number_of_steps=100)
        self.opacity_slider.pack(fill="x", padx=10, pady=5)
        self.opacity_slider.set(int(round(self.settings.text_opacity * 100)))
        self.opacity_slider.configure(command=self._on_opacity_slider)

        # ============================================================
        # 9. СЕКЦИЯ: ФОН
        # ============================================================
        background_section = ctk.CTkFrame(self)
        background_section.pack(fill="x", padx=10, pady=5)

        bg_flow = ctk.CTkFrame(background_section, fg_color="transparent")
        bg_flow.pack(fill="x", padx=10, pady=5)

        background_color_label = ctk.CTkLabel(bg_flow, text=self.i18n.tr("background") + ":")
        background_color_label.pack(side="left")

        self.background_color_button = ctk.CTkButton(
            bg_flow, text="", command=self._select_background_color,
            width=40, height=24,
        )
        self.background_color_button.pack(side="right", padx=5)
        self.background_color_button.configure(fg_color=self.settings.background_color or "#ffffff")
        if self.settings.transparent_background:
            self.background_color_button.configure(state="disabled")

        transparent_background_check = ctk.CTkCheckBox(
            background_section, text=self.i18n.tr("transparent_bg"),
            variable=self.transparent_background_var,
            command=self._toggle_transparent_background,
            checkbox_height=18, checkbox_width=18,
        )
        transparent_background_check.pack(anchor="w", padx=10, pady=2)

    # ============================================================
    #  ФОНТ и ПРЕСЕТЫ (ручные обработчики)
    # ============================================================

    def _open_system_font_picker(self):
        from ui.dialogs import SystemFontPicker
        dialog = SystemFontPicker(self, self.settings, self.i18n)
        dialog.wait_window()
        if self.settings.font_path:
            self.font_label.configure(
                text=f"{self.i18n.tr('font')}: {os.path.basename(self.settings.font_path)}"
            )
            self._on_change()

    def _select_font(self):
        path = filedialog.askopenfilename(
            title=self.i18n.tr("choose_font"),
            filetypes=[("Font files", "*.ttf *.otf *.ttc *.pfb *.pfm *.fon *.fnt"),
                        ("All files", "*.*")],
        )
        if path:
            self.settings.font_path = path
            self.font_label.configure(text=f"{self.i18n.tr('font')}: {os.path.basename(path)}")
            self._on_change()

    def _reset_icon_size_to_native(self):
        pass

    def _on_font_size_change(self, event):
        try:
            val = int(self.font_size_entry.get())
            if val < FONT_SIZE_MIN:
                val = FONT_SIZE_MIN
            elif val > FONT_SIZE_MAX:
                val = FONT_SIZE_MAX
            self.font_size_slider.set(val)
            self.settings.font_size = val
            self._on_change()
        except ValueError:
            pass

    def _on_font_size_slider(self, value):
        val = int(value)
        self.font_size_entry.delete(0, "end")
        self.font_size_entry.insert(0, str(val))
        self.settings.font_size = val
        self._on_change()

    def _on_alignment_change(self, value):
        self.settings.text_alignment = value
        self._on_change()

    def _on_scale_change(self, event):
        try:
            val = int(self.scale_entry.get())
            if val < -50: val = -50
            elif val > 50: val = 50
            self.scale_slider.set(val)
            self.settings.text_scale_x = (val + 100) / 100.0
            self._on_change()
        except ValueError:
            pass

    def _on_scale_slider(self, value):
        val = int(value)
        self.scale_entry.delete(0, "end")
        self.scale_entry.insert(0, str(val))
        self.settings.text_scale_x = (val + 100) / 100.0
        self._on_change()

    def _on_spacing_change(self, event):
        try:
            val = int(self.spacing_entry.get())
            if val < -20: val = -20
            elif val > 20: val = 20
            self.spacing_slider.set(val)
            self.settings.letter_spacing = val
            self._on_change()
        except ValueError:
            pass

    def _on_spacing_slider(self, value):
        val = int(value)
        self.spacing_entry.delete(0, "end")
        self.spacing_entry.insert(0, str(val))
        self.settings.letter_spacing = val
        self._on_change()

    # ============================================================
    #  TEXT COLOR / TRANSPARENT / CUTOUT (ручные)
    # ============================================================

    def _select_text_color(self):
        from ui.dialogs import ask_color
        color = ask_color(self, self.settings.text_color, self.i18n.tr("text_color"), self.i18n)
        if color:
            self.settings.text_color = color
            self.text_color_button.configure(fg_color=color)
            self._on_change()

    def _toggle_transparent_text(self):
        self.settings.transparent_text = self.transparent_text_var.get()
        if self.settings.transparent_text:
            self.settings.saved_text_color = self.settings.text_color
            self.settings.text_color = "transparent"
            self.text_color_button.configure(state="disabled")
        else:
            self.settings.text_color = self.settings.saved_text_color
            self.text_color_button.configure(state="normal")
        self._on_change()

    def _toggle_cutout_mode(self):
        self.settings.cutout_mode = self.cutout_mode_var.get()
        self._on_change()

    # ============================================================
    #  GRADIENT (ручные обработчики)
    # ============================================================

    def _toggle_gradient(self):
        self.settings.gradient_enabled = self.gradient_enabled_var.get()
        if self.settings.gradient_enabled:
            self.gradient_frame.pack(fill="x")
        else:
            self.gradient_frame.pack_forget()
        self._on_change()

    def _on_gradient_type_change(self, value):
        self.settings.gradient_type = value
        self._on_change()

    def _on_gradient_angle_change(self, event):
        try:
            val = int(self.gradient_angle_entry.get()) % 360
            self.gradient_angle_slider.set(val)
            self.settings.gradient_angle = val
            self._on_change()
        except ValueError:
            pass

    def _on_gradient_angle_slider(self, value):
        val = int(value)
        self.gradient_angle_entry.delete(0, "end")
        self.gradient_angle_entry.insert(0, str(val))
        self.settings.gradient_angle = val
        self._on_change()

    # ============================================================
    #  PATTERN (ручные обработчики)
    # ============================================================

    def _select_pattern_texture(self):
        path = filedialog.askopenfilename(
            title=self.i18n.tr("choose_texture"),
            filetypes=[("Image files", "*.png *.bmp *.gif *.jpg *.jpeg *.webp"),
                        ("All files", "*.*")],
        )
        if path:
            self.settings.pattern_image_path = path
            self.pattern_texture_label.configure(text=os.path.basename(path))
            self._on_change()

    def _toggle_pattern(self):
        self.settings.pattern_enabled = self.pattern_enabled_var.get()
        if self.settings.pattern_enabled:
            self.pattern_frame.pack(fill="x")
        else:
            self.pattern_frame.pack_forget()
        self._on_change()

    def _on_pattern_scale_change(self, event):
        try:
            val = int(self.pattern_scale_entry.get())
            if val < 5: val = 5
            elif val > 500: val = 500
            self.pattern_scale_slider.set(val)
            self.settings.pattern_scale = val
            self._on_change()
        except ValueError:
            pass

    def _on_pattern_scale_slider(self, value):
        val = int(value)
        self.pattern_scale_entry.delete(0, "end")
        self.pattern_scale_entry.insert(0, str(val))
        self.settings.pattern_scale = val
        self._on_change()

    def _on_pattern_offset_x_change(self, event):
        try:
            val = int(self.pattern_offset_x_entry.get())
            self.settings.pattern_offset_x = val
            self._on_change()
        except ValueError:
            pass

    def _on_pattern_offset_y_change(self, event):
        try:
            val = int(self.pattern_offset_y_entry.get())
            self.settings.pattern_offset_y = val
            self._on_change()
        except ValueError:
            pass

    def _on_pattern_angle_change(self, event):
        try:
            val = int(self.pattern_angle_entry.get()) % 360
            self.pattern_angle_slider.set(val)
            self.settings.pattern_angle = val
            self._on_change()
        except ValueError:
            pass

    def _on_pattern_angle_slider(self, value):
        val = int(value)
        self.pattern_angle_entry.delete(0, "end")
        self.pattern_angle_entry.insert(0, str(val))
        self.settings.pattern_angle = val
        self._on_change()

    def _on_pattern_blend_change(self, value):
        self.settings.pattern_blend_mode = value
        self._on_change()

    # ============================================================
    #  SHADOW (ручные обработчики — внешняя тень)
    # ============================================================

    def _toggle_shadow(self):
        self.settings.shadow_enabled = self.shadow_var.get()
        if self.settings.shadow_enabled:
            self.shadow_frame.pack(fill="x")
        else:
            self.shadow_frame.pack_forget()
        self._on_change()

    def _select_shadow_color(self):
        from ui.dialogs import ask_color
        color = ask_color(self, self.settings.shadow_color, self.i18n.tr("shadow_color"), self.i18n)
        if color:
            self.settings.shadow_color = color
            self.shadow_color_button.configure(fg_color=color)
            self._on_change()

    def _on_shadow_distance_change(self, event):
        try:
            val = int(self.shadow_distance_entry.get())
            if val < 0: val = 0
            elif val > 50: val = 50
            self.settings.shadow_distance = val
            self._on_change()
        except ValueError:
            pass

    def _on_shadow_blur_change(self, event):
        try:
            val = int(self.shadow_blur_entry.get())
            if val < 0: val = 0
            elif val > 30: val = 30
            self.settings.shadow_blur = val
            self._on_change()
        except ValueError:
            pass

    def _on_shadow_direction_change(self, value):
        self.settings.shadow_direction = value
        self._on_change()

    def _on_shadow_blend_change(self, value):
        self.settings.shadow_blend_mode = value
        self._on_change()

    # ============================================================
    #  ROTATION (ручные обработчики)
    # ============================================================

    def _on_rotation_change(self, event):
        try:
            val = int(self.rotation_entry.get())
            if val < -180: val = -180
            elif val > 180: val = 180
            self.rotation_slider.set(val)
            self.settings.rotation_angle = val
            self._on_change()
        except ValueError:
            pass

    def _on_rotation_slider(self, value):
        val = int(value)
        self.rotation_entry.delete(0, "end")
        self.rotation_entry.insert(0, str(val))
        self.settings.rotation_angle = val
        self._on_change()

    # ============================================================
    #  ARC (ручные обработчики)
    # ============================================================

    def _toggle_arc_text(self):
        self.settings.arc_text_enabled = self.arc_text_enabled_var.get()
        if self.settings.arc_text_enabled:
            self.arc_frame.pack(fill="x")
        else:
            self.arc_frame.pack_forget()
        self._on_change()

    def _on_arc_clockwise_change(self):
        self.settings.arc_clockwise = self.arc_clockwise_var.get()
        self._on_change()

    def _on_arc_flip_change(self):
        self.settings.arc_flip = self.arc_flip_var.get()
        self._on_change()

    def _on_arc_radius_change(self, event):
        try:
            val = int(self.arc_radius_entry.get())
            if val < 1: val = 1
            elif val > 2000: val = 2000
            self.arc_radius_slider.set(val)
            self.settings.arc_radius = val
            self._on_change()
        except ValueError:
            pass

    def _on_arc_radius_slider(self, value):
        val = int(value)
        self.arc_radius_entry.delete(0, "end")
        self.arc_radius_entry.insert(0, str(val))
        self.settings.arc_radius = val
        self._on_change()

    def _on_arc_angle_change(self, event):
        try:
            val = int(self.arc_start_angle_entry.get()) % 360
            self.arc_start_angle_slider.set(val)
            self.settings.arc_start_angle = val
            self._on_change()
        except ValueError:
            pass

    def _on_arc_angle_slider(self, value):
        val = int(value)
        self.arc_start_angle_entry.delete(0, "end")
        self.arc_start_angle_entry.insert(0, str(val))
        self.settings.arc_start_angle = val
        self._on_change()

    # ============================================================
    #  OPACITY (ручные обработчики)
    # ============================================================

    def _on_opacity_change(self, event):
        try:
            val = int(self.opacity_entry.get())
            if val < 0: val = 0
            elif val > 100: val = 100
            self.opacity_slider.set(val)
            self.settings.text_opacity = val / 100.0
            self._on_change()
        except ValueError:
            pass

    def _on_opacity_slider(self, value):
        val = int(value)
        self.opacity_entry.delete(0, "end")
        self.opacity_entry.insert(0, str(val))
        self.settings.text_opacity = val / 100.0
        self._on_change()

    # ============================================================
    #  BACKGROUND (ручные обработчики)
    # ============================================================

    def _select_background_color(self):
        from ui.dialogs import ask_color
        color = ask_color(self, self.settings.background_color or "#ffffff",
                          self.i18n.tr("background"), self.i18n)
        if color:
            self.settings.background_color = color
            self.background_color_button.configure(fg_color=color)
            self._on_change()

    def _toggle_transparent_background(self):
        self.settings.transparent_background = self.transparent_background_var.get()
        if self.settings.transparent_background:
            if self.settings.background_color is not None:
                self.settings.saved_background_color = self.settings.background_color
            self.settings.background_color = None
            self.background_color_button.configure(state="disabled")
        else:
            self.background_color_button.configure(state="normal")
            saved = getattr(self.settings, "saved_background_color", None)
            if not saved:
                saved = "#ffffff"
            self.settings.background_color = saved
            self.background_color_button.configure(fg_color=saved)
        self._on_change()