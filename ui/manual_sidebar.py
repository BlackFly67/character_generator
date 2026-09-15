# -*- coding: utf-8 -*-
"""
Ручные секции боковой панели.

Каждая фабрика build_*_section(parent, sidebar, settings, i18n)
строит одну секцию UI и возвращает dict виджетов, чтобы sidebar.py
мог сохранить нужные ссылки в self.*.

Обработчики (command=..., bind(...)) объявлены внутри фабрик как
локальные функции-замыкания — так они рядом с виджетами, которые
обслуживают, и не раздувают Sidebar. Взаимодействие с внешним миром
идёт через:
  - settings (чтение/запись полей)
  - sidebar._on_change() — уведомить превью

Здесь только те секции, которые НЕ являются эффектами из PIPELINE
(их UI строится автоматически в ui/auto_sidebar.py):

  - header (reset / presets),
  - Font,
  - Text color + transparent_text + cutout_mode,
  - Rotation,
  - Arc text,
  - Opacity,
  - Background.

Gradient и Pattern теперь тоже авто — из PIPELINE fill-стадии,
поэтому их ручных фабрик здесь больше нет.
"""

import os
import customtkinter as ctk
from tkinter import filedialog, messagebox

from constants import FONT_SIZE_MIN, FONT_SIZE_MAX


# ============================================================
#  1. HEADER — заголовок с reset / presets
# ============================================================

def build_header(parent, sidebar, settings, i18n):
    widgets = {}

    header = ctk.CTkFrame(parent, fg_color="transparent")
    header.pack(fill="x", padx=10, pady=(15, 10))

    widgets["frame"] = header

    widgets["label"] = ctk.CTkLabel(
        header, text=i18n.tr("settings"), font=("Arial", 18, "bold")
    )
    widgets["label"].pack(side="left")

    reset_button = ctk.CTkButton(
        header, text="↺", width=28, height=28,
        font=("Segoe UI Symbol", 16, "bold"),
        fg_color="#8B0000", hover_color="#5C0000",
        command=lambda: _reset_settings(sidebar, i18n),
    )
    reset_button.pack(side="right")

    presets_button = ctk.CTkButton(
        header, text="🎨 " + i18n.tr("style_presets"),
        command=lambda: _open_presets(sidebar, i18n),
    )
    presets_button.pack(side="right", padx=5)
    widgets["presets_button"] = presets_button

    return widgets


def _reset_settings(sidebar, i18n):
    if messagebox.askyesno(
        i18n.tr("warning"),
        i18n.tr("reset_warning") + "\n\n" + i18n.tr("reset_confirm")
    ):
        sidebar.settings.reset()
        sidebar._refresh_all_widgets()
        sidebar._on_change()
        messagebox.showinfo(i18n.tr("done"), i18n.tr("settings_reset"))


def _open_presets(sidebar, i18n):
    from ui.dialogs import StylePresetsDialog
    dialog = StylePresetsDialog(sidebar, sidebar.settings, i18n)
    dialog.wait_window()
    sidebar._refresh_all_widgets()
    sidebar._on_change()


# ============================================================
#  2. FONT
# ============================================================

