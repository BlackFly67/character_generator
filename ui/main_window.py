# -*- coding: utf-8 -*-
"""
Главное окно приложения
"""

import os
import sys
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import numpy as np

from config import Settings
from constants import (
    APP_VERSION, APP_NAME, CONFIG_FILE, DEFAULT_FILENAME_TEMPLATE,
    PREVIEW_TEXT, ICON_CANVAS_BASELINE_OVERHEAD, IMAGE_EXTENSIONS
)
from fonts import load_font_safe, SYSTEM_FONTS
from utils import parse_characters, format_filename, get_color_rgb
from render.text import render_text_characters
from render.icons import render_icons, get_icon_mask, default_icon_font_size
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

        # Переменные состояния
        self.preview_index = 0
        self.text_font_size = settings.text_font_size
        self.icon_font_size = settings.icon_font_size
        self.loaded_icon_paths = list(settings.icon_paths)

        # Настройка окна
        self._setup_window()

        # Создание интерфейса
        self._create_layout()

        # Загрузка состояния
        self._apply_settings()

        # Обновление превью
        self.preview.update()

        # Обработчик закрытия
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self):
        self.root.title(f"{APP_NAME} {APP_VERSION}")
        self.root.geometry("1050x750")
        self.root.minsize(950, 650)

        self.root.grid_columnconfigure(0, weight=0)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_rowconfigure(0, weight=1)

    # ==================== LAYOUT ====================

    def _create_layout(self):
        # Боковая панель
        self.sidebar = Sidebar(self.root, self.settings, self.i18n)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.add_change_callback(self._on_settings_change)

        # Основная область
        content_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        content_frame.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
        content_frame.grid_rowconfigure(1, weight=1)
        content_frame.grid_columnconfigure(0, weight=1)

        self._create_input_panel(content_frame)
        self._create_bottom_bar(content_frame)

        # Превью
        self.preview = PreviewPanel(content_frame, self.settings, self.i18n, self)
        self.preview.pack(fill="both", expand=True, pady=(0, 10))
        self.preview.add_callback(self._on_preview_change)

    # ==================== INPUT PANEL ====================

    def _create_input_panel(self, parent):
        self.char_frame = ctk.CTkFrame(parent)
        self.char_frame.pack(fill="x", pady=(0, 10))

        # --- Переключатель режимов ---
        mode_row = ctk.CTkFrame(self.char_frame, fg_color="transparent")
        mode_row.pack(fill="x", padx=15, pady=(10, 0))

        self.mode_text_btn = ctk.CTkButton(
            mode_row, text="📝 " + self.i18n.tr("text_mode"),
            width=110, height=26,
            command=lambda: self._set_input_mode(False)
        )
        self.mode_text_btn.pack(side="left", padx=(0, 2))

        self.mode_icon_btn = ctk.CTkButton(
            mode_row, text="🖼 " + self.i18n.tr("icon_mode"),
            width=110, height=26,
            fg_color="transparent", border_width=1,
            command=lambda: self._set_input_mode(True)
        )
        self.mode_icon_btn.pack(side="left", padx=(0, 15))

        # --- Шаблон имени файла ---
        template_col = ctk.CTkFrame(mode_row, fg_color="transparent")
        template_col.pack(side="left", fill="x", expand=True)

        template_row = ctk.CTkFrame(template_col, fg_color="transparent")
        template_row.pack(fill="x")

        ctk.CTkLabel(template_row, text=self.i18n.tr("filename_template") + ":",
                    font=("Arial", 11)).pack(side="left")

        self.filename_template_entry = ctk.CTkEntry(
            template_row, font=("Arial", 11)
        )
        self.filename_template_entry.pack(side="left", fill="x", expand=True, padx=(8, 0))
        self.filename_template_entry.insert(0, self.settings.filename_template)
        self.filename_template_entry.bind("<KeyRelease>", self._on_filename_template_change)

        ctk.CTkLabel(template_col, text=self.i18n.tr("filename_template_hint"),
                    font=("Arial", 9), text_color="gray").pack(anchor="w", pady=(2, 0))

        # --- Текстовый режим ---
        self.text_input_frame = ctk.CTkFrame(self.char_frame, fg_color="transparent")

        header = ctk.CTkFrame(self.text_input_frame, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(header, text=self.i18n.tr("characters_to_generate"),
                    font=("Arial", 14, "bold")).pack(side="left")

        actions = ctk.CTkFrame(header, fg_color="transparent")
        actions.pack(side="right")

        self.case_button = ctk.CTkButton(
            actions, text="Aa Ori", width=55, height=26,
            command=self._cycle_case, font=("Arial", 11, "bold")
        )
        self.case_button.pack(side="left", padx=2)

        from constants import PATTERNS_FILE
        if os.path.exists(PATTERNS_FILE):
            try:
                import json
                with open(PATTERNS_FILE, 'r', encoding='utf-8') as f:
                    patterns = json.load(f)
                if patterns:
                    pattern_btn = ctk.CTkButton(
                        actions, text="📋 " + self.i18n.tr("select_pattern"),
                        width=110, height=26,
                        command=lambda: self._show_pattern_selector(patterns)
                    )
                    pattern_btn.pack(side="left", padx=2)
            except Exception:
                pass

        json_btn = ctk.CTkButton(
            actions, text="📂 JSON", width=70, height=26,
            command=self._load_pattern_file
        )
        json_btn.pack(side="left", padx=2)

        self.characters_entry = ctk.CTkEntry(
            self.text_input_frame, height=40, font=("Arial", 14)
        )
        self.characters_entry.pack(fill="x", padx=15, pady=(0, 15))
        self.characters_entry.bind("<KeyRelease>", self._on_characters_change)
        self.characters_entry.bind("<Control-c>", lambda e: self.characters_entry.event_generate("<<Cut>>"))
        self.characters_entry.bind("<Control-v>", lambda e: self.characters_entry.event_generate("<<Paste>>"))
        self.characters_entry.bind("<Control-x>", lambda e: self.characters_entry.event_generate("<<Cut>>"))
        self.characters_entry.bind("<Control-a>", lambda e: self.characters_entry.select_range(0, "end"))
        self.characters_entry.bind("<Button-3>", self._show_context_menu)

        self.text_input_frame.pack(fill="x")

        # --- Иконочный режим ---
        self.icon_input_frame = ctk.CTkFrame(self.char_frame, fg_color="transparent")

        icon_header = ctk.CTkFrame(self.icon_input_frame, fg_color="transparent")
        icon_header.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(icon_header, text=self.i18n.tr("loaded_icons"),
                    font=("Arial", 14, "bold")).pack(side="left")

        icon_actions = ctk.CTkFrame(icon_header, fg_color="transparent")
        icon_actions.pack(side="right")

        load_btn = ctk.CTkButton(
            icon_actions, text="📁 " + self.i18n.tr("load_icons"),
            width=120, height=26, command=self._load_icons
        )
        load_btn.pack(side="left", padx=2)

        clear_btn = ctk.CTkButton(
            icon_actions, text="🗑 " + self.i18n.tr("clear"),
            width=90, height=26,
            fg_color="#8B0000", hover_color="#5C0000",
            command=self._clear_icons
        )
        clear_btn.pack(side="left", padx=2)

        self.icon_list_frame = ctk.CTkScrollableFrame(self.icon_input_frame, height=90)
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
        # settings.save() — только по кнопке Generate

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
                font=("Arial", 10), text_color="gray"
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
            image_paths = [p for p in raw_paths if os.path.isfile(p) and
                          p.lower().endswith(IMAGE_EXTENSIONS)]
            if image_paths:
                if not self.settings.icon_mode:
                    self._set_input_mode(True)
                self._add_icon_paths(image_paths)
        except Exception:
            pass

    # ==================== BOTTOM BAR ====================

    def _create_bottom_bar(self, parent):
        bottom_bar = ctk.CTkFrame(parent, fg_color="transparent")
        bottom_bar.pack(side="bottom", fill="x", pady=5)
        bottom_bar.grid_columnconfigure(0, weight=0)
        bottom_bar.grid_columnconfigure(1, weight=1)
        bottom_bar.grid_columnconfigure(2, weight=0)

        self.create_bin_var = ctk.BooleanVar(value=self.settings.create_bin)
        bin_check = ctk.CTkCheckBox(
            bottom_bar,
            text=self.i18n.tr("create_bin"),
            variable=self.create_bin_var,
            command=self._on_bin_toggle,
            checkbox_height=18, checkbox_width=18
        )
        bin_check.grid(row=0, column=0, sticky="w", padx=(0, 10))

        self.generate_btn = ctk.CTkButton(
            bottom_bar,
            text=self.i18n.tr("generate_images"),
            command=self._on_generate,
            height=50, font=("Arial", 16, "bold"),
            fg_color="#1f538d", hover_color="#14375e"
        )
        self.generate_btn.grid(row=0, column=1, sticky="ew", padx=(0, 10))

        settings_btn = ctk.CTkButton(
            bottom_bar, text="⚙", width=50, height=50,
            font=("Segoe UI Symbol", 20),
            fg_color=("#dbdbdb", "#2b2b2b"),
            text_color=("#1a1a1a", "#e0e0e0"),
            hover_color=("#c7c7c7", "#3a3a3a"),
            command=self._open_settings
        )
        settings_btn.grid(row=0, column=2, sticky="e")

    # ==================== SETTINGS ====================

    def _apply_settings(self):
        ctk.set_appearance_mode(self.settings.theme)

        self.settings.icon_mode = self.settings.icon_mode
        self._set_input_mode(self.settings.icon_mode, apply=True)

        self.characters_entry.delete(0, "end")
        self.characters_entry.insert(0, self.settings.characters)

        self.loaded_icon_paths = list(self.settings.icon_paths)
        self._rebuild_icon_list()

        self.filename_template_entry.delete(0, "end")
        self.filename_template_entry.insert(0, self.settings.filename_template)

        self.preview_index = 0

        self.sidebar._refresh_all_widgets()

    def _on_settings_change(self):
        self.preview.update()

    def _on_preview_change(self):
        pass

    def _open_settings(self):
        dialog = SettingsDialog(self.root, self.settings, self.i18n)
        dialog.wait_window()
        self._apply_settings()
        self.preview.update()

    # ==================== INPUT MODE ====================

    def _set_input_mode(self, is_icon_mode, apply=False):
        """
        FIX: раньше здесь читались self.preview.font_size_entry и
        self.preview.font_size_slider — этих виджетов в PreviewPanel нет,
        они живут в Sidebar. Из-за hasattr() исключения не было, но и
        значение никогда не читалось/не обновлялось — переключение режима
        фактически игнорировало размер. Теперь работаем с
        self.sidebar.font_size_entry / self.sidebar.font_size_slider.
        """
        if not apply:
            # Запоминаем текущий размер для ПРЕДЫДУЩЕГО режима
            current_size = self.settings.font_size
            try:
                if hasattr(self.sidebar, 'font_size_entry'):
                    raw = self.sidebar.font_size_entry.get().strip()
                    if raw:
                        current_size = int(raw)
            except (ValueError, AttributeError):
                pass

            if self.settings.icon_mode:
                self.icon_font_size = current_size
            else:
                self.text_font_size = current_size

        self.settings.icon_mode = is_icon_mode

        if is_icon_mode:
            self.text_input_frame.pack_forget()
            self.icon_input_frame.pack(fill="x")

            size_val = self.icon_font_size
            if size_val is None:
                size_val = self._default_icon_font_size()
            if size_val is None:
                size_val = 64
            self.icon_font_size = size_val
            self.settings.font_size = size_val
        else:
            self.icon_input_frame.pack_forget()
            self.text_input_frame.pack(fill="x")

            size_val = self.text_font_size if self.text_font_size is not None else 64
            self.settings.font_size = size_val

        # Обновляем виджеты размера в сайдбаре
        if hasattr(self.sidebar, 'font_size_entry'):
            self.sidebar.font_size_entry.delete(0, "end")
            self.sidebar.font_size_entry.insert(0, str(self.settings.font_size))
        if hasattr(self.sidebar, 'font_size_slider'):
            self.sidebar.font_size_slider.set(self.settings.font_size)

        self._update_mode_buttons()
        self.preview_index = 0
        self.sidebar._refresh_all_widgets()
        self.preview.update()

    def _update_mode_buttons(self):
        active_fg = "#1f538d"
        inactive_fg = ("#e2e2e2", "#3a3a3a")
        inactive_text = ("#1a1a1a", "#e0e0e0")
        inactive_border = ("#a0a0a0", "#5a5a5a")

        if self.settings.icon_mode:
            self.mode_text_btn.configure(fg_color=inactive_fg, border_width=1,
                                         text_color=inactive_text, border_color=inactive_border)
            self.mode_icon_btn.configure(fg_color=active_fg, border_width=0, text_color="white")
        else:
            self.mode_text_btn.configure(fg_color=active_fg, border_width=0, text_color="white")
            self.mode_icon_btn.configure(fg_color=inactive_fg, border_width=1,
                                         text_color=inactive_text, border_color=inactive_border)

    def _default_icon_font_size(self):
        if not self.loaded_icon_paths:
            return None
        try:
            _, iw, ih = get_icon_mask(self.loaded_icon_paths[0])
            native_max = max(iw, ih)
            return max(1, native_max - ICON_CANVAS_BASELINE_OVERHEAD)
        except Exception:
            return None

    # ==================== ICONS ====================

    def _load_icons(self):
        paths = filedialog.askopenfilenames(
            title=self.i18n.tr("load_icons"),
            filetypes=[("Image files", "*.png *.bmp *.gif *.jpg *.jpeg *.webp"),
                      ("All files", "*.*")]
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
                self.icon_font_size = dim
                self.settings.font_size = dim
                # FIX: размер живёт в сайдбаре, не в preview
                if hasattr(self.sidebar, 'font_size_entry'):
                    self.sidebar.font_size_entry.delete(0, "end")
                    self.sidebar.font_size_entry.insert(0, str(dim))
                if hasattr(self.sidebar, 'font_size_slider'):
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
            ctk.CTkLabel(self.icon_list_frame, text=self.i18n.tr("no_icons_loaded"),
                        text_color="gray", font=("Arial", 11)).pack(pady=10)
            return

        cols = 3
        for col in range(cols):
            self.icon_list_frame.grid_columnconfigure(col, weight=1)

        for idx, path in enumerate(self.loaded_icon_paths):
            row, col = divmod(idx, cols)
            chip = ctk.CTkFrame(self.icon_list_frame, fg_color=("#dbdbdb", "#3a3a3a"))
            chip.grid(row=row, column=col, sticky="ew", padx=3, pady=3)

            name = os.path.splitext(os.path.basename(path))[0]
            ctk.CTkLabel(chip, text=name, anchor="w", font=("Arial", 10)).pack(
                side="left", fill="x", expand=True, padx=(6, 2), pady=2
            )

            ctk.CTkButton(
                chip, text="✕", width=20, height=18,
                fg_color="transparent",
                hover_color=("#c7c7c7", "#4a4a4a"),
                command=lambda p=path: self._remove_icon(p)
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

    def _show_context_menu(self, event):
        import tkinter as tk
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label=self.i18n.tr("cut"), command=lambda: self.characters_entry.event_generate("<<Cut>>"))
        menu.add_command(label=self.i18n.tr("copy"), command=lambda: self.characters_entry.event_generate("<<Copy>>"))
        menu.add_command(label=self.i18n.tr("paste"), command=lambda: self.characters_entry.event_generate("<<Paste>>"))
        menu.add_separator()
        menu.add_command(label=self.i18n.tr("delete"), command=lambda: self.characters_entry.delete("sel.first", "sel.last"))
        menu.add_separator()
        menu.add_command(label=self.i18n.tr("select_all"), command=lambda: self.characters_entry.select_range(0, "end"))
        menu.post(event.x_root, event.y_root)

    # ==================== PATTERNS ====================

    def _load_pattern_file(self):
        path = filedialog.askopenfilename(
            title=self.i18n.tr("select_pattern"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
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

        ctk.CTkLabel(top, text=self.i18n.tr("available_patterns") + ":",
                    font=("Arial", 14, "bold")).pack(side="left", anchor="w")

        lang_frame = ctk.CTkFrame(top, fg_color="transparent")
        lang_frame.pack(side="right")

        ctk.CTkLabel(lang_frame, text=self.i18n.tr("language") + ":",
                    font=("Arial", 12)).pack(side="left", padx=(5, 5))

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

        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                            height=10, font=("Arial", 12))
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.configure(command=listbox.yview)

        info_frame = ctk.CTkFrame(main)
        info_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(info_frame, text=self.i18n.tr("pattern_info"),
                    font=("Arial", 12, "bold")).pack(anchor="w")

        info_text = tk.Text(info_frame, height=4, wrap="word", font=("Arial", 12))
        info_text.pack(fill="x")
        info_text.config(state="disabled")

        filtered_keys = []

        def update_list(selected_lang):
            nonlocal filtered_keys
            listbox.delete(0, "end")
            filtered_keys = []
            for key, pattern in patterns.items():
                p_lang = str(pattern.get("lang", pattern.get("language", "all"))).strip().lower()
                if selected_lang.lower() == "all" or p_lang == selected_lang.lower():
                    filtered_keys.append(key)
                    display = f"{pattern.get('name', key)} - {pattern.get('description', '')}"
                    listbox.insert("end", display)
            info_text.config(state="normal")
            info_text.delete(1.0, "end")
            info_text.config(state="disabled")

        lang_combo = ctk.CTkComboBox(lang_frame, values=combo_values,
                                     width=100, state="readonly",
                                     command=update_list)
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

        ctk.CTkButton(btn_frame, text=self.i18n.tr("load"),
                     command=load_selected, font=("Arial", 12)).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text=self.i18n.tr("cancel"),
                     command=selector.destroy, font=("Arial", 12)).pack(side="left", padx=5)

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

        # FIX: размер читаем из settings (его синхронизирует sidebar),
        # а не из self.preview.font_size_entry, которого больше нет.
        font_size = self.settings.font_size
        if font_size <= 0:
            messagebox.showerror(self.i18n.tr("error"), "Font size must be a positive number.")
            return

        from constants import FONT_SIZE_MAX
        if font_size > FONT_SIZE_MAX:
            font_size = FONT_SIZE_MAX
            self.settings.font_size = font_size

        # Сохраняем всё состояние настроек на диск по кнопке Generate
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
                        progress_callback=update_progress
                    )
                else:
                    chars = parse_characters(raw)
                    render_text_characters(
                        characters=chars,
                        settings=self.settings,
                        progress_callback=update_progress
                    )
                    count = len(chars)

                progress_window.destroy()

                output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "output")
                messagebox.showinfo(
                    self.i18n.tr("done"),
                    self.i18n.tr("generated").format(count=count) + f"\n\nSaved to:\n{output_dir}"
                )
            except Exception as e:
                progress_window.destroy()
                messagebox.showerror(self.i18n.tr("error"),
                                    f"{self.i18n.tr('generation_failed')}: {e}")

        self.root.after(100, run_generation)

    def _on_bin_toggle(self):
        self.settings.create_bin = self.create_bin_var.get()

    # ==================== CLOSE ====================

    def _on_close(self):
        self.settings.save()
        self.root.destroy()