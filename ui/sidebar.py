# -*- coding: utf-8 -*-
"""
Правая панель настроек — во всю высоту окна.

Структура:
    ┌─────────────────────────────────┐
    │ Settings    🎨 Presets   ↺  ⚙  │  header (фикс, не скроллится)
    ├─────────────────────────────────┤
    │ ┌─────────────────────────────┐ │
    │ │ ▶ Font                      │ │  Base scroll (~30% высоты,
    │ │ ▶ Style                     │ │   свой скроллбар)
    │ │ ▶ Rotation                  │ │
    │ │ ▶ Arc / circle text         │ │
    │ │ ▶ Opacity                   │ │
    │ │ ▶ Background                │ │
    │ └─────────────────────────────┘ │
    ├─────────────────────────────────┤
    │ ┌─────────────────────────────┐ │
    │ │ Эффекты                     │ │  FX scroll (~70% высоты,
    │ │ [icon] [icon] ...           │ │   свой скроллбар)
    │ │ ▼ Pattern fill              │ │  ← активная панель
    │ │   ...                        │ │
    │ └─────────────────────────────┘ │
    └─────────────────────────────────┘

Sidebar — ctk.CTkFrame (НЕ ScrollableFrame): у него два независимых
скролла — Base и FX. Соотношение 30/70 через grid_rowconfigure(weight).

Sidebar — единственный источник истины для active_id (какая панель
эффекта сейчас раскрыта). FXGrid (ui/fx_grid.py) спрашивает у него
через is_active_fn и перерисовывается по вызову refresh_fx_grid().

Sidebar._on_change() — вызывается из manual_sidebar и auto_sidebar
при реальном изменении settings (эффект включили/выключили, подвинули
слайдер) => MainWindow обновит превью и запишет шаг Undo/Redo.

AutoHideScrollFrame (ui/widgets.py) — прячет свой скроллбар,
когда контент помещается в видимую область. refresh_scrollbar()
вызывается после операций, меняющих содержимое скролла
(сворачивание Base-секции, смена активной панели эффекта).
"""

import customtkinter as ctk

from ui.auto_sidebar import build_single_effect_panel, MANUAL_EFFECT_IDS
from ui.fx_grid import FXGrid
from ui.widgets import AutoHideScrollFrame
from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS
from ui import manual_sidebar as ms


# Base-секции — id, i18n-ключ заголовка, builder-функция.
# Все сворачиваемые (▼ в заголовке). Порядок — как на экране.
BASE_SECTIONS = [
    ("base.font",       "font",       ms.build_font_section),
    ("base.style",      "text_style", ms.build_style_text_part),
    ("base.rotation",   "rotation",   ms.build_rotation_section),
    ("base.arc",        "arc_text",   ms.build_arc_section),
    ("base.opacity",    "opacity",    ms.build_opacity_section),
    ("base.background", "background", ms.build_background_section),
]

DEFAULT_ACTIVE_EFFECT = None   # None = ни одна панель эффекта не открыта