def build_font_section(parent, sidebar, settings, i18n):
    widgets = {}

    font_section = ctk.CTkFrame(parent)
    font_section.pack(fill="x", padx=10, pady=5)
    widgets["frame"] = font_section

    font_choice_frame = ctk.CTkFrame(font_section, fg_color="transparent")
    font_choice_frame.pack(fill="x", padx=10, pady=2)

    font_name = (os.path.basename(settings.font_path)
                 if settings.font_path else i18n.tr("no_font"))
    widgets["label"] = ctk.CTkLabel(
        font_choice_frame,
        text=f"{i18n.tr('font')}: {font_name}",
        font=("Arial", 12, "bold"),
    )
    widgets["label"].pack(anchor="w", pady=5)

    ctk.CTkButton(
        font_choice_frame, text=i18n.tr("system_font"),
        command=lambda: _open_system_font_picker(sidebar, i18n, widgets["label"]),
    ).pack(fill="x", pady=5)

    ctk.CTkButton(
        font_choice_frame, text=i18n.tr("choose_font"),
        command=lambda: _select_font(sidebar, i18n, widgets["label"]),
    ).pack(fill="x", pady=5)

    font_props_frame = ctk.CTkFrame(font_section, fg_color="transparent")
    font_props_frame.pack(fill="x", padx=10, pady=2)

    size_row = ctk.CTkFrame(font_props_frame, fg_color="transparent")
    size_row.pack(fill="x", pady=2)

    ctk.CTkLabel(size_row, text=i18n.tr("size") + ":").pack(side="left")

    size_entry = ctk.CTkEntry(size_row, width=55)
    size_entry.insert(0, str(settings.font_size))
    size_entry.pack(side="left", padx=5)
    widgets["size_entry"] = size_entry

    ctk.CTkButton(
        size_row, text="⟲", width=28, height=28,
        font=("Segoe UI Symbol", 14),
        state="disabled",
        command=lambda: None,
    ).pack(side="right", padx=(5, 0))

    size_slider = ctk.CTkSlider(
        size_row, from_=FONT_SIZE_MIN, to=FONT_SIZE_MAX,
        number_of_steps=FONT_SIZE_MAX - FONT_SIZE_MIN,
    )
    size_slider.set(settings.font_size)
    size_slider.pack(side="left", padx=5, fill="x", expand=True)
    widgets["size_slider"] = size_slider

    def on_size_entry(event=None):
        try:
            val = int(size_entry.get())
            val = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, val))
            size_slider.set(val)
            settings.font_size = val
            sidebar._on_change()
        except ValueError:
            pass

    def on_size_slider(value):
        val = int(value)
        size_entry.delete(0, "end")
        size_entry.insert(0, str(val))
        settings.font_size = val
        sidebar._on_change()

    size_entry.bind("<KeyRelease>", on_size_entry)
    size_slider.configure(command=on_size_slider)

    alignment_frame = ctk.CTkFrame(font_props_frame, fg_color="transparent")
    alignment_frame.pack(fill="x", pady=2)

    ctk.CTkLabel(alignment_frame, text=i18n.tr("align") + ":").pack(side="left")

    alignment_var = ctk.StringVar(value=settings.text_alignment)
    alignment_menu = ctk.CTkOptionMenu(
        alignment_frame, values=["left", "center", "right"],
        variable=alignment_var, width=90,
        command=lambda v: (setattr(settings, "text_alignment", v), sidebar._on_change()),
    )
    alignment_menu.pack(side="left", padx=5)
    widgets["alignment_var"] = alignment_var

    scale_section = ctk.CTkFrame(font_section, fg_color="transparent")
    scale_section.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(scale_section, text=i18n.tr("text_scale") + " (%):",
                 font=("Arial", 11)).pack(side="left")

    scale_init = int(round((settings.text_scale_x - 1.0) * 100))
    scale_entry = ctk.CTkEntry(scale_section, width=40)
    scale_entry.insert(0, str(scale_init))
    scale_entry.pack(side="right", padx=(5, 0))
    widgets["scale_entry"] = scale_entry

    scale_slider = ctk.CTkSlider(scale_section, from_=-50, to=50, number_of_steps=100)
    scale_slider.pack(side="left", padx=5, fill="x", expand=True)
    scale_slider.set(scale_init)
    widgets["scale_slider"] = scale_slider

    def on_scale_entry(event=None):
        try:
            val = int(scale_entry.get())
            val = max(-50, min(50, val))
            scale_slider.set(val)
            settings.text_scale_x = (val + 100) / 100.0
            sidebar._on_change()
        except ValueError:
            pass

    def on_scale_slider(value):
        val = int(value)
        scale_entry.delete(0, "end")
        scale_entry.insert(0, str(val))
        settings.text_scale_x = (val + 100) / 100.0
        sidebar._on_change()

    scale_entry.bind("<KeyRelease>", on_scale_entry)
    scale_slider.configure(command=on_scale_slider)

    spacing_section = ctk.CTkFrame(font_section, fg_color="transparent")
    spacing_section.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(spacing_section, text=i18n.tr("letter_spacing") + " (px):",
                 font=("Arial", 11)).pack(side="left")

    spacing_entry = ctk.CTkEntry(spacing_section, width=40)
    spacing_entry.insert(0, str(settings.letter_spacing))
    spacing_entry.pack(side="right", padx=(5, 0))
    widgets["spacing_entry"] = spacing_entry

    spacing_slider = ctk.CTkSlider(spacing_section, from_=-20, to=20, number_of_steps=40)
    spacing_slider.pack(side="left", padx=5, fill="x", expand=True)
    spacing_slider.set(settings.letter_spacing)
    widgets["spacing_slider"] = spacing_slider

    def on_spacing_entry(event=None):
        try:
            val = int(spacing_entry.get())
            val = max(-20, min(20, val))
            spacing_slider.set(val)
            settings.letter_spacing = val
            sidebar._on_change()
        except ValueError:
            pass

    def on_spacing_slider(value):
        val = int(value)
        spacing_entry.delete(0, "end")
        spacing_entry.insert(0, str(val))
        settings.letter_spacing = val
        sidebar._on_change()

    spacing_entry.bind("<KeyRelease>", on_spacing_entry)
    spacing_slider.configure(command=on_spacing_slider)

    return widgets


