# -*- coding: utf-8 -*-
"""
Боковая панель с настройками.

Эффекты из PIPELINE — включая fill-стадию (halftone_mask → color_fill →
gradient → pattern), inner/outer и post — строятся АВТОМАТИЧЕСКИ из
ParamSpec, см. ui/auto_sidebar.py.

Внешняя тень (ShadowOuter) — тоже строится автоматически, но не из
PIPELINE, а из POST_COMPOSE_EFFECTS: она работает с final_img, а не с
char_layer, поэтому вызывается вручную в compose_full. Для UI это
прозрачно — просто order=["shadow"] в build_effect_sections.

Ручные секции (header, font, style-text, rotation, arc, opacity,
background) вынесены в ui/manual_sidebar.py — их фабрики
build_*_section(parent, sidebar, settings, i18n) возвращают dict
виджетов. Sidebar._create_sidebar только собирает всё в нужном порядке
и сохраняет ссылки в self.*, которые нужны MainWindow (см.
main_window.py: sidebar.font_size_entry, sidebar.font_size_slider).
"""

import customtkinter as ctk

from ui.auto_sidebar import build_effect_sections
from ui import manual_sidebar as ms


class Sidebar(ctk.CTkScrollableFrame):
    """Боковая панель с настройками."""

    def __init__(self, parent, settings, i18n):
        super().__init__(parent, width=320, corner_radius=0)
        self.settings = settings
        self.i18n = i18n
        self._on_change_callbacks = []

        # Секции авто-эффектов
        self.effect_sections = {}

        # Публичные атрибуты, которые читает MainWindow
        self.font_size_entry = None
        self.font_size_slider = None

        # Прочие ссылки, которые были у Sidebar раньше (для совместимости
        # с возможным внешним кодом, который мог их читать).
        self.text_color_button = None
        self.rotation_entry = None
        self.rotation_slider = None
        self.arc_frame = None
        self.opacity_entry = None
        self.opacity_slider = None
        self.background_color_button = None
        self.settings_label = None
        self.style_presets_button = None

        # --- СОЗДАЁМ ИНТЕРФЕЙС ---
        self._create_sidebar()

    # ============================================================
    #  Callbacks / refresh
    # ============================================================

    def _on_change(self):
        for callback in self._on_change_callbacks:
            callback()

    def add_change_callback(self, callback):
        self._on_change_callbacks.append(callback)

    def _refresh_all_widgets(self):
        """Обновляет все виджеты после сброса."""
        for widget in self.winfo_children():
            widget.destroy()
        self._create_sidebar()

    # ============================================================
    #  Сборка сайдбара
    # ============================================================

    def _create_sidebar(self):
        """Создаёт весь sidebar."""

        # 1. Header
        header = ms.build_header(self, self, self.settings, self.i18n)
        self.settings_label = header["label"]
        self.style_presets_button = header["presets_button"]

        # 2. Font
        font_w = ms.build_font_section(self, self, self.settings, self.i18n)
        self.font_size_entry = font_w["size_entry"]
        self.font_size_slider = font_w["size_slider"]

        # 3. Style: text color + transparent + cutout (ручное),
        #    gradient + pattern (теперь авто — из PIPELINE fill-стадии).
        style_section = ctk.CTkFrame(self, fg_color="transparent")
        style_section.pack(fill="x", padx=10, pady=5)

        style_text = ms.build_style_text_part(
            style_section, self, self.settings, self.i18n
        )
        self.text_color_button = style_text["text_color_button"]

        # 4a. Первая группа auto-эффектов (включая gradient и pattern —
        #     они идут первыми в order, чтобы остаться на прежнем месте UI:
        #     сразу после text-color, до outline_inner).
        self.effect_sections.update(build_effect_sections(
            style_section, self, self.settings, self.i18n,
            order=[
                "gradient",
                "pattern",
                "outline_inner",
                "outline_outer",
                "glow_inner",
                "glow_outer",
                "extrude",
                "emboss",
                "inner_shadow",
            ],
        ))

        # 4b. Внешняя тень (POST_COMPOSE_EFFECTS)
        self.effect_sections.update(build_effect_sections(
            style_section, self, self.settings, self.i18n,
            order=["shadow"],
        ))

        # 4c. Вторая группа auto-эффектов
        self.effect_sections.update(build_effect_sections(
            style_section, self, self.settings, self.i18n,
            order=[
                "skew",
                "perspective",
                "reflection",
                "halftone",
                "glitch",
            ],
        ))

        # 5. Rotation
        rotation_w = ms.build_rotation_section(
            self, self, self.settings, self.i18n
        )
        self.rotation_entry = rotation_w["entry"]
        self.rotation_slider = rotation_w["slider"]

        # 6. Arc
        arc_w = ms.build_arc_section(self, self, self.settings, self.i18n)
        self.arc_frame = arc_w["body_frame"]

        # 7. Opacity
        opacity_w = ms.build_opacity_section(
            self, self, self.settings, self.i18n
        )
        self.opacity_entry = opacity_w["entry"]
        self.opacity_slider = opacity_w["slider"]

        # 8. Background
        bg_w = ms.build_background_section(
            self, self, self.settings, self.i18n
        )
        self.background_color_button = bg_w["color_button"]