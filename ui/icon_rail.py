# -*- coding: utf-8 -*-
"""
Левая колонка с иконками эффектов.

Структура:
  [Base]       Aa ◨                ← закреплено, не сворачивается
  [Fill]       ■ ▤ ▦ ⁙             ← сворачиваемая группа
  [Inner]      ◉ ✦ ◐ ⬓
  ...
  ------------
  [↺] [🎨] [📌]

Два визуальных слоя:
  - обводка иконки    = активный таб (только один)
  - маленькая точка  = enabled=True (у эффектов с флагом)

Сворачивание: клик по заголовку группы (разделитель) сворачивает
её в одну строку с названием. Заголовок группы — тонкая полоса
с иконкой-шевроном.

Rail НЕ знает про SettingsPanel. Callback on_select(effect_id)
сообщает, что пользователь выбрал эффект. on_reset / on_presets /
on_unpin_all — нижние кнопки.
"""

import customtkinter as ctk

from ui.icons import RAIL_ICONS, RAIL_GROUPS, ENABLEABLE_IDS, get_icon
from ui.tooltip import Tooltip


RAIL_WIDTH = 68
ICON_BTN_SIZE = 40
ICON_FONT_SIZE = 16
GROUP_HEADER_HEIGHT = 20


# Человекочитаемые названия групп для заголовков (i18n-ключи).
GROUP_LABELS = {
    "base": "base",
    "fill": "fill_group",
    "inner": "inner_group",
    "outer": "outer_group",
    "geometry": "geometry_group",
    "post": "post_group",
    "extra": "extra_group",
}