def _open_system_font_picker(sidebar, i18n, font_label):
    from ui.dialogs import SystemFontPicker
    dialog = SystemFontPicker(sidebar, sidebar.settings, i18n)
    dialog.wait_window()
    if sidebar.settings.font_path:
        font_label.configure(
            text=f"{i18n.tr('font')}: {os.path.basename(sidebar.settings.font_path)}"
        )
        sidebar._on_change()


def _select_font(sidebar, i18n, font_label):
    path = filedialog.askopenfilename(
        title=i18n.tr("choose_font"),
        filetypes=[("Font files", "*.ttf *.otf *.ttc *.pfb *.pfm *.fon *.fnt"),
                   ("All files", "*.*")],
    )
    if path:
        sidebar.settings.font_path = path
        font_label.configure(text=f"{i18n.tr('font')}: {os.path.basename(path)}")
        sidebar._on_change()


# ============================================================
#  3. STYLE — text color + transparent + cutout
# ============================================================

def build_style_text_part(parent, sidebar, settings, i18n):
    widgets = {}

    ctk.CTkLabel(
        parent, text=i18n.tr("text_style"),
        font=("Arial", 12, "bold"),
    ).pack(anchor="w", padx=10, pady=2)

    color_flow = ctk.CTkFrame(parent, fg_color="transparent")
    color_flow.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(color_flow, text=i18n.tr("text_color") + ":").pack(side="left")

    text_color_button = ctk.CTkButton(color_flow, text="", width=40, height=24)
    text_color_button.pack(side="right", padx=5)
    text_color_button.configure(fg_color=settings.text_color)
    widgets["text_color_button"] = text_color_button

    def select_text_color():
        from ui.dialogs import ask_color
        color = ask_color(sidebar, settings.text_color, i18n.tr("text_color"), i18n)
        if color:
            settings.text_color = color
            text_color_button.configure(fg_color=color)
            sidebar._on_change()

    text_color_button.configure(command=select_text_color)

    transparent_var = ctk.BooleanVar(value=settings.transparent_text)
    widgets["transparent_var"] = transparent_var

    def toggle_transparent_text():
        settings.transparent_text = transparent_var.get()
        if settings.transparent_text:
            settings.saved_text_color = settings.text_color
            settings.text_color = "transparent"
            text_color_button.configure(state="disabled")
        else:
            settings.text_color = settings.saved_text_color
            text_color_button.configure(state="normal")
        sidebar._on_change()

    ctk.CTkCheckBox(
        parent, text=i18n.tr("transparent"),
        variable=transparent_var,
        command=toggle_transparent_text,
        checkbox_height=18, checkbox_width=18,
    ).pack(anchor="w", padx=10, pady=2)

    cutout_var = ctk.BooleanVar(value=settings.cutout_mode)
    widgets["cutout_var"] = cutout_var

    ctk.CTkCheckBox(
        parent, text=i18n.tr("cutout"),
        variable=cutout_var,
        command=lambda: (setattr(settings, "cutout_mode", cutout_var.get()),
                         sidebar._on_change()),
        checkbox_height=18, checkbox_width=18,
    ).pack(anchor="w", padx=10, pady=2)

    return widgets


