# -*- coding: utf-8 -*-
"""
Левый "рельс" (rail) с пиктограммами — Blender-style.

В отличие от первой (Photoshop-style) версии, рельс здесь ЧИСТО
навигационный и не хранит собственного состояния "включено"/"закреплено":
   - подсветка иконки = активная вкладка (какая панель сейчас "активна",
     т.е. первая в стеке справа) — это единственное, что решает клик;
   - "точка" в углу иконки = settings.<id>_enabled (только для реальных
     эффектов; у "Arc" тоже есть флаг arc_text_enabled, у остальных
     Base-разделов — нет, там точка не рисуется);
   - тонкая рамка = эффект закреплён (pinned) в стеке справа.

Рельс НЕ пишет напрямую в settings (кроме как через колбэки, которые
вызывают методы Sidebar). Вся правда о том, что активно/закреплено —
в ui/sidebar.py (Sidebar.active_id / Sidebar.pinned_ids); рельс лишь
спрашивает об этом через is_active_fn/is_pinned_fn при каждом refresh().
Такое разделение исключает рассинхронизацию двух независимых копий
одного и того же состояния (см. историю правок в предыдущей версии).

Структура (сверху вниз):
  1. Группа "Base" — НЕ прокручивается, всегда видна: font, style,
     rotation, arc, opacity, background. Это те настройки, к которым
     нужен частый доступ (шрифт меняют постоянно) — раньше они были
     погребены в общем прокручиваемом списке.
  2. Прокручиваемая область: эффекты PIPELINE/POST_COMPOSE_EFFECTS,
     сгруппированные по стадии (Fill/Inner/Outer/Geometry/Post) — те
     же стадии, что и в effects/registry.py. Каждая группа сворачивается
     по клику на заголовок.
  3. Нижняя панель — глобальные действия рельса: "📌 Открепить всё" и
     "Свернуть/развернуть все группы".
"""

import customtkinter as ctk

from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS

# id базовых (не-эффектных) разделов — префикс "base." гарантированно
# не пересекается с id эффектов из реестра.
BASE_IDS = [
    ("base.font", "🔤", "font", None),
    ("base.style", "🎨", "text_style", None),
    ("base.rotation", "🔄", "rotation", None),
    ("base.arc", "🌙", "arc_text", "arc_text_enabled"),
    ("base.opacity", "🌫", "opacity", None),
    ("base.background", "🖼", "background", None),
]

# Группы эффектов из PIPELINE/POST_COMPOSE_EFFECTS — те же стадии, что
# в effects/registry.py (fill/inner/outer/geometry/post), только
# "shadow" (POST_COMPOSE, физически stage="post_compose") визуально
# отнесён к "Outer" — так он и был расположен в старом линейном
# сайдбаре (сразу после inner-эффектов, перед skew/perspective).
GROUPS = [
    ("group_fill", [("gradient", "🌈"), ("pattern", "🧱")]),
    ("group_inner", [("outline_inner", "◻"), ("glow_inner", "🔆"),
                      ("emboss", "🗿"), ("inner_shadow", "🕳")]),
    ("group_outer", [("outline_outer", "⬜"), ("glow_outer", "✨"),
                      ("extrude", "🧊"), ("shadow", "🌑")]),
    ("group_geometry", [("skew", "📐"), ("perspective", "🎭")]),
    ("group_post", [("reflection", "🪞"), ("halftone", "⚫"), ("glitch", "📺")]),
]

_COLOR_ACTIVE = "#1f538d"
_COLOR_ACTIVE_TEXT = "white"
_COLOR_IDLE = ("#dbdbdb", "#2b2b2b")
_COLOR_IDLE_TEXT = ("#1a1a1a", "#e0e0e0")
_COLOR_DOT_ON = "#4caf50"
_COLOR_PIN_BORDER = "#f0a500"


