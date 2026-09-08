# -*- coding: utf-8 -*-
"""
Диалоговые окна
"""

import os
import json
import customtkinter as ctk
from tkinter import filedialog, messagebox
from PIL import Image, ImageTk

from fonts import SYSTEM_FONTS, tk_style_from_font_style
from constants import STYLE_PRESETS_FILE, STYLE_PRESET_KEYS
from utils import create_checkerboard_background, get_color_rgba
from ui.widgets import ColorPickerButton


def ask_color(parent, initial_color, title, i18n):
    """
    Открывает диалог выбора цвета.
    """
    try:
        from ctk_color_picker import askcolor
        color = askcolor(parent, initial=initial_color, title=title)
        return color
    except ImportError:
        from tkinter import colorchooser
        color = colorchooser.askcolor(title=title, initialcolor=initial_color)
        return color[1] if color else None


class SettingsDialog(ctk.CTkToplevel):
    """Окно настроек (язык, тема)."""
    
    def __init__(self, parent, settings, i18n):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        
        self.title("⚙ " + i18n.tr("settings"))
        self.geometry("300x200")
        self.resizable(False, False)
        self.transient(parent)
        self.attributes("-topmost", True)
        
        # Центрируем
        self.update_idletasks()
        px, py = parent.winfo_x(), parent.winfo_y()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        self.geometry(f"+{px + (pw - 300)//2}+{py + (ph - 200)//2}")
        
        self._create_widgets()
    
    def _create_widgets(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Язык
        ctk.CTkLabel(frame, text=self.i18n.tr("language") + ":", 
                    font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 2))
        
        self.lang_combo = ctk.CTkComboBox(
            frame, values=self.i18n.get_languages(), 
            state="readonly", command=self._on_language_change
        )
        self.lang_combo.set(self.settings.language)
        self.lang_combo.pack(fill="x", pady=(0, 15))
        
        # Тема
        ctk.CTkLabel(frame, text=self.i18n.tr("theme") + ":", 
                    font=("Arial", 12, "bold")).pack(anchor="w", pady=(0, 2))
        
        self.theme_combo = ctk.CTkComboBox(
            frame, values=["Light", "Dark", "System"],
            state="readonly", command=self._on_theme_change
        )
        self.theme_combo.set(self.settings.theme.capitalize())
        self.theme_combo.pack(fill="x", pady=(0, 10))
    
    def _on_language_change(self, lang):
        if self.i18n.set_language(lang):
            self.settings.language = lang
            self.settings.save()
            self.destroy()
    
    def _on_theme_change(self, theme):
        theme_lower = theme.lower()
        ctk.set_appearance_mode(theme_lower)
        self.settings.theme = theme_lower
        self.settings.save()
        self.destroy()


class SystemFontPicker(ctk.CTkToplevel):
    """Окно выбора системного шрифта."""
    
    def __init__(self, parent, settings, i18n):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        
        self.title(i18n.tr("system_font"))
        self.geometry("380x480")
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
    
    def _create_widgets(self):
        # Поиск
        self.search_entry = ctk.CTkEntry(self, placeholder_text=self.i18n.tr("system_font_search"))
        self.search_entry.pack(fill="x", padx=10, pady=(10, 5))
        self.search_entry.bind("<KeyRelease>", self._on_search)
        
        # Список
        self.list_container = ctk.CTkScrollableFrame(self)
        self.list_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        
        self._rebuild_list()
    
    def _on_search(self, event):
        self._rebuild_list()
    
    def _rebuild_list(self):
        """Обновляет список шрифтов."""
        for w in self.list_container.winfo_children():
            w.destroy()
        
        filter_text = self.search_entry.get().lower().strip()
        
        for name, info in SYSTEM_FONTS.items():
            if filter_text and filter_text not in name.lower():
                continue
            
            style_words = tk_style_from_font_style(info.get("style", ""))
            try:
                item_font = (info["family"], 13) + style_words
            except Exception:
                item_font = ("Arial", 13)
            
            row = ctk.CTkLabel(
                self.list_container,
                text=name,
                font=item_font,
                anchor="w",
                fg_color="transparent"
            )
            row.pack(fill="x", padx=2, pady=1)
            row.bind("<Button-1>", lambda e, n=name: self._select(n))
            row.bind("<Enter>", lambda e, r=row: r.configure(fg_color=("#dbdbdb", "#3a3a3a")))
            row.bind("<Leave>", lambda e, r=row: r.configure(fg_color="transparent"))
    
    def _select(self, name):
        """Выбирает шрифт."""
        if name in SYSTEM_FONTS:
            self.settings.font_path = SYSTEM_FONTS[name]["path"]
            self.destroy()