# ============================================================
#  4. ROTATION
# ============================================================

def build_rotation_section(parent, sidebar, settings, i18n):
    widgets = {}

    rotation_section = ctk.CTkFrame(parent)
    rotation_section.pack(fill="x", padx=10, pady=5)
    widgets["frame"] = rotation_section

    entry_frame = ctk.CTkFrame(rotation_section, fg_color="transparent")
    entry_frame.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(entry_frame, text=i18n.tr("rotation") + " (°):",
                 font=("Arial", 11)).pack(side="left")

    rotation_entry = ctk.CTkEntry(entry_frame, width=40)
    rotation_entry.insert(0, str(settings.rotation_angle))
    rotation_entry.pack(side="right", padx=(5, 0))
    widgets["entry"] = rotation_entry

    slider_frame = ctk.CTkFrame(rotation_section, fg_color="transparent")
    slider_frame.pack(fill="x", padx=10, pady=2)

    rotation_slider = ctk.CTkSlider(
        slider_frame, from_=-180, to=180, number_of_steps=360,
    )
    rotation_slider.pack(fill="x", padx=5, pady=2)
    rotation_slider.set(settings.rotation_angle)
    widgets["slider"] = rotation_slider

    def on_rotation_entry(event=None):
        try:
            val = int(rotation_entry.get())
            val = max(-180, min(180, val))
            rotation_slider.set(val)
            settings.rotation_angle = val
            sidebar._on_change()
        except ValueError:
            pass

    def on_rotation_slider(value):
        val = int(value)
        rotation_entry.delete(0, "end")
        rotation_entry.insert(0, str(val))
        settings.rotation_angle = val
        sidebar._on_change()

    rotation_entry.bind("<KeyRelease>", on_rotation_entry)
    rotation_slider.configure(command=on_rotation_slider)

    return widgets


# ============================================================
#  5. ARC TEXT
# ============================================================

