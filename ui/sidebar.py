# -*- coding: utf-8 -*-
"""
Боковая панель с настройками — Photoshop-style режим.

Раньше Sidebar показывал ВСЕ секции (шрифт, стиль, все эффекты) одним
длинным списком с прокруткой. Теперь это правая колонка окна:
пиктограммы эффектов вынесены в отдельный виджет EffectRail
(ui/effect_rail.py, левая колонка), а Sidebar показывает НАСТРОЙКИ
ТОЛЬКО ОДНОГО активного раздела за раз:

  - selected_effect_id == BASE_ID ("base") — общие настройки: шрифт,
    цвет текста, поворот, дуга, прозрачность, фон (build_*_section из
    ui/manual_sidebar.py — как раньше, без эффектов из PIPELINE);
  - selected_effect_id == <effect_id> — параметры одного эффекта из
    PIPELINE/POST_COMPOSE_EFFECTS (build_single_effect_panel из
    ui/auto_sidebar.py).

EffectRail сообщает о выборе через колбэк on_select, переданный при
создании (см. MainWindow._create_layout -> EffectRail(..., on_select=
self._on_effect_selected) -> self.sidebar.select_effect(effect_id)).

Header (reset / presets) остаётся виден всегда — это глобальные
действия, не привязанные к конкретному эффекту.
"""

import customtkinter as ctk

from ui.auto_sidebar import build_single_effect_panel
from ui.effect_rail import BASE_ID
from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS
from ui import manual_sidebar as ms


class Sidebar(ctk.CTkScrollableFrame):
    """Правая панель настроек: Base или один активный эффект."""

    def __init__(self, parent, settings, i18n):
        super().__init__(parent, width=320, corner_radius=0)
        self.settings = settings
        self.i18n = i18n
        self._on_change_callbacks = []

        # Какой раздел сейчас показан справа: BASE_ID или id эффекта.
        self.selected_effect_id = BASE_ID

        # BooleanVar чекбокса "включено" ТЕКУЩЕЙ открытой панели эффекта
        # (None, если сейчас показан Base). Нужна для
        # sync_enabled_checkbox() — синхронизации со значением,
        # переключённым через чекбокс НА РЕЛЬСЕ (EffectRail), у которого
        # свой, независимый BooleanVar на тот же settings.<id>_enabled.
        self._current_enabled_var = None

        # Публичные атрибуты, которые читает MainWindow. Существуют
        # ТОЛЬКО когда открыт Base-раздел (там же и создаются) — в
        # остальное время равны None. Вызывающий код в main_window.py
        # обязан проверять на None (не просто hasattr — атрибут
        # объявлен всегда, но может указывать на уже уничтоженный
        # виджет после _refresh_all_widgets(), если панель эффекта
        # была открыта не в первый раз).
        self.font_size_entry = None
        self.font_size_slider = None

        # Прочие ссылки, которые были у Sidebar раньше (для совместимости
        # с возможным внешним кодом, который мог их читать). Тоже валидны
        # только при selected_effect_id == BASE_ID.
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
        """Обновляет все виджеты (текущего раздела) после сброса."""
        for widget in self.winfo_children():
            widget.destroy()
        self._create_sidebar()

    # ------------------------------------------------------------
    #  Выбор раздела — вызывается из MainWindow по клику на рельсе
    # ------------------------------------------------------------

    def select_effect(self, effect_id):
        """Переключает панель на Base или на один из эффектов."""
        self.selected_effect_id = effect_id
        self._refresh_all_widgets()

    def sync_enabled_checkbox(self):
        """
        Подтягивает enabled_var текущей открытой панели эффекта из
        settings. Нужно вызывать после ЛЮБОГО изменения settings извне
        текущей панели (в первую очередь — после переключения чекбокса
        на самой иконке в EffectRail: там свой BooleanVar, физически
        не связанный с тем, что лежит в панели справа).

        Если сейчас открыт Base — делать нечего (_current_enabled_var
        is None).
        """
        if self._current_enabled_var is None:
            return
        if self.selected_effect_id in (None, BASE_ID):
            return
        key = f"{self.selected_effect_id}_enabled"
        self._current_enabled_var.set(bool(getattr(self.settings, key, False)))

    # ============================================================
    #  Сборка сайдбара
    # ============================================================

    def _create_sidebar(self):
        """Создаёт содержимое текущего раздела (Base или эффект)."""

        # Header виден всегда — reset/presets не привязаны к разделу.
        header = ms.build_header(self, self, self.settings, self.i18n)
        self.settings_label = header["label"]
        self.style_presets_button = header["presets_button"]

        if self.selected_effect_id in (None, BASE_ID):
            self.selected_effect_id = BASE_ID
            self._current_enabled_var = None
            self._build_base_section()
        else:
            self._build_effect_section(self.selected_effect_id)

    def _build_base_section(self):
        """Общие настройки — то, что раньше было видно без выбора эффекта."""

        # font_size_entry/slider существуют ТОЛЬКО пока открыт Base —
        # обнуляем на входе в _build_effect_section (см. ниже), чтобы
        # main_window.py не трогал уничтоженные виджеты (см. комментарий
        # в __init__).
        font_w = ms.build_font_section(self, self, self.settings, self.i18n)
        self.font_size_entry = font_w["size_entry"]
        self.font_size_slider = font_w["size_slider"]

        style_section = ctk.CTkFrame(self, fg_color="transparent")
        style_section.pack(fill="x", padx=10, pady=5)

        style_text = ms.build_style_text_part(
            style_section, self, self.settings, self.i18n
        )
        self.text_color_button = style_text["text_color_button"]

        rotation_w = ms.build_rotation_section(
            self, self, self.settings, self.i18n
        )
        self.rotation_entry = rotation_w["entry"]
        self.rotation_slider = rotation_w["slider"]

        arc_w = ms.build_arc_section(self, self, self.settings, self.i18n)
        self.arc_frame = arc_w["body_frame"]

        opacity_w = ms.build_opacity_section(
            self, self, self.settings, self.i18n
        )
        self.opacity_entry = opacity_w["entry"]
        self.opacity_slider = opacity_w["slider"]

        bg_w = ms.build_background_section(
            self, self, self.settings, self.i18n
        )
        self.background_color_button = bg_w["color_button"]

    def _build_effect_section(self, effect_id):
        """Параметры одного эффекта (PIPELINE/POST_COMPOSE_EFFECTS)."""

        # Base-виджеты сейчас не существуют — обнуляем ссылки, чтобы
        # main_window.py не пытался писать в уже уничтоженные объекты
        # (см. комментарий у self.font_size_entry в __init__).
        self.font_size_entry = None
        self.font_size_slider = None
        self.text_color_button = None
        self.rotation_entry = None
        self.rotation_slider = None
        self.arc_frame = None
        self.opacity_entry = None
        self.opacity_slider = None
        self.background_color_button = None

        by_id = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}
        cls = by_id.get(effect_id)
        if cls is None:
            # Неизвестный/удалённый из реестра id — не падаем, тихо
            # откатываемся на Base.
            self.selected_effect_id = BASE_ID
            self._current_enabled_var = None
            self._build_base_section()
            return

        panel = build_single_effect_panel(self, self, self.settings, self.i18n, cls)
        self._current_enabled_var = panel["enabled_var"]
