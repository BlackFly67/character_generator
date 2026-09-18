# -*- coding: utf-8 -*-
"""
Правая панель настроек — во всю высоту окна.

Структура:
    ┌─────────────────────────────────┐
    │ Settings    🎨 Presets   ↺  ⚙  │  header (фикс, блок)
    ├─────────────────────────────────┤
    │ ▶ Font                          │  Base (прозрачный,
    │ ▶ Style                         │   растягивается)
    │ ▶ Rotation                      │
    │ ▶ Arc / circle text             │
    │ ▶ Opacity                       │
    │ ▶ Background                    │
    ├─────────────────────────────────┤
    │ Эффекты                         │  FX (блок с фоном,
    │ [icon] [icon] [icon] ...        │   мин. высота 180,
    │ [icon] [icon] [icon] ...        │   не растягивается)
    ├─────────────────────────────────┤
    │ ▼ Pattern fill                  │  Active (прозрачный,
    │   Choose texture ...            │   растягивается)
    │   Scale ...                     │
    └─────────────────────────────────┘

Sidebar — ctk.CTkFrame (НЕ ScrollableFrame): 4 grid-строки —
header (фикс, weight=0), Base (weight=1), FX (weight=0, фикс. высота),
Active (weight=1).
"""

import customtkinter as ctk

from ui.auto_sidebar import build_single_effect_panel, MANUAL_EFFECT_IDS
from ui.fx_grid import FXGrid
from ui.widgets import AutoHideScrollFrame
from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS
from ui import manual_sidebar as ms
from ui.theme import BLOCK_BG


BASE_SECTIONS = [
    ("base.font",       "font",       ms.build_font_section),
    ("base.style",      "text_style", ms.build_style_text_part),
    ("base.rotation",   "rotation",   ms.build_rotation_section),
    ("base.arc",        "arc_text",   ms.build_arc_section),
    ("base.opacity",    "opacity",    ms.build_opacity_section),
    ("base.background", "background", ms.build_background_section),
]

DEFAULT_ACTIVE_EFFECT = None