class GradientStopEditor(ctk.CTkFrame):
    """Редактор точек градиента."""
    
    def __init__(self, parent, stops, on_change):
        super().__init__(parent, fg_color="transparent")
        self.stops = stops
        self.on_change = on_change
        self.selected_index = None
        self.photo = None
        
        import tkinter as tk
        self.canvas = tk.Canvas(self, height=40, highlightthickness=1,
                               highlightbackground="#555555", bg="#2b2b2b")
        self.canvas.pack(fill="x", pady=(2, 8))
        
        self.canvas.bind("<Button-1>", self._on_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        
        self._redraw()
    
    def _redraw(self):
        """Перерисовывает градиент и точки."""
        self.canvas.delete("all")
        w = max(self.canvas.winfo_width(), 10)
        h = max(self.canvas.winfo_height(), 30)
        ramp_h = max(1, int(h * 0.6))
        
        sorted_stops = sorted(self.stops, key=lambda s: s["pos"])
        ramp_w = max(w, 2)
        ramp_h2 = max(ramp_h, 2)
        
        # Рисуем градиент
        from effects.gradient import sample_gradient_color
        row = [sample_gradient_color(sorted_stops, x / max(1, ramp_w - 1)) 
               for x in range(ramp_w)]
        
        ramp_rgba = Image.new("RGBA", (ramp_w, ramp_h2))
        ramp_rgba.putdata(row * ramp_h2)
        checker = create_checkerboard_background(ramp_w, ramp_h2, cell_size=6)
        ramp = Image.alpha_composite(checker, ramp_rgba).convert("RGB")
        
        self.photo = ImageTk.PhotoImage(ramp)
        self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
        
        # Рисуем точки
        for i, stop in enumerate(self.stops):
            x = int(stop["pos"] * w)
            outline = "#ffffff" if i == self.selected_index else "#000000"
            r, g, b, a = get_color_rgba(stop["color"])
            marker_fill = "" if a == 0 else "#{:02x}{:02x}{:02x}".format(r, g, b)
            self.canvas.create_polygon(
                x - 6, h, x + 6, h, x, ramp_h + 2,
                fill=marker_fill,
                outline=outline, width=2,
                dash=(None if a == 255 else (3, 2))
            )
    
    def _get_stop_at(self, x, w):
        """Находит точку градиента по координате."""
        if not self.stops:
            return None
        best_idx, best_dist = None, None
        for i, stop in enumerate(self.stops):
            dist = abs(stop["pos"] * w - x)
            if best_dist is None or dist < best_dist:
                best_idx, best_dist = i, dist
        return best_idx if best_dist is not None and best_dist <= 10 else None
    
    def _on_click(self, event):
        w = max(self.canvas.winfo_width(), 1)
        idx = self._get_stop_at(event.x, w)
        if idx is not None:
            self.selected_index = idx
        else:
            # Добавляем новую точку
            from effects.gradient import sample_gradient_color
            t = max(0.0, min(1.0, event.x / w))
            sorted_stops = sorted(self.stops, key=lambda s: s["pos"])
            r, g, b, a = sample_gradient_color(sorted_stops, t)
            color = "#{:02x}{:02x}{:02x}".format(r, g, b)
            if a < 255:
                color += "{:02x}".format(a)
            self.stops.append({"pos": t, "color": color})
            self.selected_index = len(self.stops) - 1
            self.on_change(self.stops)
        self._redraw()
    
    def _on_drag(self, event):
        if self.selected_index is None:
            return
        w = max(self.canvas.winfo_width(), 1)
        t = max(0.0, min(1.0, event.x / w))
        self.stops[self.selected_index]["pos"] = t
        self._redraw()
    
    def _on_release(self, event):
        self.on_change(self.stops)
    
    def _on_double_click(self, event):
        w = max(self.canvas.winfo_width(), 1)
        idx = self._get_stop_at(event.x, w)
        if idx is None:
            return
        
        self.selected_index = idx
        color = self.stops[idx]["color"]
        
        # Открываем диалог выбора цвета
        try:
            from ctk_color_picker import askcolor
            new_color = askcolor(self, initial=color, title="Select Gradient Color")
            if new_color:
                self.stops[idx]["color"] = new_color
                self.on_change(self.stops)
                self._redraw()
        except ImportError:
            from tkinter import colorchooser
            new_color = colorchooser.askcolor(title="Select Gradient Color", 
                                             initialcolor=color)
            if new_color and new_color[1]:
                self.stops[idx]["color"] = new_color[1]
                self.on_change(self.stops)
                self._redraw()
    
    def _on_right_click(self, event):
        if len(self.stops) <= 2:
            return
        w = max(self.canvas.winfo_width(), 1)
        idx = self._get_stop_at(event.x, w)
        if idx is None:
            return
        del self.stops[idx]
        self.selected_index = None
        self.on_change(self.stops)
        self._redraw()


class StylePresetsDialog(ctk.CTkToplevel):
    """Окно управления пресетами стиля."""
    
    def __init__(self, parent, settings, i18n):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        
        self.title(i18n.tr("style_presets"))
        self.geometry("380x500")
        self.transient(parent)
        self.grab_set()
        
        self._create_widgets()
        self._rebuild_list()
    
    def _create_widgets(self):
        """Создаёт виджеты."""
        main = ctk.CTkFrame(self)
        main.pack(fill="both", expand=True, padx=10, pady=10)
        
        ctk.CTkLabel(main, text=self.i18n.tr("style_presets"),
                    font=("Arial", 14, "bold")).pack(anchor="w", pady=(0, 10))
        
        # Сохранение
        save_row = ctk.CTkFrame(main, fg_color="transparent")
        save_row.pack(fill="x", pady=(0, 5))
        
        self.name_entry = ctk.CTkEntry(save_row, placeholder_text=self.i18n.tr("style_preset_name"))
        self.name_entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        
        save_btn = ctk.CTkButton(save_row, text=self.i18n.tr("save"), width=70,
                                command=self._save_preset)
        save_btn.pack(side="left")
        
        # Импорт
        import_row = ctk.CTkFrame(main, fg_color="transparent")
        import_row.pack(fill="x", pady=(0, 10))
        
        import_btn = ctk.CTkButton(import_row, text="📥 " + self.i18n.tr("import_from_file"),
                                  command=self._import_preset)
        import_btn.pack(side="left", fill="x", expand=True)
        
        # Список пресетов
        self.list_frame = ctk.CTkScrollableFrame(main)
        self.list_frame.pack(fill="both", expand=True)
    
    def _rebuild_list(self):
        """Обновляет список пресетов."""
        for w in self.list_frame.winfo_children():
            w.destroy()
        
        try:
            with open(STYLE_PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            presets = {}
        
        if not presets:
            ctk.CTkLabel(self.list_frame, text=self.i18n.tr("no_style_presets"),
                        text_color="gray").pack(pady=20)
            return
        
        for name in sorted(presets.keys(), key=str.lower):
            row = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row, text=name, anchor="w").pack(side="left", fill="x", expand=True, padx=(2, 5))
            
            # Load
            ctk.CTkButton(row, text=self.i18n.tr("load"), width=60, height=26,
                         command=lambda n=name: self._load_preset(n)).pack(side="left", padx=2)
            
            # Export
            ctk.CTkButton(row, text="📤", width=30, height=26,
                         command=lambda n=name: self._export_preset(n)).pack(side="left", padx=2)
            
            # Delete
            ctk.CTkButton(row, text="🗑", width=30, height=26,
                         fg_color="#8B0000", hover_color="#5C0000",
                         command=lambda n=name: self._delete_preset(n)).pack(side="left")
    
    def _save_preset(self):
        """Сохраняет текущие настройки как пресет."""
        name = self.name_entry.get().strip()
        if not name:
            return
        
        # Проверяем, существует ли пресет
        try:
            with open(STYLE_PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            presets = {}
        
        if name in presets:
            if not messagebox.askyesno(self.i18n.tr("warning"),
                                       self.i18n.tr("overwrite_style_confirm").format(name=name)):
                return
        
        # Сохраняем
        style_dict = {}
        for key in STYLE_PRESET_KEYS:
            if hasattr(self.settings, key):
                style_dict[key] = getattr(self.settings, key)
        
        presets[name] = style_dict
        
        try:
            with open(STYLE_PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        
        self.name_entry.delete(0, "end")
        self._rebuild_list()
    
    def _load_preset(self, name):
        """Загружает пресет."""
        try:
            with open(STYLE_PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            return
        
        style_dict = presets.get(name)
        if not style_dict:
            return
        
        for key, value in style_dict.items():
            if hasattr(self.settings, key):
                setattr(self.settings, key, value)
        
        self.settings.save()
        self.destroy()
    
    def _export_preset(self, name):
        """Экспортирует пресет в файл."""
        try:
            with open(STYLE_PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            return
        
        style_dict = presets.get(name)
        if not style_dict:
            return
        
        path = filedialog.asksaveasfilename(
            title=self.i18n.tr("export_style_preset"),
            defaultextension=".json",
            initialfile=name.replace(" ", "_") + ".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not path:
            return
        
        payload = {"type": "style_preset", "name": name, "style": style_dict}
        
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
            messagebox.showinfo(self.i18n.tr("done"), self.i18n.tr("export_success"))
        except Exception as e:
            messagebox.showerror(self.i18n.tr("error"), str(e))
    
    def _import_preset(self):
        """Импортирует пресет из файла."""
        path = filedialog.askopenfilename(
            title=self.i18n.tr("import_style_preset"),
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if not path:
            return
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                payload = json.load(f)
        except Exception as e:
            messagebox.showerror(self.i18n.tr("error"), 
                                f"{self.i18n.tr('invalid_style_preset_file')}\n{e}")
            return
        
        # Определяем формат
        name, style_dict = None, None
        
        if isinstance(payload, dict):
            if isinstance(payload.get("style"), dict):
                # Наш формат
                style_dict = payload["style"]
                name = payload.get("name")
            elif len(payload) == 1:
                # Одиночный пресет
                only_name, only_value = next(iter(payload.items()))
                if isinstance(only_value, dict):
                    name, style_dict = only_name, only_value
            elif len(payload) > 1 and all(isinstance(v, dict) for v in payload.values()):
                messagebox.showerror(self.i18n.tr("error"), 
                                    self.i18n.tr("multiple_presets_in_file"))
                return
            elif any(k in STYLE_PRESET_KEYS for k in payload.keys()):
                style_dict = payload
        
        if not isinstance(style_dict, dict):
            messagebox.showerror(self.i18n.tr("error"), 
                                self.i18n.tr("invalid_style_preset_file"))
            return
        
        name = str(name or "").strip() or os.path.splitext(os.path.basename(path))[0]
        
        # Фильтруем только известные ключи
        sanitized = {k: style_dict[k] for k in STYLE_PRESET_KEYS if k in style_dict}
        
        if not sanitized:
            messagebox.showerror(self.i18n.tr("error"), 
                                self.i18n.tr("invalid_style_preset_file"))
            return
        
        try:
            with open(STYLE_PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            presets = {}
        
        if name in presets:
            if not messagebox.askyesno(self.i18n.tr("warning"),
                                       self.i18n.tr("overwrite_style_confirm").format(name=name)):
                return
        
        presets[name] = sanitized
        
        try:
            with open(STYLE_PRESETS_FILE, 'w', encoding='utf-8') as f:
                json.dump(presets, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        
        messagebox.showinfo(self.i18n.tr("done"), self.i18n.tr("style_preset_imported"))
        self._rebuild_list()
    
    def _delete_preset(self, name):
        """Удаляет пресет."""
        if not messagebox.askyesno(self.i18n.tr("warning"),
                                   self.i18n.tr("delete_style_confirm").format(name=name)):
            return
        
        try:
            with open(STYLE_PRESETS_FILE, 'r', encoding='utf-8') as f:
                presets = json.load(f)
        except Exception:
            return
        
        if name in presets:
            del presets[name]
            try:
                with open(STYLE_PRESETS_FILE, 'w', encoding='utf-8') as f:
                    json.dump(presets, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        
        self._rebuild_list()