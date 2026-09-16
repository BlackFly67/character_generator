# -*- coding: utf-8 -*-
"""
Правая панель: настройки ОДНОГО активного эффекта.

Архитектура:
  - SettingsPanel знает про settings, i18n, main_window.
  - Хранит current_effect_id и кэш построенных панелей
    (dict[effect_id → CTkFrame]).
  - set_active_effect(effect_id) — переключает видимую панель.
  - Первое построение панели — ленивое (при первом обращении).
  - После reset / presets / смены языка — кэш сбрасывается,
    текущая активная панель пересоздаётся.

Панель может содержать:
  - эффект из PIPELINE / POST_COMPOSE_EFFECTS (через
    auto_sidebar.build_single_effect) — если id в списке,
  - ручную секцию (font, style_text, rotation, arc, opacity,
    background) — через manual_sidebar.MANUAL_PANELS.
"""

import customtkinter as ctk

from ui.auto_sidebar import build_single_effect
from ui import manual_sidebar as ms
from ui.icons import RAIL_GROUPS


# Плоский список id в порядке групп — для fallback и для проверки.
ALL_EFFECT_IDS = [eid for _, ids in RAIL_GROUPS for eid in ids]

DEFAULT_EFFECT_ID = "gradient"


class SettingsPanel(ctk.CTkFrame):
    def __init__(self, parent, settings, i18n, main_window,
                 on_change=None):
        super().__init__(parent, width=340, corner_radius=0)
        self.pack_propagate(False)
        self.grid_propagate(False)

        self.settings = settings
        self.i18n = i18n
        self.main_window = main_window
        self._on_change_external = on_change

        # Кэш: effect_id -> frame
        self._cache = {}

        # Текущая активная панель
        self.current_effect_id = None
        self._current_frame = None

        # Контейнер, куда панели pack'аются
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True)

        # Публичные ссылки на виджеты, которые читает MainWindow.
        # Заполняются при построении панели "font".
        self.font_size_entry = None
        self.font_size_slider = None

        # Сразу открываем дефолтный эффект — чтобы панель не была пустой.
        self.set_active_effect(DEFAULT_EFFECT_ID)

    # ============================================================
    #  Публичный API
    # ============================================================

    def set_active_effect(self, effect_id):
        """
        Переключает активную панель. Если панели ещё нет в кэше —
        строит её. Скрывает предыдущую.
        """
        if effect_id not in ALL_EFFECT_IDS:
            # Fallback: неизвестный id — ничего не делаем.
            return

        # Скрыть предыдущую
        if self._current_frame is not None:
            try:
                self._current_frame.pack_forget()
            except Exception:
                pass

        # Построить/достать из кэша
        if effect_id not in self._cache:
            frame = self._build_panel(effect_id)
            self._cache[effect_id] = frame

        self._current_frame = self._cache[effect_id]
        self._current_frame.pack(fill="both", expand=True)
        self.current_effect_id = effect_id

    def refresh_active_panel(self):
        """
        Пересоздать текущую активную панель (после reset, presets,
        смены языка). Кэш целиком сбрасывается, кроме активной —
        её пересоздаём.
        """
        eid = self.current_effect_id or DEFAULT_EFFECT_ID

        # Уничтожить все панели в кэше
        for frame in self._cache.values():
            try:
                frame.destroy()
            except Exception:
                pass
        self._cache.clear()
        self._current_frame = None

        # Сбросить ссылки на font (могли устареть)
        self.font_size_entry = None
        self.font_size_slider = None

        # Построить активную заново
        self.set_active_effect(eid)

    def notify_change(self):
        """
        Вызывается из панелей (через sidebar-параметр) при
        изменении settings. Пробрасывает наружу.
        """
        if callable(self._on_change_external):
            self._on_change_external()

    def _on_change(self):
        """
        Совместимость с auto_sidebar и manual_sidebar — они вызывают
        sidebar._on_change() при изменениях в контролах.
        В старой архитектуре Sidebar._on_change() вызывал все
        зарегистрированные callbacks; теперь callback один.
        """
        self.notify_change()

    # ============================================================
    #  Построение одной панели
    # ============================================================

    def _build_panel(self, effect_id):
        """
        Создаёт фрейм-обёртку с одной панелью эффекта.
        Внутри — либо auto_single_effect, либо manual-секция.
        """
        wrapper = ctk.CTkScrollableFrame(
            self.body, fg_color="transparent", corner_radius=0,
        )

        # Заголовок секции — чтобы было понятно, где находимся
        self._build_header(wrapper, effect_id)

        # Ручные секции — через MANUAL_PANELS
        if effect_id in ms.MANUAL_PANELS:
            builder = ms.MANUAL_PANELS[effect_id]["builder"]
            result = builder(wrapper, self, self.settings, self.i18n)
            self._bind_manual_widgets(effect_id, result)
            return wrapper

        # Иначе — эффект из PIPELINE / POST_COMPOSE_EFFECTS
        build_single_effect(wrapper, self, self.settings, self.i18n,
                            effect_id)
        return wrapper

    def _build_header(self, parent, effect_id):
        """Заголовок панели: название эффекта + отступ."""
        from ui.icons import get_icon
        _, label_key = get_icon(effect_id)

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(
            header, text=self.i18n.tr(label_key),
            font=("Arial", 14, "bold"),
            anchor="w",
        ).pack(side="left")

    def _bind_manual_widgets(self, effect_id, result):
        """
        Сохраняет публичные ссылки на виджеты ручных секций, чтобы
        MainWindow мог их читать (например, font_size_entry).
        """
        if effect_id == "font":
            self.font_size_entry = result.get("size_entry")
            self.font_size_slider = result.get("size_slider")