def build_arc_section(parent, sidebar, settings, i18n):
    widgets = {}

    arc_section = ctk.CTkFrame(parent)
    arc_section.pack(fill="x", padx=10, pady=5)
    widgets["frame"] = arc_section

    arc_enabled_var = ctk.BooleanVar(value=settings.arc_text_enabled)
    widgets["enabled_var"] = arc_enabled_var

    arc_frame = ctk.CTkFrame(arc_section, fg_color="transparent")
    widgets["body_frame"] = arc_frame

    def toggle_arc():
        settings.arc_text_enabled = arc_enabled_var.get()
        if settings.arc_text_enabled:
            arc_frame.pack(fill="x")
        else:
            arc_frame.pack_forget()
        sidebar._on_change()

    ctk.CTkCheckBox(
        arc_section, text=i18n.tr("arc_text"),
        variable=arc_enabled_var,
        command=toggle_arc,
        checkbox_height=18, checkbox_width=18,
    ).pack(anchor="w", padx=10, pady=2)

    if settings.arc_text_enabled:
        arc_frame.pack(fill="x")

    # --- radius ---
    radius_flow = ctk.CTkFrame(arc_frame, fg_color="transparent")
    radius_flow.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(radius_flow, text=i18n.tr("arc_radius") + ":").pack(side="left")

    radius_entry = ctk.CTkEntry(radius_flow, width=50)
    radius_entry.insert(0, str(settings.arc_radius))
    radius_entry.pack(side="right", padx=(5, 0))
    widgets["radius_entry"] = radius_entry

    radius_slider = ctk.CTkSlider(radius_flow, from_=1, to=2000, number_of_steps=1990)
    radius_slider.pack(side="left", padx=5, fill="x", expand=True)
    radius_slider.set(settings.arc_radius)
    widgets["radius_slider"] = radius_slider

    def on_radius_entry(event=None):
        try:
            val = int(radius_entry.get())
            val = max(1, min(2000, val))
            radius_slider.set(val)
            settings.arc_radius = val
            sidebar._on_change()
        except ValueError:
            pass

    def on_radius_slider(value):
        val = int(value)
        radius_entry.delete(0, "end")
        radius_entry.insert(0, str(val))
        settings.arc_radius = val
        sidebar._on_change()

    radius_entry.bind("<KeyRelease>", on_radius_entry)
    radius_slider.configure(command=on_radius_slider)

    # --- start angle ---
    angle_flow = ctk.CTkFrame(arc_frame, fg_color="transparent")
    angle_flow.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(angle_flow, text=i18n.tr("arc_start_angle") + " (°):").pack(side="left")

    angle_entry = ctk.CTkEntry(angle_flow, width=50)
    angle_entry.insert(0, str(settings.arc_start_angle))
    angle_entry.pack(side="right", padx=(5, 0))
    widgets["angle_entry"] = angle_entry

    angle_slider = ctk.CTkSlider(angle_flow, from_=0, to=360, number_of_steps=360)
    angle_slider.pack(side="left", padx=5, fill="x", expand=True)
    angle_slider.set(settings.arc_start_angle)
    widgets["angle_slider"] = angle_slider

    def on_angle_entry(event=None):
        try:
            val = int(angle_entry.get()) % 360
            angle_slider.set(val)
            settings.arc_start_angle = val
            sidebar._on_change()
        except ValueError:
            pass

    def on_angle_slider(value):
        val = int(value)
        angle_entry.delete(0, "end")
        angle_entry.insert(0, str(val))
        settings.arc_start_angle = val
        sidebar._on_change()

    angle_entry.bind("<KeyRelease>", on_angle_entry)
    angle_slider.configure(command=on_angle_slider)

    # --- clockwise / flip ---
    options_flow = ctk.CTkFrame(arc_frame, fg_color="transparent")
    options_flow.pack(fill="x", padx=10, pady=(2, 8))

    cw_var = ctk.BooleanVar(value=settings.arc_clockwise)
    widgets["clockwise_var"] = cw_var
    ctk.CTkCheckBox(
        options_flow, text=i18n.tr("arc_clockwise"),
        variable=cw_var,
        command=lambda: (setattr(settings, "arc_clockwise", cw_var.get()),
                         sidebar._on_change()),
        checkbox_height=18, checkbox_width=18,
    ).pack(side="left", padx=(0, 15))

    flip_var = ctk.BooleanVar(value=settings.arc_flip)
    widgets["flip_var"] = flip_var
    ctk.CTkCheckBox(
        options_flow, text=i18n.tr("arc_flip"),
        variable=flip_var,
        command=lambda: (setattr(settings, "arc_flip", flip_var.get()),
                         sidebar._on_change()),
        checkbox_height=18, checkbox_width=18,
    ).pack(side="left")

    return widgets


# ============================================================
#  6. OPACITY
# ============================================================