class Sidebar(ctk.CTkFrame):
    """Правая колонка: header + Base scroll + FX scroll."""

    def __init__(self, parent, settings, i18n):
        super().__init__(parent, width=340, corner_radius=6)

        self.grid_propagate(False)

        # Пропорция 30/70 между Base и FX scroll.
        self.grid_rowconfigure(0, weight=0)  # header (фикс)
        self.grid_rowconfigure(1, weight=3)  # base_scroll
        self.grid_rowconfigure(2, weight=7)  # fx_scroll
        self.grid_columnconfigure(0, weight=1)

        self.settings = settings
        self.i18n = i18n
        self._on_change_callbacks = []

        # id активной панели эффекта (None — ни одна не открыта).
        self.active_id = DEFAULT_ACTIVE_EFFECT

        # Сворачивание Base-секций: id -> bool (collapsed).
        # По умолчанию все свёрнуты — пользователь разворачивает
        # только нужную секцию.
        self._base_collapsed = {pid: True for pid, _, _ in BASE_SECTIONS}

        # Сворачивание активной панели эффекта.
        self._active_collapsed = False

        # panel_id -> BooleanVar (для синхронизации enabled-чекбоксов).
        self._enabled_vars = {}
        self._enabled_keys = {}

        # Публичные ссылки для MainWindow.
        self._reset_base_refs()
        self.settings_label = None
        self.style_presets_button = None

        # Колбэк на ⚙ (устанавливается из MainWindow).
        self._settings_callback = None

        # Ссылки на скроллы и активную панель.
        self._base_scroll = None
        self._fx_scroll = None
        self._fx_grid = None
        self._active_panel_frame = None

        self._create_sidebar()

    # ============================================================
    #  Callbacks
    # ============================================================

    def _on_change(self):
        for callback in self._on_change_callbacks:
            callback()

    def add_change_callback(self, callback):
        self._on_change_callbacks.append(callback)

    def set_settings_callback(self, callback):
        """Устанавливает колбэк для ⚙ (открыть SettingsDialog)."""
        self._settings_callback = callback

    def _refresh_all_widgets(self):
        """Пересобрать всё содержимое (после сброса / смены языка)."""
        for widget in self.winfo_children():
            widget.destroy()
        self._create_sidebar()

    # ============================================================
    #  Публичное API
    # ============================================================

    def _known_effect_ids(self):
        """Множество валидных id эффектов (без MANUAL_EFFECT_IDS)."""
        return {
            cls.id for cls in PIPELINE + POST_COMPOSE_EFFECTS
            if cls.id not in MANUAL_EFFECT_IDS
        }

    def set_active(self, panel_id):
        """
        Сделать panel_id активной панелью эффекта. Перерисовывает
        ТОЛЬКО блок активной панели (Base и FXGrid не трогаются).
        """
        if panel_id not in self._known_effect_ids():
            return
        self.active_id = panel_id
        self._active_collapsed = False
        self._render_active_panel()
        self.refresh_fx_grid()

    def refresh_fx_grid(self):
        """Пересчитать цвета иконок FXGrid."""
        if self._fx_grid is not None:
            self._fx_grid.refresh()

    def sync_enabled_vars(self):
        """
        Перечитать settings для enabled-var активной панели. Нужно
        после внешних изменений settings (Undo/Redo, сброс, пресеты).
        """
        for panel_id, var in self._enabled_vars.items():
            key = self._enabled_keys.get(panel_id)
            if key:
                var.set(bool(getattr(self.settings, key, False)))

    # ============================================================
    #  Сборка
    # ============================================================

    def _create_sidebar(self):
        # --- row 0: header (фикс, не скроллится) ---
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=0, pady=0)

        header = ms.build_header(header_frame, self, self.settings, self.i18n)
        self.settings_label = header["label"]
        self.style_presets_button = header["presets_button"]

        # Кнопка ⚙ — в правом верхнем углу header.
        header_inner = header.get("frame")
        if header_inner is not None:
            settings_btn = ctk.CTkButton(
                header_inner, text="⚙", width=32, height=28,
                font=("Segoe UI Symbol", 16),
                fg_color=("#dbdbdb", "#2b2b2b"),
                text_color=("#1a1a1a", "#e0e0e0"),
                hover_color=("#c7c7c7", "#3a3a3a"),
                command=self._on_settings_clicked,
            )
            # ⚙ должен оказаться крайней справа. reset_button и
            # presets_button уже упакованы (оба side="right") внутри
            # build_header — чтобы ⚙ встал ПРАВЕЕ них, вставляем его
            # в очередь упаковки ПЕРЕД reset_button через before=.
            reset_button = header.get("reset_button")
            if reset_button is not None:
                settings_btn.pack(side="right", padx=(4, 0), before=reset_button)
            else:
                settings_btn.pack(side="right", padx=(4, 0))

        self._reset_base_refs()
        self._enabled_vars = {}
        self._enabled_keys = {}

        # --- row 1: Base scroll (30%) — с авто-скрытием скроллбара ---
        self._base_scroll = AutoHideScrollFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._base_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 4))

        for panel_id, label_key, builder_fn in BASE_SECTIONS:
            self._render_base_section(panel_id, label_key, builder_fn)

        # --- row 2: FX scroll (70%) — с авто-скрытием скроллбара ---
        self._fx_scroll = AutoHideScrollFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._fx_scroll.grid(row=2, column=0, sticky="nsew", padx=6, pady=(4, 6))

        self._fx_grid = FXGrid(
            self._fx_scroll, self.settings, self.i18n,
            on_select=self._on_fx_select,
            is_active_fn=lambda pid: pid == self.active_id,
        )
        self._fx_grid.pack(fill="x", padx=4, pady=(4, 4))
        self._fx_grid.refresh()

        # Активная панель эффекта — тоже в FX scroll, под FXGrid.
        self._render_active_panel()

        # Первый пересчёт скроллбаров — после полной сборки UI.
        # after(150) — дать Tk время на расчёт геометрии после
        # создания всех виджетов.
        self.after(150, self._base_scroll.refresh_scrollbar)
        self.after(150, self._fx_scroll.refresh_scrollbar)

    def _on_settings_clicked(self):
        """Клик по ⚙ — вызвать колбэк, если он установлен."""
        if callable(self._settings_callback):
            self._settings_callback()

    def _on_fx_select(self, panel_id):
        """Клик по иконке FX — сделать эффект активным."""
        self.set_active(panel_id)

    # ------------------------------------------------------------
    #  Base-секции
    # ------------------------------------------------------------

    def _render_base_section(self, panel_id, label_key, builder_fn):
        """
        Одна Base-секция: [▶ Font] + [body]. По клику на заголовок —
        сворачивание/разворачивание body.
        """
        collapsed = self._base_collapsed.get(panel_id, True)

        wrap = ctk.CTkFrame(self._base_scroll, fg_color="transparent")
        wrap.pack(fill="x", padx=6, pady=(2, 4))

        header_btn = ctk.CTkButton(
            wrap,
            text=("▶ " if collapsed else "▼ ") + self.i18n.tr(label_key),
            anchor="w", height=26,
            font=("Arial", 12, "bold"),
            fg_color="transparent",
            hover_color=("#d0d0d0", "#3a3a3a"),
            text_color=("#1a1a1a", "#e0e0e0"),
            command=lambda pid=panel_id: self._toggle_base(pid),
        )
        header_btn.pack(fill="x")

        body = ctk.CTkFrame(wrap, fg_color="transparent")
        if not collapsed:
            body.pack(fill="x")

        widgets = builder_fn(body, self, self.settings, self.i18n)
        self._store_base_refs(panel_id, widgets)

        if not hasattr(self, "_base_bodies"):
            self._base_bodies = {}
        self._base_bodies[panel_id] = {
            "wrap": wrap, "header": header_btn, "body": body,
            "label_key": label_key,
        }

    def _toggle_base(self, panel_id):
        info = self._base_bodies.get(panel_id)
        if info is None:
            return
        collapsed = not self._base_collapsed.get(panel_id, True)
        self._base_collapsed[panel_id] = collapsed

        arrow = "▶" if collapsed else "▼"
        info["header"].configure(
            text=f"{arrow} {self.i18n.tr(info['label_key'])}"
        )
        if collapsed:
            info["body"].pack_forget()
        else:
            info["body"].pack(fill="x")

        # Пересчитать скроллбар Base-скролла: контент изменился.
        if self._base_scroll is not None:
            self.after(80, self._base_scroll.refresh_scrollbar)

    def _reset_base_refs(self):
        """
        Публичные атрибуты, которые читает MainWindow. Существуют,
        пока живы соответствующие Base-секции. После
        _refresh_all_widgets() старые виджеты уничтожены — main_window
        обязан проверять на None перед обращением.
        """
        self.font_size_entry = None
        self.font_size_slider = None
        self.text_color_button = None
        self.rotation_entry = None
        self.rotation_slider = None
        self.arc_frame = None
        self.opacity_entry = None
        self.opacity_slider = None
        self.background_color_button = None
        self._base_bodies = {}

    def _store_base_refs(self, panel_id, widgets):
        if panel_id == "base.font":
            self.font_size_entry = widgets.get("size_entry")
            self.font_size_slider = widgets.get("size_slider")
        elif panel_id == "base.style":
            self.text_color_button = widgets.get("text_color_button")
        elif panel_id == "base.rotation":
            self.rotation_entry = widgets.get("entry")
            self.rotation_slider = widgets.get("slider")
        elif panel_id == "base.arc":
            self.arc_frame = widgets.get("body_frame")
        elif panel_id == "base.opacity":
            self.opacity_entry = widgets.get("entry")
            self.opacity_slider = widgets.get("slider")
        elif panel_id == "base.background":
            self.background_color_button = widgets.get("color_button")

    # ------------------------------------------------------------
    #  Активная панель эффекта (внутри FX scroll)
    # ------------------------------------------------------------

    def _render_active_panel(self):
        """Перерисовать только блок активной панели (Base и FXGrid не трогаются)."""
        if self._active_panel_frame is not None:
            try:
                self._active_panel_frame.destroy()
            except Exception:
                pass
            self._active_panel_frame = None

        # При смене активного эффекта старые BooleanVar (от уничтоженных
        # чекбоксов) в _enabled_vars/_enabled_keys не нужны — открыта
        # максимум ОДНА панель эффекта.
        self._enabled_vars = {}
        self._enabled_keys = {}

        if self.active_id is None:
            # Активной панели нет — контент FX-скролла стал короче.
            if self._fx_scroll is not None:
                self.after(80, self._fx_scroll.refresh_scrollbar)
            return

        by_id = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}
        cls = by_id.get(self.active_id)
        if cls is None:
            if self._fx_scroll is not None:
                self.after(80, self._fx_scroll.refresh_scrollbar)
            return

        wrap = ctk.CTkFrame(self._fx_scroll, fg_color="transparent")
        wrap.pack(fill="x", padx=6, pady=(6, 10))
        self._active_panel_frame = wrap

        collapsed = self._active_collapsed
        header_btn = ctk.CTkButton(
            wrap,
            text=("▶ " if collapsed else "▼ ") + self.i18n.tr(cls.label_key),
            anchor="w", height=26,
            font=("Arial", 12, "bold"),
            fg_color="transparent",
            hover_color=("#d0d0d0", "#3a3a3a"),
            text_color=("#1a1a1a", "#e0e0e0"),
            command=self._toggle_active,
        )
        header_btn.pack(fill="x")

        body = ctk.CTkFrame(wrap, fg_color="transparent")
        if not collapsed:
            body.pack(fill="x")

        panel = build_single_effect_panel(
            body, self, self.settings, self.i18n, cls,
        )
        self._enabled_vars[self.active_id] = panel["enabled_var"]
        self._enabled_keys[self.active_id] = f"{self.active_id}_enabled"

        # Пересчитать скроллбар FX-скролла: панель эффекта могла
        # сильно увеличить контент.
        if self._fx_scroll is not None:
            self.after(80, self._fx_scroll.refresh_scrollbar)

    def _toggle_active(self):
        self._active_collapsed = not self._active_collapsed
        self._render_active_panel()