# -*- coding: utf-8 -*-
"""
FX-сетка — поток иконок эффектов.

Иконки эффектов живут внутри правой колонки настроек (Sidebar),
между блоком Base-секций (Font / Style / Rotation / Arc / Opacity /
Background) и активной панелью выбранного эффекта.

    FX
    ▤ ▦ ◉ ✦ ⬓ ◐
    ◎ ✧ ⬒ ☁ ⟋ ⬔
    ⤓ ⁙ ⚡

Никаких групп, разделителей и заголовков — просто все иконки
подряд, с переносом по 6 в ряд. Название эффекта — tooltip.

Клик по иконке — on_select(panel_id). Sidebar переключает активную
панель эффекта.

Стилизация иконок:
    - серый   — panel_id не активен и не включён;
    - зелёный — settings.<id>_enabled == True (только для ENABLEABLE_IDS);
    - синий   — panel_id == current_active_id (открыт в правой панели).

Приоритет: активен → синий; включён → зелёный; иначе → серый.
"""

import customtkinter as ctk

from ui.icons import (
    RAIL_ICONS, FX_GROUPS, ENABLEABLE_IDS, get_icon,
)


# Цвета иконок
_COLOR_ACTIVE_BG = "#1f538d"            # синий — активная панель
_COLOR_ACTIVE_FG = "#ffffff"

_COLOR_ENABLED_BG = ("#8fd19e", "#1e5631")   # зелёный — enabled
_COLOR_ENABLED_FG = ("#0a2a12", "#eaffef")

_COLOR_IDLE_BG = ("#e0e0e0", "#2b2b2b")      # серый — обычный
_COLOR_IDLE_FG = ("#1a1a1a", "#d0d0d0")

# Размер иконки
ICON_W = 40
ICON_H = 32
ICON_FONT_SIZE = 14
MAX_COLS = 5


class FXGrid(ctk.CTkFrame):
    """
    Горизонтальная сетка иконок эффектов. Все иконки — в одном
    потоке, перенос по MAX_COLS в ряд. Без разделителей и групп.

    Публичный API:
        - __init__(parent, settings, i18n, on_select, is_active_fn)
        - refresh() — пересчитать цвета после изменения settings
          или смены активной панели.
        - refresh_labels() — пересобрать при смене языка.
    """

    def __init__(self, parent, settings, i18n,
                 on_select, is_active_fn):
        super().__init__(parent, fg_color="transparent")

        self.settings = settings
        self.i18n = i18n
        self._on_select = on_select
        self._is_active_fn = is_active_fn

        # panel_id -> CTkButton
        self._buttons = {}

        self._build()

    # ============================================================
    #  Построение
    # ============================================================

    def _build(self):
        # Заголовок "FX" сверху.
        ctk.CTkLabel(
            self, text=self.i18n.tr("effects"),
            font=("Arial", 15, "bold"), anchor="w",
        ).pack(anchor="w", padx=8, pady=(6, 4))

        # Контейнер под иконки — grid, чтобы перенос был надёжным
        # (pack плохо переносит строки внутри разных групп).
        grid_frame = ctk.CTkFrame(self, fg_color="transparent")
        grid_frame.pack(fill="x", padx=8, pady=(2, 4))

        # Собираем все id эффектов из FX_GROUPS в один плоский список.
        # Группировка в icons.py остаётся (для порядка), но визуально
        # на экране группы не разделяются — общий поток.
        all_ids = []
        for _group_key, ids in FX_GROUPS:
            all_ids.extend(ids)

        for i, panel_id in enumerate(all_ids):
            r = i // MAX_COLS
            c = i % MAX_COLS
            self._add_icon_grid(grid_frame, panel_id, r, c)

    def _add_icon_grid(self, parent, panel_id, row, col):
        symbol, tooltip_key = get_icon(panel_id)

        btn = ctk.CTkButton(
            parent, text=symbol,
            width=ICON_W, height=ICON_H,
            font=("Segoe UI Symbol", ICON_FONT_SIZE),
            fg_color=_COLOR_IDLE_BG,
            text_color=_COLOR_IDLE_FG,
            hover_color=("#c7c7c7", "#3a3a3a"),
            corner_radius=4,
            command=lambda pid=panel_id: self._click(pid),
        )
        btn.grid(row=row, column=col, padx=2, pady=2, sticky="w")
        self._buttons[panel_id] = btn

        self._attach_tooltip(btn, self.i18n.tr(tooltip_key))

    def _attach_tooltip(self, widget, text):
        """
        Минималистичный tooltip: показываем через 400 мс после Enter,
        скрываем на Leave. Использует CTkToplevel с overrideredirect.
        """
        state = {"after_id": None, "tip": None}

        def on_enter(event):
            on_leave(event)
            state["after_id"] = widget.after(400, show)

        def on_leave(event):
            if state["after_id"] is not None:
                try:
                    widget.after_cancel(state["after_id"])
                except Exception:
                    pass
                state["after_id"] = None
            if state["tip"] is not None:
                try:
                    state["tip"].destroy()
                except Exception:
                    pass
                state["tip"] = None

        def show():
            state["after_id"] = None
            try:
                x = widget.winfo_rootx() + widget.winfo_width() + 6
                y = widget.winfo_rooty() + 4
            except Exception:
                return
            tw = ctk.CTkToplevel()
            tw.overrideredirect(True)
            tw.geometry(f"+{x}+{y}")
            tw.attributes("-topmost", True)
            frame = ctk.CTkFrame(
                tw, fg_color=("#ffffff", "#2b2b2b"),
                corner_radius=4, border_width=1,
                border_color=("#c0c0c0", "#555555"),
            )
            frame.pack()
            ctk.CTkLabel(
                frame, text=text, font=("Arial", 11),
                text_color=("#1a1a1a", "#e0e0e0"),
            ).pack(padx=8, pady=4)
            state["tip"] = tw

        widget.bind("<Enter>", on_enter, add="+")
        widget.bind("<Leave>", on_leave, add="+")
        widget.bind("<ButtonPress>", on_leave, add="+")

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
        """
        Пересчитать цвета всех иконок по текущему состоянию settings
        и по активной панели (спрашивает у is_active_fn).
        """
        for panel_id, btn in self._buttons.items():
            is_active = bool(self._is_active_fn(panel_id))
            is_enabled = (
                panel_id in ENABLEABLE_IDS
                and bool(getattr(self.settings, f"{panel_id}_enabled", False))
            )

            if is_active:
                btn.configure(
                    fg_color=_COLOR_ACTIVE_BG,
                    text_color=_COLOR_ACTIVE_FG,
                )
            elif is_enabled:
                btn.configure(
                    fg_color=_COLOR_ENABLED_BG,
                    text_color=_COLOR_ENABLED_FG,
                )
            else:
                btn.configure(
                    fg_color=_COLOR_IDLE_BG,
                    text_color=_COLOR_IDLE_FG,
                )

    def refresh_labels(self):
        """
        Пересобрать tooltip-тексты при смене языка. Проще всего
        пересоздать FXGrid целиком — вызывается редко.
        """
        for w in self.winfo_children():
            w.destroy()
        self._buttons = {}
        self._build()
        self.refresh()