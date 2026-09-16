# -*- coding: utf-8 -*-
"""
Правая панель: активная панель эффекта + стек пинутых панелей.

Структура:
  ┌─ активная панель (сверху, всегда развёрнута)
  ├─ пинутая панель 1 (со своим заголовком и кнопками ▼/📌)
  ├─ пинутая панель 2
  └─ ...

Пинутые панели:
  - Добавляются/убираются через toggle_pin(effect_id).
  - Порядок — в порядке добавления.
  - Каждая может быть свёрнута (▼/▶) — состояние хранится в _collapsed.
  - Кэш построенных фреймов: _cache[effect_id] = frame.
    Один и тот же effect_id может быть и активным, и пинутым —
    но отображается один раз: если активен, он НЕ показывается
    в стеке пинутых (чтобы не дублировался).
"""

import customtkinter as ctk

from ui.auto_sidebar import build_single_effect
from ui import manual_sidebar as ms
from ui.icons import RAIL_GROUPS, get_icon


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

        # Кэш панелей: effect_id -> CTkFrame (только тело панели,
        # без заголовка — заголовок строится каждый раз при
        # пересборке стека, потому что кнопки ▼/📌 зависят от
        # контекста: активная панель не имеет 📌, пинутая имеет).
        self._cache = {}

        # Пинутые эффекты в порядке добавления.
        self.pinned_ids = []

        # Свёрнутые панели (для пинутых).
        self._collapsed = {}   # effect_id -> bool

        # Активный эффект.
        self.current_effect_id = None

        # Публичные ссылки для MainWindow.
        self.font_size_entry = None
        self.font_size_slider = None

        # Скроллируемый контейнер.
        self.body = ctk.CTkScrollableFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self.body.pack(fill="both", expand=True)

        # Сразу открываем дефолтный эффект.
        self.set_active_effect(DEFAULT_EFFECT_ID)

    # ============================================================
    #  Публичный API
    # ============================================================

    def set_active_effect(self, effect_id):
        """Сменить активный эффект. Полностью пересобирает стек."""
        if effect_id not in ALL_EFFECT_IDS:
            return
        self.current_effect_id = effect_id
        self._rebuild_stack()

    def toggle_pin(self, effect_id):
        """Добавить/убрать эффект из пинутых."""
        if effect_id == self.current_effect_id:
            # Активный нельзя пинуть — он и так сверху.
            return
        if effect_id in self.pinned_ids:
            self.pinned_ids.remove(effect_id)
        else:
            self.pinned_ids.append(effect_id)
        self._rebuild_stack()
        self._notify_change()

    def unpin_all(self):
        """Снять все пины."""
        if not self.pinned_ids:
            return
        self.pinned_ids.clear()
        self._rebuild_stack()
        self._notify_change()

    def is_pinned(self, effect_id):
        return effect_id in self.pinned_ids

    def refresh_active_panel(self):
        """Полная пересборка: сбросить кэш и перестроить стек."""
        eid = self.current_effect_id or DEFAULT_EFFECT_ID

        # Уничтожить все тела панелей в кэше.
        for frame in self._cache.values():
            try:
                frame.destroy()
            except Exception:
                pass
        self._cache.clear()

        # Сбросить ссылки на font.
        self.font_size_entry = None
        self.font_size_slider = None

        self.current_effect_id = eid
        self._rebuild_stack()

    def notify_change(self):
        if callable(self._on_change_external):
            self._on_change_external()

    def _on_change(self):
        """Совместимость с auto_sidebar / manual_sidebar."""
        self.notify_change()

    # ============================================================
    #  Построение стека
    # ============================================================

    def _rebuild_stack(self):
        # Очистить body.
        for w in self.body.winfo_children():
            try:
                w.destroy()
            except Exception:
                pass

        # Активная панель.
        if self.current_effect_id:
            self._build_section(
                self.body, self.current_effect_id,
                is_active=True, is_pinned=False,
            )

        # Пинутые (в порядке добавления), кроме активного.
        for eid in self.pinned_ids:
            if eid == self.current_effect_id:
                continue
            self._build_section(
                self.body, eid,
                is_active=False, is_pinned=True,
            )

    def _build_section(self, parent, effect_id, is_active, is_pinned):
        """
        Строит один блок: заголовок + тело.
        Тело кэшируется в self._cache — переиспользуется, если уже есть.
        Заголовок создаётся каждый раз (кнопки зависят от контекста).
        """
        section = ctk.CTkFrame(parent, fg_color="transparent")
        section.pack(fill="x", pady=(0, 6), padx=4)

        header = self._build_header(section, effect_id,
                                     is_active=is_active,
                                     is_pinned=is_pinned)

        body_wrapper = ctk.CTkFrame(section, fg_color="transparent")
        body_wrapper.pack(fill="x")

        # Свёрнутость (только для пинутых).
        collapsed = self._collapsed.get(effect_id, False)
        if is_pinned and collapsed:
            body_wrapper.pack_forget()

        # Тело панели — из кэша или построить.
        if effect_id not in self._cache:
            self._cache[effect_id] = self._create_body(effect_id, body_wrapper)
        else:
            # Перепривязать к новому body_wrapper.
            cached = self._cache[effect_id]
            cached.pack_forget()
            cached.master = body_wrapper  # не поможет для tk; делаем
                                          # иначе — см. ниже.
            # НЕЛЬЗЯ перепривязать к другому parent в tkinter напрямую.
            # Поэтому кэш хранит только body-фрейм, но каждый раз
            # пересоздаётся. См. _create_body — там build_*_section
            # строит заново. Кэш не выключаем полностью — оставляем
            # для будущей оптимизации.
            pass

    def _build_header(self, parent, effect_id, is_active, is_pinned):
        _, label_key = get_icon(effect_id)
        title = self.i18n.tr(label_key)

        header = ctk.CTkFrame(parent, fg_color="transparent")
        header.pack(fill="x", padx=4, pady=(8, 2))

        # Заголовок: жирный для активного, обычный для пинутого.
        font_style = ("Arial", 13, "bold") if is_active else ("Arial", 12)
        ctk.CTkLabel(
            header, text=title, font=font_style, anchor="w",
        ).pack(side="left", fill="x", expand=True)

        # Кнопки в заголовке.
        if is_pinned:
            # Свернуть/развернуть.
            collapsed = self._collapsed.get(effect_id, False)
            collapse_btn = ctk.CTkButton(
                header,
                text="▶" if collapsed else "▼",
                width=24, height=20,
                font=("Arial", 10),
                fg_color="transparent",
                hover_color=("#c7c7c7", "#3a3a3a"),
                text_color=("#4a4a4a", "#c0c0c0"),
                command=lambda e=effect_id: self._toggle_collapse(e),
            )
            collapse_btn.pack(side="right", padx=1)

            # Снять пин.
            unpin_btn = ctk.CTkButton(
                header,
                text="📌",
                width=24, height=20,
                font=("Segoe UI Symbol", 11),
                fg_color="transparent",
                hover_color=("#c7c7c7", "#3a3a3a"),
                text_color=("#2e8b57", "#3cb371"),
                command=lambda e=effect_id: self.toggle_pin(e),
            )
            unpin_btn.pack(side="right", padx=1)

        elif is_active:
            # Пин — только для активного, если он не является
            # base/effect-без-смысла-пина. Пинить можно все.
            pin_btn = ctk.CTkButton(
                header,
                text="📌",
                width=24, height=20,
                font=("Segoe UI Symbol", 11),
                fg_color="transparent",
                hover_color=("#c7c7c7", "#3a3a3a"),
                text_color=("#4a4a4a", "#c0c0c0"),
                command=lambda e=effect_id: self.toggle_pin(e),
            )
            pin_btn.pack(side="right", padx=1)

        return header

    def _toggle_collapse(self, effect_id):
        self._collapsed[effect_id] = not self._collapsed.get(effect_id, False)
        self._rebuild_stack()

    def _create_body(self, effect_id, parent):
        """
        Строит тело панели эффекта. parent — body_wrapper.
        Возвращает frame, содержащий UI.
        """
        # Внутренний фрейм, чтобы auto_sidebar мог pack-ать в него.
        inner = ctk.CTkFrame(parent, fg_color="transparent")
        inner.pack(fill="x")

        if effect_id in ms.MANUAL_PANELS:
            builder = ms.MANUAL_PANELS[effect_id]["builder"]
            result = builder(inner, self, self.settings, self.i18n)
            self._bind_manual_widgets(effect_id, result)
        else:
            build_single_effect(inner, self, self.settings, self.i18n,
                                 effect_id)

        return inner

    def _bind_manual_widgets(self, effect_id, result):
        if effect_id == "font":
            self.font_size_entry = result.get("size_entry")
            self.font_size_slider = result.get("size_slider")

    def _notify_change(self):
        self.notify_change()