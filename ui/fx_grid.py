# -*- coding: utf-8 -*-
"""
FX-сетка — поток иконок эффектов.

Иконки — буква «A» с эффектом, рендерятся на лету через
ui/effect_icon.py. Никаких подписей — название только в tooltip.

Клик — on_select(panel_id). Sidebar переключает активную панель.

Стилизация (см. ui/theme.py — единая палитра с остальным UI). Фон и
рамка — два НЕЗАВИСИМЫХ канала: фон сигналит "сейчас под курсором или
открыто", рамка сигналит "включено":
    - обычная        — фон idle, рамка _BORDER_IDLE 1px;
    - hover          — фон _COLOR_HOVER, рамка как была;
    - активная       — фон _COLOR_HOVER, рамка _BORDER_IDLE;
    - включённая     — фон idle, рамка _BORDER_ENABLED 1px;
    - актив+включена — фон _COLOR_HOVER, рамка _BORDER_ENABLED.

Раскладка: 5 равных колонок (grid weight=1, uniform), кнопки
растягиваются по ширине ячейки (sticky="ew") — правого отступа
не остаётся.

Реализация кнопки: CTkFrame-контейнер (умеет border_width/
border_color) с CTkLabel (картинка) внутри через place(). CTkLabel
не поддерживает border_width — потому рамка на контейнере, а не на
самой иконке.
"""

import customtkinter as ctk

from ui.icons import (
    RAIL_ICONS, FX_GROUPS, ENABLEABLE_IDS, get_icon,
)
from ui.theme import (
    BLOCK_ITEM_BG, HOVER_BG, ACCENT_BLUE_LIGHT, BORDER_IDLE,
    TILE_CORNER_RADIUS,
)


_COLOR_IDLE_BG = BLOCK_ITEM_BG
_COLOR_HOVER = HOVER_BG

_BORDER_IDLE = BORDER_IDLE
_BORDER_ENABLED = ACCENT_BLUE_LIGHT
_BORDER_WIDTH = 1

# Размеры
ICON_W = 52
ICON_H = 40
ICON_SIZE_PX = (32, 32)
MAX_COLS = 5


