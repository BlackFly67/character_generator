# -*- coding: utf-8 -*-
"""
Левая колонка с иконками эффектов.

Структура:
  [Base]       Aa ◨ ■
  [Fill]       ▤ ▦ ⁙
  ...
  [Extra]      ◑ ▨
  ------------
  [↺] [🎨]

Каждая иконка — CTkButton с emoji/Unicode-символом. Подсветка:
  - активная (текущая в SettingsPanel) — обводка акцентным цветом;
  - enabled=True — акцентный фон;
  - enabled=False или нет флага — нейтральный.

Rail НЕ знает про SettingsPanel. Он сообщает о клике через callback
on_select(effect_id). Также есть on_reset и on_presets — кнопки внизу.
"""

import customtkinter as ctk

from ui.icons import RAIL_ICONS, RAIL_GROUPS, ENABLEABLE_IDS, get_icon
from ui.tooltip import Tooltip


# Размеры
RAIL_WIDTH = 68
ICON_BTN_SIZE = 40
ICON_FONT_SIZE = 16
SEPARATOR_HEIGHT = 1


class IconRail(ctk.CTkFrame):
    def __init__(self, parent, settings, i18n,
                 on_select=None, on_reset=None, on_presets=None):
        super().__init__(parent, width=RAIL_WIDTH, corner_radius=0)
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.settings = settings
        self.i18n = i18n
        self.on_select = on_select
        self.on_reset = on_reset
        self.on_presets = on_presets

        self.current_effect_id = None
        self._buttons = {}      # effect_id -> CTkButton
        self._tooltips = {}     # effect_id -> Tooltip

        self._build()

    # ============================================================
    #  Построение
    # ============================================================

    def _build(self):
        # Скроллируемая область для иконок (на случай, если не
        # влезут на маленьком экране).
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=("#c0c0c0", "#3a3a3a"),
            scrollbar_button_hover_color=("#a0a0a0", "#505050"),
        )
        self.scroll.pack(fill="both", expand=True, padx=2, pady=(6, 4))
        self.scroll._scrollbar.configure(width=6)

        inner = self.scroll

        first_group = True
        for group_id, ids in RAIL_GROUPS:
            if not first_group:
                sep = ctk.CTkFrame(
                    inner, height=SEPARATOR_HEIGHT,
                    fg_color=("#c0c0c0", "#3a3a3a"),
                )
                sep.pack(fill="x", padx=12, pady=(6, 6))
            first_group = False

            for effect_id in ids:
                self._add_icon_button(inner, effect_id)

        # Нижний блок: reset + presets. Отделён от иконок спейсером,
        # чтобы визуально не смешивался с эффектами.
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(side="bottom", fill="x", padx=4, pady=(4, 8))

        reset_btn = ctk.CTkButton(
            bottom, text="↺", width=ICON_BTN_SIZE, height=ICON_BTN_SIZE,
            font=("Segoe UI Symbol", ICON_FONT_SIZE, "bold"),
            fg_color="transparent",
            hover_color=("#c7c7c7", "#3a3a3a"),
            text_color=("#8B0000", "#d97a7a"),
            border_width=0,
            command=self._handle_reset,
        )
        reset_btn.pack(pady=2)
        Tooltip(reset_btn, self.i18n.tr("reset"))

        presets_btn = ctk.CTkButton(
            bottom, text="🎨", width=ICON_BTN_SIZE, height=ICON_BTN_SIZE,
            font=("Segoe UI Symbol", ICON_FONT_SIZE),
            fg_color="transparent",
            hover_color=("#c7c7c7", "#3a3a3a"),
            text_color=("#1a1a1a", "#e0e0e0"),
            border_width=0,
            command=self._handle_presets,
        )
        presets_btn.pack(pady=2)
        Tooltip(presets_btn, self.i18n.tr("style_presets"))

    def _add_icon_button(self, parent, effect_id):
        symbol, label_key = get_icon(effect_id)
        label = self.i18n.tr(label_key)

        btn = ctk.CTkButton(
            parent, text=symbol,
            width=ICON_BTN_SIZE, height=ICON_BTN_SIZE,
            font=("Segoe UI Symbol", ICON_FONT_SIZE),
            fg_color="transparent",
            hover_color=("#c7c7c7", "#3a3a3a"),
            text_color=("#4a4a4a", "#c0c0c0"),
            border_width=2,
            border_color=("#c7c7c7", "#3a3a3a"),
            corner_radius=6,
            command=lambda eid=effect_id: self._handle_click(eid),
        )
        btn.pack(pady=3)
        self._buttons[effect_id] = btn
        self._tooltips[effect_id] = Tooltip(btn, label)

    # ============================================================
    #  Callbacks
    # ============================================================

    def _handle_click(self, effect_id):
        if callable(self.on_select):
            self.on_select(effect_id)

    def _handle_reset(self):
        if callable(self.on_reset):
            self.on_reset()

    def _handle_presets(self):
        if callable(self.on_presets):
            self.on_presets()

    # ============================================================
    #  Публичный API
    # ============================================================

    def set_active(self, effect_id):
        """
        Подсветить активную иконку (обводка акцентным цветом).
        Вызывается из MainWindow при клике по иконке или при
        смене активного эффекта извне.
        """
        self.current_effect_id = effect_id
        for eid, btn in self._buttons.items():
            is_active = (eid == effect_id)
            if is_active:
                btn.configure(
                    border_color="#1f538d",
                    border_width=2,
                )
            else:
                btn.configure(
                    border_color=("#c7c7c7", "#3a3a3a"),
                    border_width=2,
                )
        self._refresh_enabled_highlights()

    def refresh_enabled_highlights(self):
        """
        Пересчитать подсветку enabled-флагов и обновить tooltips.
        Вызывается, когда settings меняются (например, on_toggle
        какого-то эффекта или reset).
        """
        self._refresh_enabled_highlights()

    def refresh_labels(self):
        """
        Обновить tooltip-тексты (например, при смене языка).
        """
        for effect_id, tip in self._tooltips.items():
            _, label_key = get_icon(effect_id)
            tip.set_text(self.i18n.tr(label_key))

    # ============================================================
    #  Внутреннее
    # ============================================================

    def _refresh_enabled_highlights(self):
        for effect_id, btn in self._buttons.items():
            enabled = self._is_enabled(effect_id)
            is_active = (effect_id == self.current_effect_id)

            # Текст: акцентный, если enabled; приглушённый, если нет.
            if enabled:
                btn.configure(
                    text_color=("#1a1a1a", "#ffffff"),
                    fg_color=("#1f538d", "#1f538d"),
                )
            else:
                btn.configure(
                    text_color=("#4a4a4a", "#c0c0c0"),
                    fg_color="transparent",
                )

            # Обводка: акцентная для активной, иначе нейтральная.
            # Активная иконка остаётся различимой даже при enabled=False.
            if is_active:
                btn.configure(
                    border_color="#1f538d",
                    border_width=2,
                )
            else:
                btn.configure(
                    border_color=("#c7c7c7", "#3a3a3a"),
                    border_width=2,
                )

    def _is_enabled(self, effect_id):
        if effect_id not in ENABLEABLE_IDS:
            return False
        return bool(getattr(self.settings, f"{effect_id}_enabled", False))