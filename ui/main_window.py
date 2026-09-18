# -*- coding: utf-8 -*-

import os
import sys
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import numpy as np

from config import Settings

from constants import (
    APP_VERSION, APP_NAME, CONFIG_FILE, DEFAULT_FILENAME_TEMPLATE,
    PREVIEW_TEXT, IMAGE_EXTENSIONS,
    SETTINGS_HISTORY_MAX, SETTINGS_HISTORY_DEBOUNCE_MS
)
from render.composer import default_icon_font_size as _shared_default_icon_font_size

from fonts import load_font_safe, SYSTEM_FONTS
from utils import parse_characters, format_filename, get_color_rgb
from render.text import render_text_characters
from render.icons import render_icons, get_icon_mask
from render.lvgl import save_lvgl_v8_bin
from ui.sidebar import Sidebar
from ui.preview import PreviewPanel
from ui.dialogs import SettingsDialog, SystemFontPicker, StylePresetsDialog
from ui.widgets import IntSliderRow, ColorPickerButton, DirectionSelector


class MainWindow:
    """Главное окно приложения."""

    def __init__(self, root, settings):
        self.root = root
        self.settings = settings
        self.i18n = settings.i18n if hasattr(settings, 'i18n') else None

        if self.i18n is None:
            from i18n import I18n
            self.i18n = I18n(settings.language)

        self.preview_index = 0
        self.loaded_icon_paths = list(settings.icon_paths)

        # История для Undo/Redo.
        self._history = []
        self._history_index = -1
        self._history_job = None
        self._applying_history = False

        self._setup_window()
        self._create_layout()
        self._apply_settings()
        self.preview.update()

        self._history = [self.settings.to_dict()]
        self._history_index = 0
        self._update_undo_redo_buttons()

        self.root.bind_all("<Control-z>", self._undo)
        self.root.bind_all("<Control-y>", self._redo)
        self.root.bind_all("<Control-Shift-Z>", self._redo)

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self):
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1200x800")
        self.root.minsize(1050, 700)

        # 2 колонки:
        #   column 0 — центральная (topbar, chars, preview, canvas_width).
        #   column 1 — правая (Sidebar во всю высоту).
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=0)
        # 4 строки:
        #   row 0 — topbar (только column 0).
        #   row 1 — chars row (только column 0).
        #   row 2 — preview (column 0, тянется).
        #   row 3 — column 0 ПУСТАЯ (ничего туда не кладётся; в
        #     докстрине модуля раньше значилось "canvas_width_delta",
        #     но этот контрол живёт ВНУТРИ ui/preview.py::PreviewPanel,
        #     т.е. фактически в row=2 — см. исправленный докстринг
        #     выше). Строка row=3 не мёртвая: sidebar_holder занимает
        #     rowspan=4 (row 0..3) в column 1, и весь этот диапазон
        #     нужен, чтобы правая колонка растягивалась на всю высоту
        #     окна наравне с превью (row 2, weight=1).
        self.root.grid_rowconfigure(0, weight=0)
        self.root.grid_rowconfigure(1, weight=0)
        self.root.grid_rowconfigure(2, weight=1)
        self.root.grid_rowconfigure(3, weight=0)

    # ==================== LAYOUT ====================

    def _create_layout(self):
        # Верхний тулбар — только над центральной колонкой.
        self._create_top_bar(self.root)

        # Строка "Characters to generate" — только над центральной.
        self._create_characters_row(self.root)

        # Центр — превью (тянется).
        content_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        content_frame.grid(row=2, column=0, sticky="nsew", padx=15, pady=(0, 5))
        content_frame.grid_rowconfigure(0, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self.preview = PreviewPanel(content_frame, self.settings, self.i18n, self)
        self.preview.pack(fill="both", expand=True)
        self.preview.add_callback(self._on_preview_change)

        # Правая колонка — Sidebar во ВСЮ высоту окна (row 0..3).
        sidebar_holder = ctk.CTkFrame(self.root, fg_color="transparent")
        sidebar_holder.grid(row=0, column=1, rowspan=4, sticky="nsew", padx=(8, 8), pady=(8, 8))

        self.sidebar = Sidebar(sidebar_holder, self.settings, self.i18n)
        self.sidebar.pack(fill="both", expand=True)
        
        self.sidebar.add_change_callback(self._on_settings_change)
        self.sidebar.add_change_callback(self._schedule_history_snapshot)
        self.sidebar.set_settings_callback(self._open_settings)

    # ==================== TOP BAR ====================

    def _create_top_bar(self, parent):
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.grid(row=0, column=0, sticky="ew", padx=15, pady=(10, 5))

        # 0 — Текст, 1 — Иконки, 2 — Шаблон (тянется),
        # 3 — Undo, 4 — Redo, 5 — .bin, 6 — Generate (тянется).
        top_bar.grid_columnconfigure(2, weight=1)
        top_bar.grid_columnconfigure(6, weight=1)

        self.mode_text_btn = ctk.CTkButton(
            top_bar, text="📝 " + self.i18n.tr("text_mode"),
            width=100, height=32,
            command=lambda: self._set_input_mode(False),
        )
        self.mode_text_btn.grid(row=0, column=0, padx=(0, 4))

        self.mode_icon_btn = ctk.CTkButton(
            top_bar, text="🖼 " + self.i18n.tr("icon_mode"),
            width=100, height=32,
            fg_color="transparent", border_width=1,
            command=lambda: self._set_input_mode(True),
        )
        self.mode_icon_btn.grid(row=0, column=1, sticky="w", padx=(0, 12))

        template_col = ctk.CTkFrame(top_bar, fg_color="transparent")
        template_col.grid(row=0, column=2, sticky="ew", padx=(0, 8))

        ctk.CTkLabel(
            template_col, text=self.i18n.tr("filename_template") + ":",
            font=("Arial", 11),
        ).pack(anchor="w")

        self.filename_template_entry = ctk.CTkEntry(template_col, font=("Arial", 11))
        self.filename_template_entry.pack(fill="x")
        self.filename_template_entry.insert(0, self.settings.filename_template)
        self.filename_template_entry.bind(
            "<KeyRelease>", self._on_filename_template_change,
        )

        ctk.CTkLabel(
            template_col, text=self.i18n.tr("filename_template_hint"),
            font=("Arial", 9), text_color="gray",
        ).pack(anchor="w", pady=(2, 0))

        self.undo_btn = ctk.CTkButton(
            top_bar, text="↶", width=36, height=44,
            font=("Segoe UI Symbol", 18),
            fg_color=("#dbdbdb", "#2b2b2b"),
            text_color=("#1a1a1a", "#e0e0e0"),
            hover_color=("#c7c7c7", "#3a3a3a"),
            command=self._undo, state="disabled",
        )
        self.undo_btn.grid(row=0, column=3, padx=(0, 4))

        self.redo_btn = ctk.CTkButton(
            top_bar, text="↷", width=36, height=44,
            font=("Segoe UI Symbol", 18),
            fg_color=("#dbdbdb", "#2b2b2b"),
            text_color=("#1a1a1a", "#e0e0e0"),
            hover_color=("#c7c7c7", "#3a3a3a"),
            command=self._redo, state="disabled",
        )
        self.redo_btn.grid(row=0, column=4, padx=(0, 8))

        self.create_bin_var = ctk.BooleanVar(value=self.settings.create_bin)
        bin_check = ctk.CTkCheckBox(
            top_bar, text=self.i18n.tr("create_bin"),
            variable=self.create_bin_var,
            command=self._on_bin_toggle,
            checkbox_height=18, checkbox_width=18,
            font=("Arial", 12),
        )
        bin_check.grid(row=0, column=5, padx=(0, 10))

        self.generate_btn = ctk.CTkButton(
            top_bar, text="▶ " + self.i18n.tr("generate_images"),
            command=self._on_generate,
            height=44, font=("Arial", 14, "bold"),
            fg_color="#1f538d", hover_color="#14375e",
        )
        self.generate_btn.grid(row=0, column=6, sticky="ew")
    # ==================== CHARACTERS ROW ====================

    def _create_characters_row(self, parent):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=15, pady=(5, 5))
        row.grid_columnconfigure(0, weight=0)
        row.grid_columnconfigure(1, weight=1)
        row.grid_columnconfigure(2, weight=0)

        ctk.CTkLabel(
            row, text=self.i18n.tr("characters_to_generate"),
            font=("Arial", 14, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.characters_entry = ctk.CTkEntry(row, height=36, font=("Arial", 13))
        self.characters_entry.grid(row=0, column=1, sticky="ew")
        self.characters_entry.bind("<KeyRelease>", self._on_characters_change)
        self.characters_entry.bind("<Control-c>", lambda e: self._copy_selection())
        self.characters_entry.bind("<Control-v>", lambda e: self._paste_clipboard())
        self.characters_entry.bind("<Control-x>", lambda e: self._cut_selection())
        self.characters_entry.bind("<Control-a>", lambda e: self._select_all())
        self.characters_entry.bind("<Button-3>", self._show_context_menu)

        actions = ctk.CTkFrame(row, fg_color="transparent")
        actions.grid(row=0, column=2, padx=(10, 0))

        # --- Case cycle ---
        self.case_button = ctk.CTkButton(
            actions, text="Aa Ori", width=55, height=32,
            command=self._cycle_case, font=("Arial", 11, "bold"),
        )
        self.case_button.pack(side="left", padx=2)

        # --- Patterns (JSON) ---
        from constants import PATTERNS_FILE
        if os.path.exists(PATTERNS_FILE):
            try:
                import json
                with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
                    patterns = json.load(f)
                if patterns:
                    pattern_btn = ctk.CTkButton(
                        actions, text="📋", width=40, height=32,
                        command=lambda: self._show_pattern_selector(patterns),
                    )
                    pattern_btn.pack(side="left", padx=2)
            except Exception:
                pass

        json_btn = ctk.CTkButton(
            actions, text="📂", width=40, height=32,
            command=self._load_pattern_file,
        )
        json_btn.pack(side="left", padx=2)

        self.text_input_frame = row

        # --- Иконочный режим (скрыт по умолчанию) ---
        self.icon_input_frame = ctk.CTkFrame(parent, fg_color="transparent")

        icon_header = ctk.CTkFrame(self.icon_input_frame, fg_color="transparent")
        icon_header.pack(fill="x", padx=15, pady=(5, 5))

        ctk.CTkLabel(
            icon_header, text=self.i18n.tr("loaded_icons"),
            font=("Arial", 14, "bold"),
        ).pack(side="left")

        icon_actions = ctk.CTkFrame(icon_header, fg_color="transparent")
        icon_actions.pack(side="right")

        load_btn = ctk.CTkButton(
            icon_actions, text="📁 " + self.i18n.tr("load_icons"),
            width=120, height=26, command=self._load_icons,
        )
        load_btn.pack(side="left", padx=2)

        clear_btn = ctk.CTkButton(
            icon_actions, text="🗑 " + self.i18n.tr("clear"),
            width=90, height=26,
            fg_color="#8B0000", hover_color="#5C0000",
            command=self._clear_icons,
        )
        clear_btn.pack(side="left", padx=2)

        self.icon_list_frame = ctk.CTkScrollableFrame(
            self.icon_input_frame, height=90,
        )
        self.icon_list_frame.pack(fill="x", padx=15, pady=(0, 15))

        try:
            from tkinterdnd2 import DND_FILES
            self._setup_dnd()
        except ImportError:
            pass

        self._rebuild_icon_list()
        self._update_mode_buttons()

    def _on_filename_template_change(self, event):
        self.settings.filename_template = self.filename_template_entry.get()

    # ==================== DND ====================

    def _setup_dnd(self):
        try:
            from tkinterdnd2 import DND_FILES
            self.icon_list_frame.drop_target_register(DND_FILES)
            self.icon_list_frame.dnd_bind('<<Drop>>', self._on_icons_drop)
            self.icon_list_frame.dnd_bind('<<DropEnter>>', self._on_icons_drag_enter)
            self.icon_list_frame.dnd_bind('<<DropLeave>>', self._on_icons_drag_leave)

            self.icon_input_frame.drop_target_register(DND_FILES)
            self.icon_input_frame.dnd_bind('<<Drop>>', self._on_icons_drop)
            self.icon_input_frame.dnd_bind('<<DropEnter>>', self._on_icons_drag_enter)
            self.icon_input_frame.dnd_bind('<<DropLeave>>', self._on_icons_drag_leave)

            hint = ctk.CTkLabel(
                self.icon_input_frame,
                text=self.i18n.tr("drag_drop_hint"),
                font=("Arial", 10), text_color="gray",
            )
            hint.pack(anchor="w", padx=15, pady=(0, 10))
        except Exception:
            pass

    def _on_icons_drag_enter(self, event):
        self.icon_input_frame.configure(border_width=2, border_color="#1f538d")

    def _on_icons_drag_leave(self, event):
        self.icon_input_frame.configure(border_width=0)

    def _on_icons_drop(self, event):
        self._on_icons_drag_leave(event)
        try:
            raw_paths = self.root.tk.splitlist(event.data)
            image_paths = [
                p for p in raw_paths
                if os.path.isfile(p) and p.lower().endswith(IMAGE_EXTENSIONS)
            ]
            if image_paths:
                if not self.settings.icon_mode:
                    self._set_input_mode(True)
                self._add_icon_paths(image_paths)
        except Exception:
            pass

    # ==================== SETTINGS ====================

    def _apply_settings(self):
        ctk.set_appearance_mode(self.settings.theme)

        # Сбросить кэш FX-иконок: с этого момента их рендер реально
        # зависит от темы (насыщенность + базовый цвет буквы для
        # пресетов без своего text_color) — см. ui/effect_icon.py.
        # ИСПРАВЛЕНО: раньше комментарий здесь утверждал то же самое,
        # но фактически ничего не менялось при смене темы — оба
        # варианта CTkImage (light_image/dark_image) указывали на один
        # и тот же объект, а _BASE_CACHE кэшировался только по panel_id
        # без учёта темы. Проверено побайтовым сравнением пикселей.
        # Теперь оба кэша (_CTK_CACHE и _BASE_CACHE) корректно
        # учитывают тему в ключе, и clear_cache() здесь — не обязателен
        # для корректности (старые записи для другой темы просто
        # останутся неиспользуемыми в памяти), но полезен, чтобы не
        # копить обе версии сразу.
        try:
            from ui.effect_icon import clear_cache
            clear_cache()
        except ImportError:
            pass

        self._set_input_mode(self.settings.icon_mode, apply=True)

        self.characters_entry.delete(0, "end")
        self.characters_entry.insert(0, self.settings.characters)

        self.loaded_icon_paths = list(self.settings.icon_paths)
        self._rebuild_icon_list()

        self.filename_template_entry.delete(0, "end")
        self.filename_template_entry.insert(0, self.settings.filename_template)

        self.preview_index = 0

        self.sidebar._refresh_all_widgets()
        self.sidebar.refresh_fx_grid()

    def _on_settings_change(self):
        self.preview.update()
        self.sidebar.sync_enabled_vars()
        self.sidebar.refresh_fx_grid()

    def _on_preview_change(self):
        pass

    def _open_settings(self):
        dialog = SettingsDialog(self.root, self.settings, self.i18n)
        dialog.wait_window()
        self._apply_settings()
        self.preview.update()

    # ==================== INPUT MODE ====================

    def _set_input_mode(self, is_icon_mode, apply=False):
        self.settings.icon_mode = is_icon_mode

        # Секции Sidebar'а, зависящие от режима (arc скрыт
        # в иконках; содержимое font переключается), синхронизируем
        # без полной пересборки.
        try:
            self.sidebar._sync_mode_dependent_sections()
        except AttributeError:
            pass

        if is_icon_mode:
            self.text_input_frame.grid_remove()
            self.icon_input_frame.grid(row=1, column=0, sticky="ew",
                                    padx=15, pady=(5, 5))
            if self.settings.icon_font_size is None:
                default = self._default_icon_font_size()
                if default is not None:
                    self.settings.icon_font_size = default
        else:
            self.icon_input_frame.grid_remove()
            self.text_input_frame.grid()
            if self.settings.text_font_size is None:
                self.settings.text_font_size = 64

        if getattr(self.sidebar, 'font_size_entry', None) is not None:
            self.sidebar.font_size_entry.delete(0, "end")
            self.sidebar.font_size_entry.insert(0, str(self.settings.font_size))
        if getattr(self.sidebar, 'font_size_slider', None) is not None:
            self.sidebar.font_size_slider.set(self.settings.font_size)

        self._update_mode_buttons()
        self.preview_index = 0
        self.preview.update()

    def _update_mode_buttons(self):
        active_fg = "#1f538d"
        inactive_fg = ("#e2e2e2", "#3a3a3a")
        inactive_text = ("#1a1a1a", "#e0e0e0")
        inactive_border = ("#a0a0a0", "#5a5a5a")

        if self.settings.icon_mode:
            self.mode_text_btn.configure(
                fg_color=inactive_fg, border_width=1,
                text_color=inactive_text, border_color=inactive_border,
            )
            self.mode_icon_btn.configure(
                fg_color=active_fg, border_width=0, text_color="white",
            )
        else:
            self.mode_text_btn.configure(
                fg_color=active_fg, border_width=0, text_color="white",
            )
            self.mode_icon_btn.configure(
                fg_color=inactive_fg, border_width=1,
                text_color=inactive_text, border_color=inactive_border,
            )
    def _default_icon_font_size(self):
        # ИСПРАВЛЕНО: раньше здесь была ВТОРАЯ, независимая копия той же
        # формулы (с той же магической константой ICON_CANVAS_BASELINE_
        # OVERHEAD=4), которую пришлось бы обновлять синхронно с
        # render/composer.py::default_icon_font_size(). Используем ту же
        # единственную функцию, чтобы поле Size и реальный расчёт холста
        # больше не могли разойтись.
        return _shared_default_icon_font_size(self.loaded_icon_paths)

    # ==================== ICONS ====================

    def _load_icons(self):
        paths = filedialog.askopenfilenames(
            title=self.i18n.tr("load_icons"),
            filetypes=[("Image files", "*.png *.bmp *.gif *.jpg *.jpeg *.webp"),
                       ("All files", "*.*")],
        )
        if paths:
            self._add_icon_paths(list(paths))

    def _add_icon_paths(self, paths):
        if not paths:
            return

        was_empty = not self.loaded_icon_paths
        dims_before = set(self._get_icon_dims(self.loaded_icon_paths))
        added_any = False

        for p in paths:
            if p not in self.loaded_icon_paths:
                self.loaded_icon_paths.append(p)
                added_any = True

        if not added_any:
            return

        self._rebuild_icon_list()

        if was_empty and self.settings.icon_mode:
            dim = self._default_icon_font_size()
            if dim:
                self.settings.font_size = dim
                if getattr(self.sidebar, 'font_size_entry', None) is not None:
                    self.sidebar.font_size_entry.delete(0, "end")
                    self.sidebar.font_size_entry.insert(0, str(dim))
                if getattr(self.sidebar, 'font_size_slider', None) is not None:
                    self.sidebar.font_size_slider.set(dim)

        dims_after = set(self._get_icon_dims(self.loaded_icon_paths))
        if len(dims_after) > 1 and len(dims_before) <= 1:
            messagebox.showinfo(self.i18n.tr("warning"),
                                self.i18n.tr("warning_mixed_icon_sizes"))

        self.preview_index = 0
        self.preview.update()
        self.settings.icon_paths = self.loaded_icon_paths
        self.settings.save()

    def _get_icon_dims(self, paths):
        dims = []
        for p in paths:
            try:
                _, iw, ih = get_icon_mask(p)
                dims.append(max(iw, ih))
            except Exception:
                continue
        return dims

    def _remove_icon(self, path):
        if path in self.loaded_icon_paths:
            self.loaded_icon_paths.remove(path)
            self._rebuild_icon_list()
            self.preview_index = 0
            self.preview.update()
            self.settings.icon_paths = self.loaded_icon_paths
            self.settings.save()

    def _clear_icons(self):
        if not self.loaded_icon_paths:
            return
        self.loaded_icon_paths = []
        self._rebuild_icon_list()
        self.preview_index = 0
        self.preview.update()
        self.settings.icon_paths = []
        self.settings.save()

    def _rebuild_icon_list(self):
        for w in self.icon_list_frame.winfo_children():
            w.destroy()

        if not self.loaded_icon_paths:
            ctk.CTkLabel(
                self.icon_list_frame,
                text=self.i18n.tr("no_icons_loaded"),
                text_color="gray", font=("Arial", 11),
            ).pack(pady=10)
            return

        cols = 3
        for col in range(cols):
            self.icon_list_frame.grid_columnconfigure(col, weight=1)

        for idx, path in enumerate(self.loaded_icon_paths):
            row, col = divmod(idx, cols)
            chip = ctk.CTkFrame(
                self.icon_list_frame, fg_color=("#dbdbdb", "#3a3a3a"),
            )
            chip.grid(row=row, column=col, sticky="ew", padx=3, pady=3)

            name = os.path.splitext(os.path.basename(path))[0]
            ctk.CTkLabel(
                chip, text=name, anchor="w", font=("Arial", 10),
            ).pack(side="left", fill="x", expand=True, padx=(6, 2), pady=2)

            ctk.CTkButton(
                chip, text="✕", width=20, height=18,
                fg_color="transparent",
                hover_color=("#c7c7c7", "#4a4a4a"),
                command=lambda p=path: self._remove_icon(p),
            ).pack(side="right", padx=2, pady=2)

    # ==================== CHARACTERS ====================

    def _on_characters_change(self, event):
        self.settings.characters = self.characters_entry.get()
        self.preview_index = 0
        self.preview.update()

    def _cycle_case(self):
        current = self.characters_entry.get()
        if not current:
            return

        if not hasattr(self, '_case_cycler'):
            self._case_cycler = {'mode': 0, 'original': None, 'last': None}

        cycler = self._case_cycler
        modes = ["original", "upper", "lower", "title"]
        mode_names = {"original": "Ori", "upper": "UPP", "lower": "low", "title": "Tit"}

        if cycler['mode'] == 0 or current != cycler['last']:
            cycler['mode'] = 0
            cycler['original'] = current

        cycler['mode'] = (cycler['mode'] + 1) % len(modes)
        mode = modes[cycler['mode']]

        if mode == "original":
            new_text = cycler['original'] if cycler['original'] is not None else current
        elif mode == "upper":
            new_text = current.upper()
        elif mode == "lower":
            new_text = current.lower()
        else:
            new_text = current.title()

        self.characters_entry.delete(0, "end")
        self.characters_entry.insert(0, new_text)
        cycler['last'] = new_text

        self.case_button.configure(text=f"Aa\n{mode_names[mode]}")
        self._on_characters_change(None)

    # ==================== CONTEXT MENU & CLIPBOARD ====================

    def _show_context_menu(self, event):
        import tkinter as tk
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=self.i18n.tr("cut"), command=self._cut_selection)
        menu.add_command(label=self.i18n.tr("copy"), command=self._copy_selection)
        menu.add_command(label=self.i18n.tr("paste"), command=self._paste_clipboard)
        menu.add_separator()
        menu.add_command(label=self.i18n.tr("delete"), command=self._delete_selection)
        menu.add_separator()
        menu.add_command(label=self.i18n.tr("select_all"), command=self._select_all)
        menu.post(event.x_root, event.y_root)

    def _entry_widget(self):
        return getattr(self.characters_entry, "_entry", self.characters_entry)

    def _has_selection(self):
        try:
            self._entry_widget().index("sel.first")
            return True
        except Exception:
            return False

    def _copy_selection(self):
        entry = self._entry_widget()
        if not self._has_selection():
            return "break"
        try:
            text = entry.selection_get()
        except Exception:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        return "break"

    def _cut_selection(self):
        entry = self._entry_widget()
        if not self._has_selection():
            return "break"
        try:
            text = entry.selection_get()
        except Exception:
            return "break"
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        entry.delete("sel.first", "sel.last")
        self._on_characters_change(None)
        return "break"

    def _paste_clipboard(self):
        entry = self._entry_widget()
        try:
            text = self.root.clipboard_get()
        except Exception:
            return "break"
        if self._has_selection():
            entry.delete("sel.first", "sel.last")
        entry.insert("insert", text)
        self._on_characters_change(None)
        return "break"

    def _delete_selection(self):
        entry = self._entry_widget()
        if not self._has_selection():
            return
        entry.delete("sel.first", "sel.last")
        self._on_characters_change(None)

    def _select_all(self):
        self._entry_widget().select_range(0, "end")
        return "break"

    # ==================== PATTERNS ====================

    def _load_pattern_file(self):
        path = filedialog.askopenfilename(
            title=self.i18n.tr("select_pattern"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if path:
            try:
                import json
                with open(path, 'r', encoding='utf-8') as f:
                    patterns = json.load(f)
                self._show_pattern_selector(patterns)
            except Exception as e:
                messagebox.showerror(self.i18n.tr("error"), f"Failed to load: {e}")

    def _show_pattern_selector(self, patterns):
        import tkinter as tk
        selector = ctk.CTkToplevel(self.root)
        selector.title(self.i18n.tr("select_pattern"))
        selector.geometry("520x440")
        selector.transient(self.root)
        selector.grab_set()

        main = ctk.CTkFrame(selector)
        main.pack(fill="both", expand=True, padx=10, pady=10)

        top = ctk.CTkFrame(main, fg_color="transparent")
        top.pack(fill="x", pady=(0, 5))

        ctk.CTkLabel(
            top, text=self.i18n.tr("available_patterns") + ":",
            font=("Arial", 14, "bold"),
        ).pack(side="left", anchor="w")

        lang_frame = ctk.CTkFrame(top, fg_color="transparent")
        lang_frame.pack(side="right")

        ctk.CTkLabel(
            lang_frame, text=self.i18n.tr("language") + ":",
            font=("Arial", 12),
        ).pack(side="left", padx=(5, 5))

        detected_langs = set()
        for p in patterns.values():
            lang = p.get("lang", p.get("language", ""))
            if lang:
                detected_langs.add(str(lang).strip().lower())
        sorted_langs = sorted(list(detected_langs))
        combo_values = ["all"] + sorted_langs

        list_frame = ctk.CTkFrame(main)
        list_frame.pack(fill="both", expand=True, pady=5)

        scrollbar = ctk.CTkScrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")

        listbox = tk.Listbox(
            list_frame, yscrollcommand=scrollbar.set,
            height=10, font=("Arial", 12),
        )
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=listbox.yview)

        info_frame = ctk.CTkFrame(main)
        info_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            info_frame, text=self.i18n.tr("pattern_info"),
            font=("Arial", 12, "bold"),
        ).pack(anchor="w")

        info_text = tk.Text(info_frame, height=4, wrap="word", font=("Arial", 12))
        info_text.pack(fill="x")
        info_text.config(state="disabled")

        filtered_keys = []

        def update_list(selected_lang):
            nonlocal filtered_keys
            listbox.delete(0, "end")
            filtered_keys = []
            for key, pattern in patterns.items():
                p_lang = str(
                    pattern.get("lang", pattern.get("language", "all"))
                ).strip().lower()
                if selected_lang.lower() == "all" or p_lang == selected_lang.lower():
                    filtered_keys.append(key)
                    display = f"{pattern.get('name', key)} - {pattern.get('description', '')}"
                    listbox.insert("end", display)
            info_text.config(state="normal")
            info_text.delete(1.0, "end")
            info_text.config(state="disabled")

        lang_combo = ctk.CTkComboBox(
            lang_frame, values=combo_values,
            width=100, state="readonly", command=update_list,
        )
        lang_combo.set("all")
        lang_combo.pack(side="left")
        update_list("all")

        def on_select(event):
            selection = listbox.curselection()
            if selection and selection[0] < len(filtered_keys):
                key = filtered_keys[selection[0]]
                pattern = patterns[key]
                info_text.config(state="normal")
                info_text.delete(1.0, "end")
                info_text.insert("end", f"{self.i18n.tr('name')}: {pattern.get('name', key)}\n")
                info_text.insert("end", f"{self.i18n.tr('description')}: {pattern.get('description', 'N/A')}\n")
                lang = pattern.get('lang', pattern.get('language', ''))
                if lang:
                    info_text.insert("end", f"{self.i18n.tr('language')}: {lang.upper()}\n")
                chars = pattern.get('characters', '')
                preview = chars[:50] + "..." if len(chars) > 50 else chars
                info_text.insert("end", f"{self.i18n.tr('preview_pattern')}: {preview}\n")
                info_text.config(state="disabled")

        listbox.bind('<<ListboxSelect>>', on_select)

        btn_frame = ctk.CTkFrame(main)
        btn_frame.pack(fill="x", pady=10)

        def load_selected():
            selection = listbox.curselection()
            if selection and selection[0] < len(filtered_keys):
                key = filtered_keys[selection[0]]
                pattern = patterns[key]
                new_chars = pattern.get('characters', '')
                current = self.characters_entry.get()
                if current:
                    if "```" in new_chars and "```" not in current:
                        current = "```".join(current.split())
                        new_text = current + "```" + new_chars
                    elif "```" in current and "```" not in new_chars:
                        # ИСПРАВЛЕНО: обратный случай к ветке выше —
                        # текущая строка уже в "```"-формате, а новый
                        # паттерн обычный (пробельный). Раньше это
                        # попадало в else и склеивалось пробелом, из-за
                        # чего parse_characters (переключающийся на
                        # "```"-режим при наличии "```" где угодно в
                        # строке) склеивал все пробельные слова нового
                        # паттерна в один "символ". Приводим новый
                        # паттерн к тому же "```"-формату перед склейкой.
                        new_chars_joined = "```".join(new_chars.split())
                        new_text = current + "```" + new_chars_joined                        
                        
                    elif "```" in new_chars:
                        new_text = current + "```" + new_chars
                    else:
                        new_text = current + " " + new_chars
                else:
                    new_text = new_chars
                self.characters_entry.delete(0, "end")
                self.characters_entry.insert(0, new_text)
                self.preview_index = 0
                self.preview.update()
                self.settings.characters = new_text
                self.settings.save()
                selector.destroy()

        ctk.CTkButton(
            btn_frame, text=self.i18n.tr("load"),
            command=load_selected, font=("Arial", 12),
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            btn_frame, text=self.i18n.tr("cancel"),
            command=selector.destroy, font=("Arial", 12),
        ).pack(side="left", padx=5)

    # ==================== GENERATE ====================

    def _on_generate(self):
        raw = self.characters_entry.get()

        if self.settings.icon_mode:
            if not self.loaded_icon_paths:
                messagebox.showwarning(self.i18n.tr("warning"),
                                       self.i18n.tr("warning_no_icons"))
                return
        elif not raw:
            messagebox.showwarning(self.i18n.tr("warning"),
                                   self.i18n.tr("warning_no_characters"))
            return

        if not self.settings.icon_mode:
            chars = parse_characters(raw)
            if not chars:
                messagebox.showerror(self.i18n.tr("error"),
                                     self.i18n.tr("warning_no_valid"))
                return

        font_size = self.settings.font_size
        if font_size <= 0:
            messagebox.showerror(self.i18n.tr("error"),
                                 "Font size must be a positive number.")
            return

        from constants import FONT_SIZE_MAX
        if font_size > FONT_SIZE_MAX:
            font_size = FONT_SIZE_MAX
            self.settings.font_size = font_size

        self.settings.save()

        progress_window = ctk.CTkToplevel(self.root)
        progress_window.title(self.i18n.tr("generating"))
        progress_window.geometry("300x120")
        progress_window.transient(self.root)
        progress_window.grab_set()

        progress_window.update_idletasks()
        rx, ry = self.root.winfo_x(), self.root.winfo_y()
        rw, rh = self.root.winfo_width(), self.root.winfo_height()
        pw, ph = progress_window.winfo_width(), progress_window.winfo_height()
        progress_window.geometry(f"+{rx + (rw - pw)//2}+{ry + (rh - ph)//2}")

        lbl = ctk.CTkLabel(progress_window, text=self.i18n.tr("processing") + "...")
        lbl.pack(pady=(15, 5))
        bar = ctk.CTkProgressBar(progress_window, width=250)
        bar.pack(pady=5)
        bar.set(0.0)

        def update_progress(current, total):
            bar.set(current / total)
            lbl.configure(text=f"{self.i18n.tr('processing')} {current}/{total}")
            progress_window.update()

        def run_generation():
            try:
                if self.settings.icon_mode:
                    count = render_icons(
                        icon_paths=list(self.loaded_icon_paths),
                        settings=self.settings,
                        progress_callback=update_progress,
                    )
                else:
                    chars = parse_characters(raw)
                    render_text_characters(
                        characters=chars,
                        settings=self.settings,
                        progress_callback=update_progress,
                    )
                    count = len(chars)

                progress_window.destroy()

                output_dir = os.path.join(
                    os.path.dirname(os.path.abspath(__file__)), "..", "output",
                )
                messagebox.showinfo(
                    self.i18n.tr("done"),
                    self.i18n.tr("generated").format(count=count)
                    + f"\n\nSaved to:\n{output_dir}",
                )
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror(self.i18n.tr("error"),
                                     f"{self.i18n.tr('generation_failed')}: {e}")

        self.root.after(100, run_generation)

    def _on_bin_toggle(self):
        self.settings.create_bin = self.create_bin_var.get()

    # ==================== UNDO / REDO ====================

    def _schedule_history_snapshot(self):
        if self._applying_history:
            return
        if self._history_job is not None:
            try:
                self.root.after_cancel(self._history_job)
            except Exception:
                pass
        self._history_job = self.root.after(
            SETTINGS_HISTORY_DEBOUNCE_MS, self._commit_history_snapshot,
        )

    def _commit_history_snapshot(self):
        self._history_job = None
        snapshot = self.settings.to_dict()
        if snapshot == self._history[self._history_index]:
            return
        self._history = self._history[:self._history_index + 1]
        self._history.append(snapshot)
        if len(self._history) > SETTINGS_HISTORY_MAX:
            self._history = self._history[-SETTINGS_HISTORY_MAX:]
        self._history_index = len(self._history) - 1
        self._update_undo_redo_buttons()

    def _undo(self, event=None):
        if self._history_index <= 0:
            return "break"
        self._history_index -= 1
        self._restore_history_snapshot(self._history[self._history_index])
        return "break"

    def _redo(self, event=None):
        if self._history_index >= len(self._history) - 1:
            return "break"
        self._history_index += 1
        self._restore_history_snapshot(self._history[self._history_index])
        return "break"

    def _restore_history_snapshot(self, snapshot):
        self._applying_history = True
        try:
            self.settings.from_dict(snapshot)
            self.sidebar._refresh_all_widgets()
            self.sidebar.refresh_fx_grid()
            self.preview.update()
            self._update_undo_redo_buttons()
        finally:
            self._applying_history = False

    def _update_undo_redo_buttons(self):
        self.undo_btn.configure(
            state="normal" if self._history_index > 0 else "disabled",
        )
        self.redo_btn.configure(
            state="normal" if self._history_index < len(self._history) - 1 else "disabled",
        )

    # ==================== CLOSE ====================

    def _on_close(self):
        self.settings.save()
        self.root.destroy()