# -*- coding: utf-8 -*-
"""
Левый "рельс" (rail) с пиктограммами эффектов — Photoshop-style.

Каждая иконка соответствует одному эффекту из effects/registry.py
(PIPELINE + POST_COMPOSE_EFFECTS). Клик по иконке делает эффект
"активным" — Sidebar (ui/sidebar.py) показывает справа только его
параметры (см. Sidebar.select_effect / build_single_effect_panel в
ui/auto_sidebar.py).

Включение/выключение эффекта НЕ требует открытия панели параметров —
у каждой строки есть свой чекбокс, как галочка слева от названия
эффекта в панели fx в Photoshop.

Подсветка:
  - включённый эффект (settings.<id>_enabled == True) — зелёный акцент;
  - выбранный сейчас (открыт в панели справа) — синий акцент;
  - both одновременно — выбранный побеждает по цвету, но чекбокс уже
    сам по себе показывает состояние enabled.

Первая строка — "Base": не эффект из реестра, а способ вернуть панель
справа к общим настройкам (шрифт, цвет текста, поворот, дуга,
прозрачность, фон) — тем самым, что раньше были видны без выбора
эффекта.
"""

import customtkinter as ctk

from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS

# Порядок и иконки эффектов на рельсе. Порядок сохраняет прежний
# линейный порядок из ui/sidebar.py — так пользователи, привыкшие к
# старому расположению, не путаются.
RAIL_ORDER = [
    ("gradient",      "🌈"),
    ("pattern",       "🧱"),
    ("outline_inner", "◻"),
    ("outline_outer", "⬜"),
    ("glow_inner",    "🔆"),
    ("glow_outer",    "✨"),
    ("extrude",       "🧊"),
    ("emboss",        "🗿"),
    ("inner_shadow",  "🕳"),
    ("shadow",        "🌑"),
    ("skew",          "📐"),
    ("perspective",   "🎭"),
    ("reflection",    "🪞"),
    ("halftone",      "⚫"),
    ("glitch",        "📺"),
]

BASE_ID = "base"

_COLOR_SELECTED = "#1f538d"
_COLOR_SELECTED_TEXT = "white"
_COLOR_ENABLED = ("#8fd19e", "#1e5631")
_COLOR_ENABLED_TEXT = ("#0a2a12", "#eaffef")
_COLOR_IDLE = ("#dbdbdb", "#2b2b2b")
_COLOR_IDLE_TEXT = ("#1a1a1a", "#e0e0e0")


class EffectRail(ctk.CTkScrollableFrame):
    """Вертикальная плёнка иконок эффектов (левая колонка окна)."""

    def __init__(self, parent, settings, i18n, on_select):
        super().__init__(parent, width=76, corner_radius=0)
        self.settings = settings
        self.i18n = i18n
        self._on_select = on_select
        self._on_change_callbacks = []

        self.selected_id = BASE_ID
        # id -> {"icon_btn": CTkButton, "checkbox": CTkCheckBox|None,
        #        "enabled_var": BooleanVar|None}
        self._rows = {}

        by_id = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}

        self._build_base_row()
        for effect_id, glyph in RAIL_ORDER:
            cls = by_id.get(effect_id)
            if cls is None:
                # Эффект мог быть удалён из реестра — не падаем,
                # просто пропускаем несуществующую иконку.
                continue
            self._build_effect_row(cls, glyph)

    # ------------------------------------------------------------
    #  Callbacks — тот же контракт, что у Sidebar._on_change, чтобы
    #  MainWindow могла подключать оба источника изменений одинаково.
    # ------------------------------------------------------------

    def add_change_callback(self, callback):
        self._on_change_callbacks.append(callback)

    def _on_change(self):
        for callback in self._on_change_callbacks:
            callback()

    # ------------------------------------------------------------
    #  Строим строки рельса
    # ------------------------------------------------------------

    def _build_base_row(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=(4, 10))

        btn = ctk.CTkButton(
            row, text="⚙", width=52, height=40,
            font=("Segoe UI Symbol", 18),
            command=lambda: self._select(BASE_ID),
        )
        btn.pack(padx=4)

        ctk.CTkLabel(row, text=self.i18n.tr("settings"),
                     font=("Arial", 9), wraplength=68).pack()

        self._rows[BASE_ID] = {"icon_btn": btn, "checkbox": None, "enabled_var": None}
        self._update_row_style(BASE_ID)

    def _build_effect_row(self, cls, glyph):
        effect_id = cls.id
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", pady=3)

        icon_btn = ctk.CTkButton(
            row, text=glyph, width=52, height=36,
            font=("Segoe UI Symbol", 16),
            command=lambda eid=effect_id: self._select(eid),
        )
        icon_btn.pack(padx=4)

        enabled_key = f"{effect_id}_enabled"
        enabled_var = ctk.BooleanVar(value=bool(getattr(self.settings, enabled_key, False)))

        def on_toggle(eid=effect_id, key=enabled_key, var=enabled_var):
            setattr(self.settings, key, bool(var.get()))
            self._update_row_style(eid)
            self._on_change()

        checkbox = ctk.CTkCheckBox(
            row, text="", variable=enabled_var, command=on_toggle,
            width=18, checkbox_width=16, checkbox_height=16,
        )
        checkbox.pack(pady=(3, 0))

        ctk.CTkLabel(row, text=self.i18n.tr(cls.label_key),
                     font=("Arial", 9), wraplength=68).pack()

        self._rows[effect_id] = {
            "icon_btn": icon_btn, "checkbox": checkbox, "enabled_var": enabled_var,
        }
        self._update_row_style(effect_id)

    # ------------------------------------------------------------
    #  Выбор / подсветка
    # ------------------------------------------------------------

    def _select(self, effect_id):
        previous = self.selected_id
        self.selected_id = effect_id
        self._update_row_style(previous)
        self._update_row_style(effect_id)
        self._on_select(effect_id)

    def _update_row_style(self, effect_id):
        info = self._rows.get(effect_id)
        if info is None:
            return
        is_selected = (self.selected_id == effect_id)
        is_enabled = effect_id != BASE_ID and bool(
            getattr(self.settings, f"{effect_id}_enabled", False)
        )

        if is_selected:
            fg, text_color = _COLOR_SELECTED, _COLOR_SELECTED_TEXT
        elif is_enabled:
            fg, text_color = _COLOR_ENABLED, _COLOR_ENABLED_TEXT
        else:
            fg, text_color = _COLOR_IDLE, _COLOR_IDLE_TEXT

        info["icon_btn"].configure(fg_color=fg, text_color=text_color)

    # ------------------------------------------------------------
    #  Синхронизация извне (Undo/Redo, сброс настроек, пресеты,
    #  переключение чекбокса ИЗ панели параметров справа)
    # ------------------------------------------------------------

    def refresh(self):
        """
        Перечитывает enabled-флаги из settings и перекрашивает рельс.

        Нужно вызывать после ЛЮБОГО изменения settings, которое могло
        произойти не через сам рельс: Undo/Redo, сброс настроек,
        загрузку пресета стиля, переключение чекбокса "enabled" внутри
        панели параметров (build_single_effect_panel в auto_sidebar.py)
        — там свой, независимый BooleanVar.
        """
        for effect_id, info in self._rows.items():
            if effect_id == BASE_ID:
                continue
            var = info.get("enabled_var")
            if var is not None:
                var.set(bool(getattr(self.settings, f"{effect_id}_enabled", False)))
            self._update_row_style(effect_id)
