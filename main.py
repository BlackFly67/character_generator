#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Character Image Generator v5.7.0
Главная точка входа
"""

import sys
import os

# Добавляем текущую директорию в путь для импортов
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import customtkinter as ctk
from ui.main_window import MainWindow
from config import Settings
from i18n import I18n
from constants import APP_VERSION, DEFAULT_CONFIG


def main():
    """Главная функция запуска приложения."""
    # Настройка CustomTkinter
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Загрузка настроек
    settings = Settings()
    settings.load(DEFAULT_CONFIG)
    
    # Создание главного окна
    root = ctk.CTk()
    app = MainWindow(root, settings)
    
    # Запуск основного цикла
    root.mainloop()


if __name__ == "__main__":
    main()