class EffectRail(ctk.CTkFrame):
    """Композитный виджет: закреплённая шапка Base + скролл групп + низ."""

    def __init__(self, parent, settings, i18n, *,
                 on_select, on_pin_toggle, on_collapse_others, on_unpin_all,
                 is_active_fn, is_pinned_fn):
        super().__init__(parent, width=78, corner_radius=0,
                          fg_color=("#dbdbdb", "#242424"))
        self.settings = settings
        self.i18n = i18n
        self._on_select = on_select
        self._on_pin_toggle = on_pin_toggle
        self._on_collapse_others = on_collapse_others
        self._on_unpin_all = on_unpin_all
        self._is_active_fn = is_active_fn
        self._is_pinned_fn = is_pinned_fn

        # id -> {"icon_btn":.., "dot":.., "enabled_key": str|None}
        self._rows = {}
        # группа-заголовок -> (frame_с_иконками, bool collapsed)
        self._group_bodies = {}
        self._groups_collapsed = {}
        self._all_collapsed_flag = False

        self.pack_propagate(False)

        self._build_base_section()
        self._build_separator()
        self._build_scrollable_groups()
        self._build_bottom_controls()

    # ------------------------------------------------------------
    #  Base (не прокручивается)
    # ------------------------------------------------------------

    def _build_base_section(self):
        ctk.CTkLabel(self, text=self.i18n.tr("base_group"),
                     font=("Arial", 9, "bold"), text_color="gray").pack(
            anchor="w", padx=6, pady=(6, 0)
        )
        for effect_id, glyph, label_key, enabled_key in BASE_IDS:
            self._build_row(self, effect_id, glyph, self.i18n.tr(label_key), enabled_key)

    def _build_separator(self):
        sep = ctk.CTkFrame(self, height=1, fg_color=("#a0a0a0", "#454545"))
        sep.pack(fill="x", padx=6, pady=6)

    # ------------------------------------------------------------
    #  Прокручиваемые группы эффектов
    # ------------------------------------------------------------

    def _build_scrollable_groups(self):
        self.scroll_area = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll_area.pack(fill="both", expand=True, padx=0, pady=0)

        by_id = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}

        for group_key, members in GROUPS:
            self._groups_collapsed[group_key] = False
            group_wrap = ctk.CTkFrame(self.scroll_area, fg_color="transparent")
            group_wrap.pack(fill="x", pady=(2, 4))

            header_btn = ctk.CTkButton(
                group_wrap, text="▼ " + self.i18n.tr(group_key),
                anchor="w", height=22, font=("Arial", 10, "bold"),
                fg_color="transparent", hover_color=("#c7c7c7", "#3a3a3a"),
                text_color=("#333333", "#cccccc"),
                command=lambda gk=group_key: self._toggle_group(gk),
            )
            header_btn.pack(fill="x", padx=4)

            body = ctk.CTkFrame(group_wrap, fg_color="transparent")
            body.pack(fill="x")

            for effect_id, glyph in members:
                cls = by_id.get(effect_id)
                if cls is None:
                    # Эффект мог быть удалён из реестра — не падаем,
                    # просто не рисуем для него иконку.
                    continue
                enabled_key = f"{effect_id}_enabled"
                self._build_row(body, effect_id, glyph,
                                 self.i18n.tr(cls.label_key), enabled_key)

            self._group_bodies[group_key] = {"header_btn": header_btn, "body": body}

    def _toggle_group(self, group_key):
        collapsed = not self._groups_collapsed[group_key]
        self._set_group_collapsed(group_key, collapsed)

    def _set_group_collapsed(self, group_key, collapsed):
        self._groups_collapsed[group_key] = collapsed
        info = self._group_bodies[group_key]
        arrow = "▶" if collapsed else "▼"
        # Текст группы всегда переводим заново — простое обновление
        # префикса-стрелки без пересборки заголовка.
        label = info["header_btn"].cget("text").split(" ", 1)[-1]
        info["header_btn"].configure(text=f"{arrow} {label}")
        if collapsed:
            info["body"].pack_forget()
        else:
            info["body"].pack(fill="x")

    def _toggle_all_groups(self):
        """Кнопка снизу: свернуть/развернуть ВСЕ группы разом."""
        self._all_collapsed_flag = not self._all_collapsed_flag
        for group_key, _members in GROUPS:
            self._set_group_collapsed(group_key, self._all_collapsed_flag)
        self.collapse_all_btn.configure(
            text=("▶ " if self._all_collapsed_flag else "▼ ")
            + self.i18n.tr("expand_all_groups" if self._all_collapsed_flag
                           else "collapse_all_groups")
        )

    # ------------------------------------------------------------
    #  Нижняя панель рельса
    # ------------------------------------------------------------

    def _build_bottom_controls(self):
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", side="bottom", padx=4, pady=(4, 6))

        ctk.CTkButton(
            bottom, text="📌 " + self.i18n.tr("unpin_all"),
            height=24, font=("Arial", 10),
            command=lambda: self._on_unpin_all(),
        ).pack(fill="x", pady=(0, 4))

        self.collapse_all_btn = ctk.CTkButton(
            bottom, text="▼ " + self.i18n.tr("collapse_all_groups"),
            height=24, font=("Arial", 10),
            command=self._toggle_all_groups,
        )
        self.collapse_all_btn.pack(fill="x")

    # ------------------------------------------------------------
    #  Строим одну строку-иконку (общая для Base и для эффектов)
    # ------------------------------------------------------------

    def _build_row(self, parent, panel_id, glyph, label_text, enabled_key):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)

        icon_btn = ctk.CTkButton(
            row, text=glyph, width=52, height=36,
            font=("Segoe UI Symbol", 16),
            command=lambda pid=panel_id: self._on_select(pid),
        )
        icon_btn.pack(padx=4)
        icon_btn.bind("<Button-3>", lambda e, pid=panel_id: self._show_context_menu(e, pid))

        dot = None
        if enabled_key is not None:
            dot = ctk.CTkLabel(row, text="●", text_color=_COLOR_DOT_ON,
                                font=("Arial", 10), fg_color="transparent")
            # Позиционируем поверх кнопки (row — общий родитель и для
            # pack-нутой кнопки, и для place-нутой точки — это ок).

        ctk.CTkLabel(row, text=label_text, font=("Arial", 8),
                     wraplength=68).pack()

        self._rows[panel_id] = {"icon_btn": icon_btn, "dot": dot,
                                 "enabled_key": enabled_key}
        self._style_row(panel_id)

    # ------------------------------------------------------------
    #  Контекстное меню (ПКМ по иконке)
    # ------------------------------------------------------------

    def _show_context_menu(self, event, panel_id):
        import tkinter as tk
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=self.i18n.tr("open_panel"),
                          command=lambda: self._on_select(panel_id))
        pin_label = (self.i18n.tr("unpin_panel") if self._is_pinned_fn(panel_id)
                     else self.i18n.tr("pin_panel"))
        menu.add_command(label=pin_label,
                          command=lambda: self._on_pin_toggle(panel_id))
        menu.add_separator()
        menu.add_command(label=self.i18n.tr("collapse_others"),
                          command=lambda: self._on_collapse_others(panel_id))
        menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------
    #  Стилизация / обновление извне
    # ------------------------------------------------------------

    def _style_row(self, panel_id):
        info = self._rows.get(panel_id)
        if info is None:
            return

        is_active = self._is_active_fn(panel_id)
        is_pinned = self._is_pinned_fn(panel_id)
        enabled_key = info["enabled_key"]
        is_enabled = bool(enabled_key) and bool(getattr(self.settings, enabled_key, False))

        fg = _COLOR_ACTIVE if is_active else _COLOR_IDLE
        text_color = _COLOR_ACTIVE_TEXT if is_active else _COLOR_IDLE_TEXT
        info["icon_btn"].configure(
            fg_color=fg, text_color=text_color,
            border_width=2 if is_pinned else 0,
            border_color=_COLOR_PIN_BORDER,
        )

        dot = info["dot"]
        if dot is not None:
            if is_enabled:
                dot.place(relx=1.0, rely=0.0, x=-6, y=2, anchor="ne")
            else:
                dot.place_forget()

    def refresh(self):
        """
        Перерисовывает ВСЕ строки — вызывать после любого изменения,
        которое могло затронуть: активную вкладку, список пинов,
        settings.<id>_enabled (Undo/Redo, сброс настроек, пресеты,
        переключение чекбокса внутри панели справа).
        """
        for panel_id in self._rows:
            self._style_row(panel_id)