def build_opacity_section(parent, sidebar, settings, i18n):
    widgets = {}

    opacity_section = ctk.CTkFrame(parent)
    opacity_section.pack(fill="x", padx=10, pady=5)
    widgets["frame"] = opacity_section

    entry_frame = ctk.CTkFrame(opacity_section, fg_color="transparent")
    entry_frame.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(entry_frame, text=i18n.tr("opacity") + " (%):",
                 font=("Arial", 11)).pack(side="left")

    opacity_entry = ctk.CTkEntry(entry_frame, width=50)
    init_val = int(round(settings.text_opacity * 100))
    opacity_entry.insert(0, str(init_val))
    opacity_entry.pack(side="right", padx=(5, 0))
    widgets["entry"] = opacity_entry

    slider_frame = ctk.CTkFrame(opacity_section, fg_color="transparent")
    slider_frame.pack(fill="x", padx=10, pady=2)

    opacity_slider = ctk.CTkSlider(slider_frame, from_=0, to=100, number_of_steps=100)
    opacity_slider.pack(fill="x", padx=5, pady=2)
    opacity_slider.set(init_val)
    widgets["slider"] = opacity_slider

    def on_opacity_entry(event=None):
        try:
            val = int(opacity_entry.get())
            val = max(0, min(100, val))
            opacity_slider.set(val)
            settings.text_opacity = val / 100.0
            sidebar._on_change()
        except ValueError:
            pass

    def on_opacity_slider(value):
        val = int(value)
        opacity_entry.delete(0, "end")
        opacity_entry.insert(0, str(val))
        settings.text_opacity = val / 100.0
        sidebar._on_change()

    opacity_entry.bind("<KeyRelease>", on_opacity_entry)
    opacity_slider.configure(command=on_opacity_slider)

    return widgets


# ============================================================
#  7. BACKGROUND
# ============================================================

def build_background_section(parent, sidebar, settings, i18n):
    widgets = {}

    background_section = ctk.CTkFrame(parent)
    background_section.pack(fill="x", padx=10, pady=5)
    widgets["frame"] = background_section

    bg_flow = ctk.CTkFrame(background_section, fg_color="transparent")
    bg_flow.pack(fill="x", padx=10, pady=2)

    ctk.CTkLabel(bg_flow, text=i18n.tr("background") + ":").pack(side="left")

    bg_color_button = ctk.CTkButton(bg_flow, text="", width=40, height=24)
    bg_color_button.pack(side="right", padx=5)
    bg_color_button.configure(fg_color=settings.background_color or "#ffffff")
    if settings.transparent_background:
        bg_color_button.configure(state="disabled")
    widgets["color_button"] = bg_color_button

    def select_background_color():
        from ui.dialogs import ask_color
        color = ask_color(sidebar, settings.background_color or "#ffffff",
                          i18n.tr("background"), i18n)
        if color:
            settings.background_color = color
            bg_color_button.configure(fg_color=color)
            sidebar._on_change()

    bg_color_button.configure(command=select_background_color)

    transparent_bg_var = ctk.BooleanVar(value=settings.transparent_background)
    widgets["transparent_var"] = transparent_bg_var

    def toggle_transparent_background():
        settings.transparent_background = transparent_bg_var.get()
        if settings.transparent_background:
            if settings.background_color is not None:
                settings.saved_background_color = settings.background_color
            settings.background_color = None
            bg_color_button.configure(state="disabled")
        else:
            bg_color_button.configure(state="normal")
            saved = getattr(settings, "saved_background_color", None)
            if not saved:
                saved = "#000000"
            settings.background_color = saved
            bg_color_button.configure(fg_color=saved)
        sidebar._on_change()

    ctk.CTkCheckBox(
        background_section, text=i18n.tr("transparent_bg"),
        variable=transparent_bg_var,
        command=toggle_transparent_background,
        checkbox_height=18, checkbox_width=18,
    ).pack(anchor="w", padx=10, pady=2)

    return widgets