class IconRail(ctk.CTkFrame):
    def __init__(self, parent, settings, i18n,
                 on_select=None, on_reset=None, on_presets=None,
                 on_unpin_all=None):
        super().__init__(parent, width=RAIL_WIDTH, corner_radius=0)
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.settings = settings
        self.i18n = i18n
        self.on_select = on_select
        self.on_reset = on_reset
        self.on_presets = on_presets
        self.on_unpin_all = on_unpin_all

        self.current_effect_id = None
        self._buttons = {}          # effect_id -> CTkButton
        self._tooltips = {}         # effect_id -> Tooltip
        self._indicators = {}       # effect_id -> CTkFrame (точка enabled)
        self._group_frames = {}     # group_id -> frame (для сворачивания)
        self._group_collapsed = {}  # group_id -> bool
        self._group_headers = {}    # group_id -> button-заголовок

        self._build()

    # ============================================================
    #  Построение
    # ============================================================

    def _build(self):
        # Верхний фиксированный блок: base (не скроллится).
        self._top_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._top_frame.pack(side="top", fill="x", padx=2, pady=(6, 4))
        self._build_group(self._top_frame, "base", collapsible=False)

        # Скроллируемая область для остальных групп.
        self.scroll = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
            scrollbar_button_color=("#c0c0c0", "#3a3a3a"),
            scrollbar_button_hover_color=("#a0a0a0", "#505050"),
        )
        self.scroll.pack(fill="both", expand=True, padx=2, pady=(0, 4))
        self.scroll._scrollbar.configure(width=6)

        for group_id, ids in RAIL_GROUPS:
            if group_id == "base":
                continue
            self._build_group(self.scroll, group_id, collapsible=True)

        # Нижний блок: reset / presets / unpin
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

        unpin_btn = ctk.CTkButton(
            bottom, text="📌", width=ICON_BTN_SIZE, height=ICON_BTN_SIZE,
            font=("Segoe UI Symbol", ICON_FONT_SIZE),
            fg_color="transparent",
            hover_color=("#c7c7c7", "#3a3a3a"),
            text_color=("#1a1a1a", "#e0e0e0"),
            border_width=0,
            command=self._handle_unpin_all,
        )
        unpin_btn.pack(pady=2)
        Tooltip(unpin_btn, self.i18n.tr("unpin_all"))

    def _build_group(self, parent, group_id, collapsible):
        """Строит группу: заголовок + контейнер с иконками."""
        ids = dict(RAIL_GROUPS)[group_id]

        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="x")

        icons_frame = ctk.CTkFrame(container, fg_color="transparent")
        icons_frame.pack(fill="x")
        self._group_frames[group_id] = icons_frame

        if collapsible:
            header = ctk.CTkButton(
                container,
                text=self._group_header_text(group_id, collapsed=False),
                height=GROUP_HEADER_HEIGHT,
                font=("Arial", 9, "bold"),
                fg_color="transparent",
                hover_color=("#c7c7c7", "#3a3a3a"),
                text_color=("#7a7a7a", "#a0a0a0"),
                anchor="w",
                command=lambda g=group_id: self._toggle_group(g),
            )
            header.pack(fill="x", padx=4, pady=(6, 0), before=icons_frame)
            self._group_headers[group_id] = header
            self._group_collapsed[group_id] = False

        for effect_id in ids:
            self._add_icon_button(icons_frame, effect_id)

    def _group_header_text(self, group_id, collapsed):
        arrow = "▶" if collapsed else "▼"
        label = self.i18n.tr(GROUP_LABELS.get(group_id, group_id))
        return f"{arrow}  {label}"

    def _toggle_group(self, group_id):
        collapsed = not self._group_collapsed.get(group_id, False)
        self._group_collapsed[group_id] = collapsed
        frame = self._group_frames.get(group_id)
        if frame is not None:
            if collapsed:
                frame.pack_forget()
            else:
                # Возвращаем на прежнее место — после header, до следующей группы.
                frame.pack(fill="x", after=self._group_headers[group_id])
        header = self._group_headers.get(group_id)
        if header is not None:
            header.configure(text=self._group_header_text(group_id, collapsed))

    def _add_icon_button(self, parent, effect_id):
        symbol, label_key = get_icon(effect_id)
        label = self.i18n.tr(label_key)

        # Кнопка-контейнер: снаружи кнопка, внутри — иконка + точка enabled.
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(pady=3, padx=4, fill="x")

        btn = ctk.CTkButton(
            wrap, text=symbol,
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
        btn.pack()

        self._buttons[effect_id] = btn
        self._tooltips[effect_id] = Tooltip(btn, label)

        # Точка enabled — отдельный маленький индикатор в правом верхнем
        # углу кнопки, видимый поверх неё. Реализуем через CTkFrame
        # в wrap, абсолютно позиционированный через .place().
        dot = ctk.CTkFrame(
            wrap, width=6, height=6, corner_radius=3,
            fg_color="transparent", border_width=0,
        )
        dot.place(relx=1.0, rely=0.0, x=-6, y=6, anchor="ne")
        # dot невидим, пока enabled=False (fg_color="transparent").
        self._indicators[effect_id] = dot

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

    def _handle_unpin_all(self):
        if callable(self.on_unpin_all):
            self.on_unpin_all()

    # ============================================================
    #  Публичный API
    # ============================================================

    def set_active(self, effect_id):
        """Подсветить активный таб (обводка)."""
        self.current_effect_id = effect_id
        self._refresh_highlights()

    def set_pinned(self, pinned_ids):
        """
        Сообщить rail, какие эффекты сейчас пинуты. Пинутые получают
        приглушённую рамку другого оттенка (например, зелёной).
        """
        self._pinned_ids = set(pinned_ids or [])
        self._refresh_highlights()

    def refresh_enabled_highlights(self):
        """Пересчитать enabled-индикацию (точки)."""
        self._refresh_highlights()

    def refresh_labels(self):
        """Обновить tooltips и заголовки групп (при смене языка)."""
        for effect_id, tip in self._tooltips.items():
            _, label_key = get_icon(effect_id)
            tip.set_text(self.i18n.tr(label_key))
        for group_id, header in self._group_headers.items():
            collapsed = self._group_collapsed.get(group_id, False)
            header.configure(text=self._group_header_text(group_id, collapsed))

    # ============================================================
    #  Внутреннее
    # ============================================================

    def _refresh_highlights(self):
        pinned = getattr(self, "_pinned_ids", set())
        for effect_id, btn in self._buttons.items():
            enabled = self._is_enabled(effect_id)
            is_active = (effect_id == self.current_effect_id)
            is_pinned = effect_id in pinned

            # Текст/фон кнопки — НЕ зависят от enabled (это навигация,
            # не состояние). Enabled показывает точка.
            if is_active:
                btn.configure(
                    text_color=("#1a1a1a", "#ffffff"),
                    fg_color=("#e8e8e8", "#2a2a2a"),
                )
            else:
                btn.configure(
                    text_color=("#4a4a4a", "#c0c0c0"),
                    fg_color="transparent",
                )

            # Рамка: активная — акцент; пинутая — зелёная; иначе нейтральная.
            if is_active:
                btn.configure(border_color="#1f538d", border_width=2)
            elif is_pinned:
                btn.configure(border_color=("#2e8b57", "#3cb371"), border_width=2)
            else:
                btn.configure(border_color=("#c7c7c7", "#3a3a3a"), border_width=2)

            # Точка enabled.
            dot = self._indicators.get(effect_id)
            if dot is not None:
                if enabled:
                    dot.configure(fg_color=("#1f538d", "#4a9eff"))
                else:
                    dot.configure(fg_color="transparent")

    def _is_enabled(self, effect_id):
        if effect_id not in ENABLEABLE_IDS:
            return False
        return bool(getattr(self.settings, f"{effect_id}_enabled", False))