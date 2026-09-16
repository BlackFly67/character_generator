# -*- coding: utf-8 -*-
"""
Минималистичные всплывающие подсказки для CustomTkinter.

Нативный Tkinter tooltip не поддерживает тёмную тему и CTk-стиль,
поэтому рисуем свой через CTkToplevel с overrideredirect(True).

FIX (зависание на Windows):
  - окно подсказки создаётся с overrideredirect(True) и
    attributes("-disabled", True) — тогда оно НЕ перехватывает
    фокус и не блокирует клики/ввод под ним. Без -disabled
    CTkToplevel "залипает" поверх мыши, <Leave> на исходный
    виджет не приходит, и подсказка не закрывается.
  - при закрытии виджета/окна отписываемся от таймера через
    <Destroy> — иначе pending-after дёргается на уничтоженном
    widget и вешает mainloop.
"""

import customtkinter as ctk


class Tooltip:
    """
    Показывает текст рядом с виджетом через delay_ms после Enter.
    Скрывается при Leave, клике или уничтожении виджета.
    """

    def __init__(self, widget, text, delay_ms=400):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after_id = None
        self._tip_window = None

        widget.bind("<Enter>", self._on_enter, add="+")
        widget.bind("<Leave>", self._on_leave, add="+")
        widget.bind("<ButtonPress>", self._on_leave, add="+")
        # FIX: если виджет уничтожен (закрытие окна, смена языка,
        # reset), отписываемся — иначе pending-after "висит" и
        # может дёрнуться уже на несуществующем widget.
        widget.bind("<Destroy>", self._on_destroy, add="+")

    def set_text(self, text):
        self.text = text

    # ------------------------------------------------------------

    def _on_enter(self, event=None):
        self._cancel()
        try:
            if not self.widget.winfo_exists():
                return
        except Exception:
            return
        self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _on_destroy(self, event=None):
        # Виджет уничтожен — снимаем таймер и убираем подсказку.
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    # ------------------------------------------------------------

    def _show(self):
        if self._tip_window is not None:
            return

        # Проверить, что виджет ещё жив (защита от pending-after).
        try:
            if not self.widget.winfo_exists():
                return
            x = self.widget.winfo_rootx() + self.widget.winfo_width() + 6
            y = self.widget.winfo_rooty() + 4
        except Exception:
            return

        tw = ctk.CTkToplevel(self.widget)
        tw.overrideredirect(True)
        tw.geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)

        # FIX (главное): окно не должно перехватывать фокус/ввод.
        # На Windows -disabled заставляет окно игнорировать клики
        # и не забирать фокус — иначе <Leave> на исходный виджет
        # не приходит, и подсказка "залипает".
        try:
            tw.attributes("-disabled", True)
        except Exception:
            pass

        # Скрыть окно до готовности контента — иначе на долю
        # секунды видно пустую рамку и мигание.
        tw.withdraw()

        frame = ctk.CTkFrame(
            tw,
            fg_color=("#ffffff", "#2b2b2b"),
            corner_radius=4,
            border_width=1,
            border_color=("#c0c0c0", "#555555"),
        )
        frame.pack()
        ctk.CTkLabel(
            frame, text=self.text,
            font=("Arial", 11),
            text_color=("#1a1a1a", "#e0e0e0"),
        ).pack(padx=8, pady=4)

        tw.deiconify()
        self._tip_window = tw

    def _hide(self):
        if self._tip_window is not None:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None