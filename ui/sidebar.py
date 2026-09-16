# -*- coding: utf-8 -*-
"""
Правая панель настроек — Blender-style стек панелей.

Sidebar больше не показывает ОДНУ панель за раз (как в предыдущей,
Photoshop-style версии) — теперь это СТЕК:

  - self.active_id   — какая панель сейчас "активна" (её открыли кликом
    по иконке на рельсе, ui/effect_rail.py). Показывается ПЕРВОЙ.
  - self.pinned_ids   — список закреплённых панелей (в порядке
    закрепления). Показываются НИЖЕ активной, в этом же порядке.
    Если активная панель сама закреплена — не дублируется, просто
    остаётся первой.
  - self._collapsed   — per-panel флаг "свёрнуто" (стрелка ▼/▶ в
    заголовке, или двойной клик по заголовку).

id панели — либо "base.<name>" (шесть общих разделов: font, style,
rotation, arc, opacity, background — см. BASE_BUILDERS), либо id
эффекта из effects/registry.py (PIPELINE + POST_COMPOSE_EFFECTS).

Sidebar — единственный источник истины для active_id/pinned_ids/
_collapsed. EffectRail (ui/effect_rail.py) ничего этого сам не хранит —
он лишь спрашивает у Sidebar через is_active_fn/is_pinned_fn (передаются
из MainWindow) и перерисовывается по вызову refresh(). Это исключает
рассинхронизацию двух копий одного состояния.

Два разных канала уведомлений наружу (через MainWindow):
  - add_change_callback(cb)  — settings реально изменились (эффект
    включили/выключили, подвинули слайдер) => нужно обновить превью
    и записать шаг Undo/Redo. Тот же контракт, что был раньше.
  - add_layout_callback(cb)  — изменилось UI-состояние (какая панель
    активна/закреплена) => не влияет на settings/превью/историю, но
    рельс должен перекрасить рамки/подсветку. Сворачивание (collapse)
    и смена порядка закреплённых (move_pinned) НЕ дёргают этот канал:
    они не меняют то, что видно на рельсе (активность/закреп), только
    внутри самой панели.
"""

import customtkinter as ctk

from ui.auto_sidebar import build_single_effect_panel, MANUAL_EFFECT_IDS
from effects.registry import PIPELINE, POST_COMPOSE_EFFECTS
from ui import manual_sidebar as ms


# id -> (i18n-ключ заголовка, builder-функция из ui/manual_sidebar.py)
BASE_BUILDERS = {
    "base.font": ("font", ms.build_font_section),
    "base.style": ("text_style", ms.build_style_text_part),
    "base.rotation": ("rotation", ms.build_rotation_section),
    "base.arc": ("arc_text", ms.build_arc_section),
    "base.opacity": ("opacity", ms.build_opacity_section),
    "base.background": ("background", ms.build_background_section),
}

DEFAULT_ACTIVE_ID = "base.font"