class FXGrid(ctk.CTkFrame):
    """Горизонтальная сетка иконок эффектов."""

    def __init__(self, parent, settings, i18n,
                 on_select, is_active_fn):
        super().__init__(parent, fg_color="transparent")

        self.settings = settings
        self.i18n = i18n
        self._on_select = on_select
        self._is_active_fn = is_active_fn

        self._buttons = {}       # panel_id -> CTkFrame (контейнер)
        self._icon_images = {}   # panel_id -> CTkImage

        self._build()

    # ============================================================
    #  Построение
    # ============================================================

    def _build(self):
        ctk.CTkLabel(
            self, text=self.i18n.tr("effects"),
            font=("Arial", 15, "bold"), anchor="w",
        ).pack(anchor="w", padx=8, pady=(6, 4))

        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="x", padx=8, pady=(2, 4))

        # 5 равных колонок: uniform-группа заставляет grid держать
        # ОДИНАКОВУЮ ширину для всех колонок (иначе колонка с более
        # широким контентом в какой-то строке была бы шире остальных),
        # weight=1 — растягивать их при увеличении окна, а не оставлять
        # лишнее место с одного края.
        for c in range(MAX_COLS):
            grid_frame.grid_columnconfigure(c, weight=1, uniform="fx_col")

        all_ids = []
        for _group_key, ids in FX_GROUPS:
            all_ids.extend(ids)

        for i, panel_id in enumerate(all_ids):
            r = i // MAX_COLS
            c = i % MAX_COLS
            self._add_icon_grid(grid_frame, panel_id, r, c)

    def _add_icon_grid(self, parent, panel_id, row, col):
        from ui.effect_icon import get_effect_icon
        from ui.tooltip import Tooltip

        tooltip_key = get_icon(panel_id)

        ctk_img = get_effect_icon(panel_id, size=ICON_SIZE_PX)

        frame = ctk.CTkFrame(
            parent,
            fg_color=_COLOR_IDLE_BG,
            corner_radius=TILE_CORNER_RADIUS,
            width=ICON_W, height=ICON_H,
            border_width=_BORDER_WIDTH,
            border_color=_BORDER_IDLE,
        )
        # sticky="ew": плитка растягивается на всю ширину своей ячейки
        # (все ячейки одинаковой ширины благодаря uniform-группе выше)
        # — без этого справа от последней колонки/между плитками
        # оставался неиспользуемый зазор.
        frame.grid(row=row, column=col, padx=2, pady=2, sticky="ew")
        frame.grid_propagate(False)
        frame.pack_propagate(False)

        lbl = ctk.CTkLabel(
            frame, text="",
            image=ctk_img, compound="center",
            fg_color="transparent",
        )
        lbl.place(relx=0.5, rely=0.5, anchor="center")

        for w in (frame, lbl):
            w.bind("<Button-1>", lambda e, pid=panel_id: self._click(pid))
            w.bind("<Enter>", lambda e, pid=panel_id: self._on_hover(pid, True))
            w.bind("<Leave>", lambda e, pid=panel_id: self._on_hover(pid, False))
            w.configure(cursor="hand2")

        self._icon_images[panel_id] = ctk_img
        self._buttons[panel_id] = frame
        Tooltip(frame, self.i18n.tr(tooltip_key))

        self._apply_button_color(panel_id)

    # ============================================================
    #  Hover / цвета
    # ============================================================

    def _on_hover(self, panel_id, entering):
        """
        Hover меняет ТОЛЬКО фон, никогда не трогает рамку — рамка
        целиком отражает "включено/не включено" и не должна мигать
        при простом наведении мыши (см. матрицу состояний в докстринге
        модуля: "hover — ... рамка как была").
        """
        frame = self._buttons.get(panel_id)
        if frame is None:
            return
        if entering:
            frame.configure(fg_color=_COLOR_HOVER)
        else:
            self._apply_button_color(panel_id)

    def _apply_button_color(self, panel_id):
        """
        Два независимых канала:
          - фон:  _COLOR_HOVER, если плитка активна (открыта справа) —
                  иначе _COLOR_IDLE_BG. Истинный hover мыши (см.
                  _on_hover выше) временно перекрывает этот фон тем же
                  _COLOR_HOVER и не проходит через эту функцию, пока
                  курсор не уйдёт.
          - рамка: цвет = _BORDER_ENABLED, если эффект включён в
                  settings, иначе нейтральный _BORDER_IDLE — ширина
                  всегда одна и та же (_BORDER_WIDTH), рамка не
                  используется для сигнала "активна".
        """
        frame = self._buttons.get(panel_id)
        if frame is None:
            return

        is_active = bool(self._is_active_fn(panel_id))
        is_enabled = (
            panel_id in ENABLEABLE_IDS
            and bool(getattr(self.settings, f"{panel_id}_enabled", False))
        )

        bg = _COLOR_HOVER if is_active else _COLOR_IDLE_BG
        border_color = _BORDER_ENABLED if is_enabled else _BORDER_IDLE

        frame.configure(
            fg_color=bg,
            border_width=_BORDER_WIDTH,
            border_color=border_color,
        )

    # ============================================================
    #  Callbacks
    # ============================================================

    def _click(self, panel_id):
        if callable(self._on_select):
            self._on_select(panel_id)

    # ============================================================
    #  Публичный API
    # ============================================================

    def refresh(self):
        for panel_id in self._buttons:
            self._apply_button_color(panel_id)

    def refresh_labels(self):
        for w in self.winfo_children():
            w.destroy()
        self._buttons = {}
        self._icon_images = {}
        self._build()
        self.refresh()