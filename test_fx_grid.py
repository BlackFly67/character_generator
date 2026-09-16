# -*- coding: utf-8 -*-
"""Временный тест FXGrid. Удалить после проверки."""
import customtkinter as ctk
from config import Settings
from i18n import I18n
from ui.fx_grid import FXGrid


def main():
    root = ctk.CTk()
    root.geometry("500x500")
    root.title("FXGrid test")

    settings = Settings()
    settings.load()
    i18n = I18n(settings.language)

    active = {"id": "gradient"}

    def is_active(panel_id):
        return panel_id == active["id"]

    def on_select(panel_id):
        active["id"] = panel_id
        print(f"selected: {panel_id}")
        grid.refresh()

    grid = FXGrid(root, settings, i18n,
                  on_select=on_select,
                  is_active_fn=is_active)
    grid.pack(fill="both", expand=True, padx=10, pady=10)

    # Включим пару эффектов для теста подсветки
    settings.gradient_enabled = True
    settings.outline_inner_enabled = True
    settings.glitch_enabled = True
    grid.refresh()

    root.mainloop()


if __name__ == "__main__":
    main()