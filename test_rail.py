# -*- coding: utf-8 -*-
"""Временный тест rail. Удалить после проверки."""
import customtkinter as ctk
from config import Settings
from i18n import I18n
from ui.icon_rail import IconRail


def main():
    root = ctk.CTk()
    root.geometry("120x750")
    root.title("Rail test")

    settings = Settings()
    settings.load()
    i18n = I18n(settings.language)

    def on_select(effect_id):
        print(f"clicked: {effect_id}")
        rail.set_active(effect_id)

    def on_reset():
        print("reset")

    def on_presets():
        print("presets")

    rail = IconRail(root, settings, i18n,
                    on_select=on_select,
                    on_reset=on_reset,
                    on_presets=on_presets)
    rail.pack(fill="both", expand=True)

    # Для теста подсветки — включим несколько эффектов
    settings.gradient_enabled = True
    settings.outline_inner_enabled = True
    settings.glitch_enabled = True
    rail.refresh_enabled_highlights()
    rail.set_active("gradient")

    root.mainloop()


if __name__ == "__main__":
    main()