class Sidebar(ctk.CTkFrame):
    """Правая колонка: header + Base + FX + Active."""

    def __init__(self, parent, settings, i18n):
        super().__init__(parent, width=340, corner_radius=6)

        self.grid_propagate(False)

        # 4 строки:
        #   0 — header (фикс),
        #   1 — Base (растягивается),
        #   2 — FX (мин. высота, не растягивается),
        #   3 — Active (растягивается).
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.settings = settings
        self.i18n = i18n
        self._on_change_callbacks = []

        self.active_id = DEFAULT_ACTIVE_EFFECT
        self._base_collapsed = {pid: True for pid, _, _ in BASE_SECTIONS}
        self._active_collapsed = False

        self._enabled_vars = {}
        self._enabled_keys = {}

        self._reset_base_refs()
        self.settings_label = None
        self.style_presets_button = None
        self._settings_callback = None

        self._base_scroll = None
        self._fx_scroll = None
        self._active_scroll = None
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
        self._settings_callback = callback

    def _refresh_all_widgets(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._create_sidebar()

    # ============================================================
    #  Публичное API
    # ============================================================

    def _known_effect_ids(self):
        return {
            cls.id for cls in PIPELINE + POST_COMPOSE_EFFECTS
            if cls.id not in MANUAL_EFFECT_IDS
        }

    def set_active(self, panel_id):
        if panel_id not in self._known_effect_ids():
            return
        self.active_id = panel_id
        self._active_collapsed = False
        self._render_active_panel()
        self.refresh_fx_grid()

    def refresh_fx_grid(self):
        if self._fx_grid is not None:
            self._fx_grid.refresh()

    def sync_enabled_vars(self):
        for panel_id, var in self._enabled_vars.items():
            key = self._enabled_keys.get(panel_id)
            if key:
                var.set(bool(getattr(self.settings, key, False)))

    # ============================================================
    #  Сборка
    # ============================================================

    def _create_sidebar(self):
        # --- row 0: header (фикс, блок) ---
        header_frame = ctk.CTkFrame(
            self, fg_color=BLOCK_BG, corner_radius=4,
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 2))

        header = ms.build_header(header_frame, self, self.settings, self.i18n)
        self.settings_label = header["label"]
        self.style_presets_button = header["presets_button"]

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
            reset_button = header.get("reset_button")
            if reset_button is not None:
                settings_btn.pack(side="right", padx=(4, 0), before=reset_button)
            else:
                settings_btn.pack(side="right", padx=(4, 0))

        self._reset_base_refs()
        self._enabled_vars = {}
        self._enabled_keys = {}

        # --- row 1: Base scroll (прозрачный, растягивается) ---
        self._base_scroll = AutoHideScrollFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._base_scroll.grid(row=1, column=0, sticky="nsew",
                                padx=6, pady=(2, 2))

        # Секцию "arc" строим отдельно — она должна скрываться
        # в режиме иконок. Остальные Base-секции — как есть.
        for panel_id, label_key, builder_fn in BASE_SECTIONS:
            if panel_id == "base.arc":
                continue
            self._render_base_section(panel_id, label_key, builder_fn)

        # arc — рендерим и сохраняем ссылки, чтобы можно было
        # упаковать/распаковать по режиму.
        self._render_base_section(
            "base.arc", "arc_text", ms.build_arc_section
        )
        # Синхронизируем видимость arc с текущим режимом.
        self._sync_arc_visibility()

        # --- row 2: FX scroll (блок, мин. высота 180) ---
        self._fx_scroll = ctk.CTkFrame(
            self, fg_color=BLOCK_BG, corner_radius=4,
            height=180,
        )
        self._fx_scroll.grid(row=2, column=0, sticky="ew",
                              padx=6, pady=(2, 2))
        

        self._fx_grid = FXGrid(
            self._fx_scroll, self.settings, self.i18n,
            on_select=self._on_fx_select,
            is_active_fn=lambda pid: pid == self.active_id,
        )
        self._fx_grid.pack(fill="x", padx=4, pady=(4, 4))
        self._fx_grid.refresh()

        # --- row 3: Active scroll (прозрачный, растягивается) ---
        self._active_scroll = AutoHideScrollFrame(
            self, fg_color="transparent", corner_radius=0,
        )
        self._active_scroll.grid(row=3, column=0, sticky="nsew",
                                  padx=6, pady=(2, 6))

        self._render_active_panel()

        self.after(150, self._base_scroll.refresh_scrollbar)

        self.after(150, self._active_scroll.refresh_scrollbar)

    def _on_settings_clicked(self):
        if callable(self._settings_callback):
            self._settings_callback()

    def _on_fx_select(self, panel_id):
        self.set_active(panel_id)

    # ------------------------------------------------------------
    #  Base-секции
    # ------------------------------------------------------------

    def _render_base_section(self, panel_id, label_key, builder_fn):
        collapsed = self._base_collapsed.get(panel_id, True)

        wrap = ctk.CTkFrame(self._base_scroll, fg_color="transparent")
        wrap.pack(fill="x", padx=6, pady=(2, 4))

        # Динамический label_key: для base.font в режиме иконок
        # показываем "Icon", иначе — "Font".
        effective_key = label_key
        if panel_id == "base.font" and self.settings.icon_mode:
            effective_key = "icon_section"

        header_btn = ctk.CTkButton(
            wrap,
            text=("▶ " if collapsed else "▼ ") + self.i18n.tr(effective_key),
            anchor="w", height=26,
            font=("Arial", 12, "bold"),
            fg_color="transparent",
            hover_color=("#b8b8b8", "#444444"),
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
            "widgets": widgets,   # ← для _sync_font_section_content
        }

    def _toggle_base(self, panel_id):
        info = self._base_bodies.get(panel_id)
        if info is None:
            return
        collapsed = not self._base_collapsed.get(panel_id, True)
        self._base_collapsed[panel_id] = collapsed

        arrow = "▶" if collapsed else "▼"
        # Динамический ключ для base.font (Font / Icon).
        label_key = info["label_key"]
        if panel_id == "base.font" and self.settings.icon_mode:
            label_key = "icon_section"
        info["header"].configure(
            text=f"{arrow} {self.i18n.tr(label_key)}"
        )
        if collapsed:
            info["body"].pack_forget()
        else:
            info["body"].pack(fill="x")

        if self._base_scroll is not None:
            self.after(80, self._base_scroll.refresh_scrollbar)

    def _reset_base_refs(self):
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
    #  Синхронизация секций, зависящих от режима (icon_mode)
    # ------------------------------------------------------------

    def _sync_arc_visibility(self):
        """
        Показать/скрыть секцию 'base.arc' по текущему режиму.

        Восстанавливаем ПОЗИЦИЮ через pack(before=...), иначе
        при repack секция уедет в конец Base-скролла (после
        background), ломая порядок.
        """
        arc_info = self._base_bodies.get("base.arc")
        if arc_info is None:
            return
        wrap = arc_info["wrap"]
        if self.settings.icon_mode:
            wrap.pack_forget()
        else:
            # Восстанавливаем ПЕРЕД следующей секцией (opacity),
            # иначе arc уедет в конец Base-скролла.
            next_info = self._base_bodies.get("base.opacity")
            next_wrap = next_info["wrap"] if next_info is not None else None
            if next_wrap is not None:
                wrap.pack(fill="x", padx=6, pady=(2, 4), before=next_wrap)
            else:
                wrap.pack(fill="x", padx=6, pady=(2, 4))

    def _sync_font_section_content(self):
        """
        Переключить содержимое секции 'base.font' при смене
        settings.icon_mode. Виджеты уже построены — только
        pack/pack_forget групп.
        """
        info = self._base_bodies.get("base.font")
        if info is None:
            return
        from ui.manual_sidebar import _apply_font_section_mode
        widgets = info.get("widgets")
        if widgets is None:
            return
        _apply_font_section_mode(self.settings, widgets)

    def _sync_mode_dependent_sections(self):
        """
        Показать/скрыть секции, зависящие от режима (icon_mode):
          - 'base.arc' — только в текстовом режиме;
          - 'base.font' — переключает содержимое (текст / иконки).
        Вызывать после смены settings.icon_mode.
        """
        # arc: скрываем в режиме иконок.
        self._sync_arc_visibility()

        # font: переключить отображение содержимого.
        self._sync_font_section_content()

        # Обновить заголовок секции base.font: "Font" / "Icon".
        font_info = self._base_bodies.get("base.font")
        if font_info is not None:
            collapsed = self._base_collapsed.get("base.font", True)
            arrow = "▶" if collapsed else "▼"
            key = "icon_section" if self.settings.icon_mode else "font"
            font_info["header"].configure(
                text=f"{arrow} {self.i18n.tr(key)}"
            )

    # ------------------------------------------------------------
    #  Активная панель эффекта (в _active_scroll, row 3)
    # ------------------------------------------------------------

    def _render_active_panel(self):
        if self._active_panel_frame is not None:
            try:
                self._active_panel_frame.destroy()
            except Exception:
                pass
            self._active_panel_frame = None

        self._enabled_vars = {}
        self._enabled_keys = {}

        if self.active_id is None:
            if self._active_scroll is not None:
                self.after(80, self._active_scroll.refresh_scrollbar)
            return

        by_id = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}
        cls = by_id.get(self.active_id)
        if cls is None:
            if self._active_scroll is not None:
                self.after(80, self._active_scroll.refresh_scrollbar)
            return

        wrap = ctk.CTkFrame(self._active_scroll, fg_color="transparent")
        wrap.pack(fill="x", padx=6, pady=(6, 10))
        self._active_panel_frame = wrap

        collapsed = self._active_collapsed
        header_btn = ctk.CTkButton(
            wrap,
            text=("▶ " if collapsed else "▼ ") + self.i18n.tr(cls.label_key),
            anchor="w", height=26,
            font=("Arial", 12, "bold"),
            fg_color="transparent",
            hover_color=("#b8b8b8", "#444444"),
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

        if self._active_scroll is not None:
            self.after(80, self._active_scroll.refresh_scrollbar)

    def _toggle_active(self):
        self._active_collapsed = not self._active_collapsed
        self._render_active_panel()