class Sidebar(ctk.CTkScrollableFrame):
    """Стек панелей настроек: активная + закреплённые."""

    def __init__(self, parent, settings, i18n):
        super().__init__(parent, width=340, corner_radius=0)
        self.settings = settings
        self.i18n = i18n
        self._on_change_callbacks = []
        self._on_layout_callbacks = []

        self.active_id = DEFAULT_ACTIVE_ID
        self.pinned_ids = []
        self._collapsed = {}

        # panel_id -> BooleanVar (только для панелей, у которых builder
        # вернул "enabled_var" — все реальные эффекты + base.arc).
        self._enabled_vars = {}
        # panel_id -> имя атрибута settings, которое отражает эта var —
        # нужно sync_enabled_vars() после внешних изменений (Undo/Redo,
        # сброс, пресеты).
        self._enabled_keys = {}

        self._reset_base_refs()
        self.settings_label = None
        self.style_presets_button = None

        self._create_sidebar()

    # ============================================================
    #  Callbacks
    # ============================================================

    def _on_change(self):
        for callback in self._on_change_callbacks:
            callback()

    def add_change_callback(self, callback):
        self._on_change_callbacks.append(callback)

    def _on_layout_change(self):
        for callback in self._on_layout_callbacks:
            callback()

    def add_layout_callback(self, callback):
        self._on_layout_callbacks.append(callback)

    def _refresh_all_widgets(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._create_sidebar()

    # ============================================================
    #  Публичное API — вызывается из MainWindow / EffectRail
    # ============================================================

    def _known_ids(self):
        # ИСКЛЮЧАЕМ MANUAL_EFFECT_IDS (сейчас это только "color_fill"):
        # у него нет реального settings.<id>_enabled (ColorFill.apply()
        # вообще не проверяет _enabled()), его UI — кнопка цвета текста
        # в base.style. Ни в одной группе EffectRail иконки для него нет,
        # но без этого фильтра set_active()/toggle_pin() всё равно
        # приняли бы этот id как "валидный" (он есть в PIPELINE) и
        # построили бы бессмысленную панель с нерабочим чекбоксом —
        # поймано при ручном прогоне всех id из PIPELINE через
        # set_active() (задел на будущее: если что-то ещё когда-нибудь
        # вызовет set_active с произвольным id из реестра).
        ids = set(BASE_BUILDERS.keys())
        ids.update(
            cls.id for cls in PIPELINE + POST_COMPOSE_EFFECTS
            if cls.id not in MANUAL_EFFECT_IDS
        )
        return ids

    def set_active(self, panel_id):
        """Клик по иконке на рельсе — делает панель активной (наверх стека)."""
        if panel_id not in self._known_ids():
            return
        self.active_id = panel_id
        self._refresh_all_widgets()
        self._on_layout_change()

    def toggle_pin(self, panel_id):
        """📌 в заголовке панели ИЛИ пункт меню на рельсе."""
        if panel_id not in self._known_ids():
            return
        if panel_id in self.pinned_ids:
            self.pinned_ids.remove(panel_id)
        else:
            self.pinned_ids.append(panel_id)
        self._refresh_all_widgets()
        self._on_layout_change()

    def unpin_all(self):
        if not self.pinned_ids:
            return
        self.pinned_ids = []
        self._refresh_all_widgets()
        self._on_layout_change()

    def collapse_all_except(self, panel_id):
        """
        Контекстное меню рельса: «Свернуть остальные». Сворачивает все
        панели ТЕКУЩЕГО стека, кроме panel_id, и разворачивает саму
        panel_id. Чисто локальное изменение (_collapsed) — состав
        активной/закреплённых панелей не меняется, поэтому рельс
        перерисовывать не нужно.
        """
        stack_ids = self._compute_stack_order()
        if panel_id not in stack_ids:
            # Панель не в текущем стеке (не активна и не закреплена) —
            # действие бессмысленно без самой панели на экране.
            return
        changed = False
        for pid in stack_ids:
            target = (pid == panel_id)
            if self._collapsed.get(pid, False) == (not target):
                continue
            self._collapsed[pid] = not target
            changed = True
        if changed:
            self._refresh_all_widgets()

    def toggle_collapse(self, panel_id):
        """Стрелка ▼/▶ или двойной клик по заголовку панели."""
        self._collapsed[panel_id] = not self._collapsed.get(panel_id, False)
        self._refresh_all_widgets()

    def move_pinned(self, panel_id, direction):
        """Кнопки ↑/↓ в заголовке закреплённой панели — сдвиг в стеке.

        Заменяет перетаскивание мышью (drag-n-drop): в Tkinter
        полноценный drag по вертикальному списку требует довольно
        много кода отслеживания позиции курсора и ручной пересборки
        порядка pack(); функционально кнопки дают тот же результат —
        перемещение панели в стеке — но без риска специфичных для
        geometry-менеджера багов при пересечении с прокруткой.
        """
        if panel_id not in self.pinned_ids:
            return
        idx = self.pinned_ids.index(panel_id)
        new_idx = idx + direction
        if not (0 <= new_idx < len(self.pinned_ids)):
            return
        self.pinned_ids[idx], self.pinned_ids[new_idx] = (
            self.pinned_ids[new_idx], self.pinned_ids[idx]
        )
        self._refresh_all_widgets()

    def sync_enabled_vars(self):
        """
        Перечитывает settings для всех enabled_var, которые сейчас
        показаны в стеке. Нужно вызывать после ЛЮБОГО изменения
        settings, произошедшего не через саму панель (Undo/Redo,
        сброс, загрузка пресета).
        """
        for panel_id, var in self._enabled_vars.items():
            key = self._enabled_keys.get(panel_id)
            if key:
                var.set(bool(getattr(self.settings, key, False)))

    # ============================================================
    #  Сборка стека
    # ============================================================

    def _compute_stack_order(self):
        valid_ids = self._known_ids()
        # Чистим id, которые могли протухнуть (эффект удалён из
        # реестра) — защитная мера, реестр в этом проекте статичен,
        # но так безопаснее на будущее.
        self.pinned_ids = [pid for pid in self.pinned_ids if pid in valid_ids]

        order = []
        if self.active_id in valid_ids:
            order.append(self.active_id)
        for pid in self.pinned_ids:
            if pid != self.active_id:
                order.append(pid)
        return order

    def _reset_base_refs(self):
        """
        Публичные атрибуты, которые читает MainWindow. Валидны ТОЛЬКО
        пока соответствующая base-панель реально есть в стеке — иначе
        None. main_window.py обязан проверять на None (см. комментарий
        там же): после _refresh_all_widgets() старые виджеты уничтожены,
        и попытка обратиться к уничтоженному CTkEntry/CTkSlider уронит
        TclError.
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

    def _create_sidebar(self):
        header = ms.build_header(self, self, self.settings, self.i18n)
        self.settings_label = header["label"]
        self.style_presets_button = header["presets_button"]

        self._reset_base_refs()
        self._enabled_vars = {}
        self._enabled_keys = {}

        for panel_id in self._compute_stack_order():
            self._render_panel(panel_id)

    def _render_panel(self, panel_id):
        if panel_id in BASE_BUILDERS:
            title_key, builder_fn = BASE_BUILDERS[panel_id]
            body = self._build_panel_chrome(panel_id, title=self.i18n.tr(title_key))
            widgets = builder_fn(body, self, self.settings, self.i18n)
            self._store_base_refs(panel_id, widgets)
            if "enabled_var" in widgets:
                # Сейчас это только base.arc (arc_text_enabled).
                self._enabled_vars[panel_id] = widgets["enabled_var"]
                self._enabled_keys[panel_id] = "arc_text_enabled"
            return

        by_id = {cls.id: cls for cls in PIPELINE + POST_COMPOSE_EFFECTS}
        cls = by_id.get(panel_id)
        if cls is None:
            return

        # title=None: у эффекта уже есть своё "название" — жирный
        # чекбокс "включено" внутри build_single_effect_panel (тот же
        # текст, что был бы в заголовке). Не дублируем его отдельной
        # надписью в шапке панели — там только пин/сворачивание/порядок.
        body = self._build_panel_chrome(panel_id, title=None)
        panel = build_single_effect_panel(body, self, self.settings, self.i18n, cls)
        self._enabled_vars[panel_id] = panel["enabled_var"]
        self._enabled_keys[panel_id] = f"{panel_id}_enabled"

    def _build_panel_chrome(self, panel_id, title):
        """
        Общая "рамка" панели в стеке: заголовок (📌 + сворачивание +
        [название] + [↑↓ для закреплённых]) и body_frame под ним.
        Возвращает body_frame — содержимое достраивает вызывающая
        сторона (_render_panel).
        """
        is_active = (panel_id == self.active_id)
        is_pinned = panel_id in self.pinned_ids

        frame = ctk.CTkFrame(
            self,
            fg_color=(("#e3edf7", "#1b2a3a") if is_active else ("#e8e8e8", "#232323")),
        )
        frame.pack(fill="x", padx=6, pady=(0, 8))

        header = ctk.CTkFrame(frame, fg_color="transparent")
        header.pack(fill="x", padx=6, pady=4)

        pin_btn = ctk.CTkButton(
            header, text="📌" if is_pinned else "📍", width=26, height=22,
            font=("Segoe UI Symbol", 12),
            fg_color=("#1f538d" if is_pinned else "transparent"),
            hover_color=("#173f6b" if is_pinned else ("#d0d0d0", "#3a3a3a")),
            command=lambda pid=panel_id: self.toggle_pin(pid),
        )
        pin_btn.pack(side="left", padx=(0, 4))

        collapsed = self._collapsed.get(panel_id, False)
        arrow_btn = ctk.CTkButton(
            header, text="▶" if collapsed else "▼", width=22, height=22,
            font=("Segoe UI Symbol", 10), fg_color="transparent",
            hover_color=("#d0d0d0", "#3a3a3a"),
            command=lambda pid=panel_id: self.toggle_collapse(pid),
        )
        arrow_btn.pack(side="left", padx=(0, 6))

        if title:
            title_label = ctk.CTkLabel(header, text=title, font=("Arial", 13, "bold"), anchor="w")
            title_label.pack(side="left", fill="x", expand=True)
            title_label.bind("<Double-Button-1>", lambda e, pid=panel_id: self.toggle_collapse(pid))
        else:
            ctk.CTkFrame(header, fg_color="transparent").pack(side="left", fill="x", expand=True)
        header.bind("<Double-Button-1>", lambda e, pid=panel_id: self.toggle_collapse(pid))

        if is_pinned:
            idx = self.pinned_ids.index(panel_id)
            down_btn = ctk.CTkButton(
                header, text="↓", width=22, height=22, font=("Segoe UI Symbol", 10),
                state=("normal" if idx < len(self.pinned_ids) - 1 else "disabled"),
                command=lambda pid=panel_id: self.move_pinned(pid, 1),
            )
            down_btn.pack(side="right", padx=(2, 0))
            up_btn = ctk.CTkButton(
                header, text="↑", width=22, height=22, font=("Segoe UI Symbol", 10),
                state=("normal" if idx > 0 else "disabled"),
                command=lambda pid=panel_id: self.move_pinned(pid, -1),
            )
            up_btn.pack(side="right", padx=(2, 0))

        body_frame = ctk.CTkFrame(frame, fg_color="transparent")
        if not collapsed:
            body_frame.pack(fill="x", padx=4, pady=(0, 8))
        return body_frame
