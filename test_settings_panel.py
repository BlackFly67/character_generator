# -*- coding: utf-8 -*-
"""Временный тест SettingsPanel. Удалить после проверки."""
import customtkinter as ctk
from config import Settings
from i18n import I18n
from ui.settings_panel import SettingsPanel


def main():
    root = ctk.CTk()
    root.geometry("400x750")
    root.title("Settings panel test")

    settings = Settings()
    settings.load()
    i18n = I18n(settings.language)

    def on_change():
        print(f"changed; active={panel.current_effect_id}")

    panel = SettingsPanel(root, settings, i18n,
                          main_window=None,
                          on_change=on_change)
    panel.pack(fill="both", expand=True)

    # Кнопки для переключения панелей (симуляция клика по rail)
    switcher = ctk.CTkFrame(root, fg_color="transparent")
    switcher.pack(side="bottom", fill="x")

    for eid in ["font", "gradient", "outline_inner", "glitch",
                "shadow", "rotation", "background"]:
        ctk.CTkButton(
            switcher, text=eid, width=80,
            command=lambda e=eid: panel.set_active_effect(e),
        ).pack(side="left", padx=2, pady=4)

    root.mainloop()


if __name__ == "__main__":
    main()