# -*- coding: utf-8 -*-
"""
Панель предпросмотра.
- Единый compose_full из render.composer.
- Общий холст для батча текста/дуги.
- У иконок — свой холст на каждую.
- Зум, скролл колесом, панорама зажатой ЛКМ.
- Debounce рендера (40 мс).
- Строка ширины холста под окном превью.
"""

import hashlib
import json
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from constants import PREVIEW_TEXT
from utils import parse_characters, create_checkerboard_background
from render.composer import (
    CharSpec, compose_full, compute_batch_geometry,
)


# Явный список полей settings, влияющих на изображение превью.
SIGNATURE_KEYS = [
    "font_path", "font_size", "text_color", "text_opacity", "text_scale_x",
    "letter_spacing", "text_alignment", "transparent_text",
    "transparent_background", "background_color", "cutout_mode",
    "canvas_width_enabled", "canvas_width_delta",
    "gradient_enabled", "gradient_stops", "gradient_type", "gradient_angle",
    "pattern_enabled", "pattern_image_path", "pattern_scale",
    "pattern_offset_x", "pattern_offset_y", "pattern_angle", "pattern_blend_mode",
    "outline_outer_enabled", "outline_outer_color", "outline_outer_width",
    "outline_inner_enabled", "outline_inner_color", "outline_inner_width",
    "glow_outer_enabled", "glow_outer_color", "glow_outer_radius", "glow_outer_intensity",
    "glow_inner_enabled", "glow_inner_color", "glow_inner_radius", "glow_inner_intensity",
    "glow_inner_blend_mode",
    "shadow_enabled", "shadow_color", "shadow_distance", "shadow_direction",
    "shadow_blur", "shadow_blend_mode",
    "inner_shadow_enabled", "inner_shadow_color", "inner_shadow_distance",
    "inner_shadow_direction", "inner_shadow_blur", "inner_shadow_blend_mode",
    "emboss_enabled", "emboss_depth", "emboss_blur", "emboss_angle",
    "emboss_highlight", "emboss_shadow",
    "rotation_angle",
    "skew_enabled", "skew_x", "skew_y",
    "perspective_enabled", "perspective_x", "perspective_y",
    "arc_text_enabled", "arc_radius", "arc_start_angle",
    "arc_clockwise", "arc_flip",
    "halftone_enabled", "halftone_cell_size", "halftone_dot_scale", "halftone_angle",
    "reflection_enabled", "reflection_gap", "reflection_opacity", "reflection_fade",
    "glitch_enabled", "glitch_rgb_shift", "glitch_slice_intensity", "glitch_seed",
    "icon_mode",
]


class PreviewPanel(ctk.CTkFrame):
    def __init__(self, parent, settings, i18n, main_window):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.main_window = main_window

        self.zoom = 100
        self.current_index = 0
        self._callbacks = []

        # Кэш реального изображения (до зума)
        self._cached_full_image = None
        self._cached_signature = None
        self._cached_is_transparent_bg = False

        # Для canvas-вьюпорта
        self._display_photo = None
        self._canvas_img_id = None
        self._drag_start = None
        self._display_size = (0, 0)

        # Debounce рендера
        self._render_job = None

        self._create_widgets()

    def add_callback(self, callback):
        self._callbacks.append(callback)

    # ============================================================
    #  Виджеты
    # ============================================================

    def _create_widgets(self):
        # --- Строка 1: Preview + навигация + зум ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(10, 5))

        ctk.CTkLabel(header, text=self.i18n.tr("preview"),
                     font=("Arial", 14, "bold")).pack(side="left")

        nav = ctk.CTkFrame(header, fg_color="transparent")
        nav.pack(side="right")

        ctk.CTkButton(nav, text="◀", width=32, height=26,
                      font=("Arial", 12, "bold"),
                      command=self._prev).pack(side="left", padx=(0, 6))

        self.index_label = ctk.CTkLabel(nav, text="1/1",
                                         font=("Arial", 11), width=48)
        self.index_label.pack(side="left")

        ctk.CTkButton(nav, text="▶", width=32, height=26,
                      font=("Arial", 12, "bold"),
                      command=self._next).pack(side="left", padx=(6, 0))

        zoom_frame = ctk.CTkFrame(header, fg_color="transparent")
        zoom_frame.pack(side="right", padx=(0, 14))

        ctk.CTkLabel(zoom_frame, text="🔍",
                     font=("Arial", 12)).pack(side="left", padx=(0, 4))

        self.zoom_slider = ctk.CTkSlider(
            zoom_frame, from_=10, to=1000,
            number_of_steps=990, width=110,
            command=self._on_zoom,
        )
        self.zoom_slider.set(100)
        self.zoom_slider.pack(side="left")

        self.zoom_entry = ctk.CTkEntry(zoom_frame, width=48)
        self.zoom_entry.insert(0, "100")
        self.zoom_entry.pack(side="left", padx=(4, 2))
        self.zoom_entry.bind("<KeyRelease>", self._on_zoom_entry)

        ctk.CTkLabel(zoom_frame, text="%",
                     font=("Arial", 11)).pack(side="left")

        # --- Область превью (canvas + скроллбары) ---
        self.center_frame = ctk.CTkFrame(
            self,
            fg_color="#1a1a1a" if ctk.get_appearance_mode() == "Dark" else "#e5e5e5",
        )
        self.center_frame.pack(fill="both", expand=True, padx=15, pady=(0, 5))
        self.center_frame.pack_propagate(False)

        self.center_frame.grid_rowconfigure(0, weight=1)
        self.center_frame.grid_columnconfigure(0, weight=1)

        is_dark = ctk.get_appearance_mode() == "Dark"
        canvas_bg = "#1a1a1a" if is_dark else "#e5e5e5"

        self.canvas = tk.Canvas(
            self.center_frame,
            bg=canvas_bg,
            highlightthickness=0,
            bd=0,
        )
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.vbar = ctk.CTkScrollbar(self.center_frame, orientation="vertical",
                                      command=self.canvas.yview)
        self.vbar.grid(row=0, column=1, sticky="ns")

        self.hbar = ctk.CTkScrollbar(self.center_frame, orientation="horizontal",
                                      command=self.canvas.xview)
        self.hbar.grid(row=1, column=0, sticky="ew")

        self.canvas.configure(yscrollcommand=self.vbar.set,
                              xscrollcommand=self.hbar.set)

        # --- События мыши ---
        self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
        self.canvas.bind("<B1-Motion>", self._on_drag_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)
        self.canvas.bind("<MouseWheel>", self._on_wheel)
        self.canvas.bind("<Button-4>", self._on_wheel_linux_up)
        self.canvas.bind("<Button-5>", self._on_wheel_linux_down)
        self.canvas.bind("<Shift-MouseWheel>", self._on_wheel_shift)
        self.canvas.bind("<Control-MouseWheel>", self._on_wheel_ctrl)

        # --- Строка 2: Ширина холста (delta) ---
        canvas_row = ctk.CTkFrame(self, fg_color="transparent")
        canvas_row.pack(fill="x", padx=15, pady=(0, 10))

        self.canvas_width_enabled_var = ctk.BooleanVar(
            value=getattr(self.settings, "canvas_width_enabled", False)
        )
        self.canvas_width_check = ctk.CTkCheckBox(
            canvas_row,
            text=self.i18n.tr("canvas_width_delta"),
            variable=self.canvas_width_enabled_var,
            command=self._on_canvas_width_toggle,
            checkbox_height=18, checkbox_width=18,
        )
        self.canvas_width_check.pack(side="left")

        current_delta = getattr(self.settings, "canvas_width_delta",
                                getattr(self.settings, "canvas_width", 0))

        self.canvas_width_entry = ctk.CTkEntry(canvas_row, width=50)
        self.canvas_width_entry.insert(0, str(current_delta))
        self.canvas_width_entry.pack(side="left", padx=(10, 5))
        self.canvas_width_entry.bind("<KeyRelease>", self._on_canvas_width_change)

        ctk.CTkLabel(canvas_row, text="px",
                     font=("Arial", 10)).pack(side="left")

        self.canvas_width_slider = ctk.CTkSlider(
            canvas_row, from_=-1000, to=1000, number_of_steps=2000,
            width=140,
        )
        self.canvas_width_slider.pack(side="left", padx=(10, 0))
        self.canvas_width_slider.set(current_delta)
        self.canvas_width_slider.configure(command=self._on_canvas_width_slider)

        ctk.CTkFrame(canvas_row, fg_color="transparent", height=1).pack(
            side="left", fill="x", expand=True
        )

        self.bind("<Configure>", lambda e: self.update())

    # ============================================================
    #  Обработчики ширины холста
    # ============================================================

    def _on_canvas_width_toggle(self):
        self.settings.canvas_width_enabled = self.canvas_width_enabled_var.get()
        self.update()

    def _on_canvas_width_change(self, event):
        try:
            val = int(self.canvas_width_entry.get())
            val = max(-1000, min(1000, val))
            self.canvas_width_slider.set(val)
            self.settings.canvas_width_delta = val
            self.update()
        except ValueError:
            pass

    def _on_canvas_width_slider(self, value):
        val = int(value)
        self.canvas_width_entry.delete(0, "end")
        self.canvas_width_entry.insert(0, str(val))
        self.settings.canvas_width_delta = val
        self.update()

    # ============================================================
    #  Навигация
    # ============================================================

    def _prev(self):
        self.current_index -= 1
        self.update()

    def _next(self):
        self.current_index += 1
        self.update()

    # ============================================================
    #  Зум
    # ============================================================

    def _on_zoom(self, value):
        self.zoom = int(value)
        self.zoom_entry.delete(0, "end")
        self.zoom_entry.insert(0, str(self.zoom))
        self._draw_zoomed()

    def _on_zoom_entry(self, event):
        try:
            v = int(self.zoom_entry.get())
            v = max(10, min(1000, v))
            self.zoom = v
            self.zoom_slider.set(v)
            self._draw_zoomed()
        except ValueError:
            pass

    def _set_zoom(self, value):
        v = max(10, min(1000, int(value)))
        self.zoom = v
        self.zoom_slider.set(v)
        self.zoom_entry.delete(0, "end")
        self.zoom_entry.insert(0, str(v))
        self._draw_zoomed()

    # ============================================================
    #  Мышь
    # ============================================================

    def _on_drag_start(self, event):
        self.canvas.scan_mark(event.x, event.y)
        self.canvas.configure(cursor="fleur")

    def _on_drag_move(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def _on_drag_end(self, event):
        self.canvas.configure(cursor="")

    def _on_wheel(self, event):
        if event.state & 0x0004:
            self._zoom_at_cursor(event, +120 if event.delta > 0 else -120)
            return
        self.canvas.yview_scroll(int(-event.delta / 120), "units")

    def _on_wheel_shift(self, event):
        self.canvas.xview_scroll(int(-event.delta / 120), "units")

    def _on_wheel_ctrl(self, event):
        self._zoom_at_cursor(event, +120 if event.delta > 0 else -120)

    def _on_wheel_linux_up(self, event):
        self.canvas.yview_scroll(-1, "units")

    def _on_wheel_linux_down(self, event):
        self.canvas.yview_scroll(+1, "units")

    def _zoom_at_cursor(self, event, delta):
        old_zoom = self.zoom
        self._set_zoom(self.zoom + (50 if delta > 0 else -50))
        if old_zoom == self.zoom:
            return
        try:
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            sx = cx / max(1, self._display_size[0])
            sy = cy / max(1, self._display_size[1])
            self.canvas.xview_moveto(max(0.0, sx - event.x / max(1, self._display_size[0])))
            self.canvas.yview_moveto(max(0.0, sy - event.y / max(1, self._display_size[1])))
        except Exception:
            pass

    # ============================================================
    #  Перерисовка (с debounce)
    # ============================================================

    def update(self):
        """
        Debounce: откладываем пересчёт на 40 мс. При быстрых вызовах
        (движение окна, набор текста, перетаскивание слайдера) делается
        только один финальный рендер вместо десятков промежуточных.
        """
        if self._render_job is not None:
            try:
                self.after_cancel(self._render_job)
            except Exception:
                pass
        self._render_job = self.after(40, self._render_preview_now)

    def _render_preview_now(self):
        """Отрабатывает отложенный рендер."""
        self._render_job = None

        try:
            if not self.winfo_exists():
                return
        except Exception:
            return

        try:
            self._render_preview()
        except Exception as e:
            import traceback
            print(f"Preview error: {e}")
            traceback.print_exc()

    def _get_all_specs(self):
        icon_paths = getattr(self.main_window, 'loaded_icon_paths', [])
        if self.settings.icon_mode and icon_paths:
            # ИСПРАВЛЕНО: enumerate(icon_paths, 1) вместо enumerate(icon_paths) —
            # render_icons в render/icons.py нумерует иконки с 1
            # (enumerate(icon_paths, 1)). spec.index используется в
            # compose_full для seed эффекта Glitch (glitch_seed + spec.index).
            # При 0-based индексации в превью и 1-based при реальном
            # рендере seed для одного и того же символа/иконки не совпадал,
            # и превью показывало не тот узор глитча, который окажется в
            # сохранённом файле.
            return [CharSpec(icon_path=p, index=i)
                    for i, p in enumerate(icon_paths, 1)]

        entry = getattr(self.main_window, 'characters_entry', None)
        raw = entry.get() if entry else ""
        chars = parse_characters(raw) if raw else parse_characters(PREVIEW_TEXT)
        if not chars:
            chars = parse_characters(PREVIEW_TEXT)
        # ИСПРАВЛЕНО: аналогично — render_text_characters в render/text.py
        # нумерует символы с 1 (enumerate(characters, 1)).
        return [CharSpec(text=ch, index=i) for i, ch in enumerate(chars, 1)]

    def _signature(self, spec, all_specs):
        d = {k: getattr(self.settings, k, None) for k in SIGNATURE_KEYS}
        d["_spec_text"] = spec.text
        d["_spec_icon"] = spec.icon_path
        d["_spec_index"] = spec.index
        d["_batch_size"] = len(all_specs)
        d["_batch_keys"] = [
            s.text if s.text is not None else s.icon_path
            for s in all_specs
        ]
        s = json.dumps(d, sort_keys=True, default=str)
        return hashlib.md5(s.encode("utf-8")).hexdigest()

    def _render_preview(self):
        all_specs = self._get_all_specs()
        total = len(all_specs)
        self.current_index %= total
        spec = all_specs[self.current_index]
        self.index_label.configure(text=f"{self.current_index + 1}/{total}")

        sig = self._signature(spec, all_specs)
        if sig != self._cached_signature or self._cached_full_image is None:
            if self.settings.icon_mode:
                self._cached_full_image = compose_full(spec, self.settings)
            else:
                batch_geom = compute_batch_geometry(all_specs, self.settings)
                self._cached_full_image = compose_full(
                    spec, self.settings, geom=batch_geom
                )
            self._cached_signature = sig
            self._cached_is_transparent_bg = self.settings.transparent_background
            self.canvas.xview_moveto(0)
            self.canvas.yview_moveto(0)

        self._draw_zoomed()

    def _draw_zoomed(self):
        if self._cached_full_image is None:
            return

        full = self._cached_full_image
        z = self.zoom / 100.0
        target_w = max(1, int(round(full.width * z)))
        target_h = max(1, int(round(full.height * z)))

        if (target_w, target_h) == full.size:
            display = full
        else:
            display = full.resize((target_w, target_h), Image.Resampling.LANCZOS)

        if self._cached_is_transparent_bg:
            bg = create_checkerboard_background(display.width, display.height, 6)
            bg.alpha_composite(display)
            display = bg

        framed = self._draw_blueprint(display, full.width, full.height)
        self._display_size = framed.size

        from PIL import ImageTk
        self._display_photo = ImageTk.PhotoImage(framed)

        self.canvas.delete("all")
        self._canvas_img_id = self.canvas.create_image(
            0, 0, anchor="nw", image=self._display_photo
        )
        self.canvas.configure(scrollregion=(0, 0, framed.width, framed.height))

    def _draw_blueprint(self, img, real_w, real_h):
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#1a1a1a" if is_dark else "#e5e5e5"
        line_color = "#555555" if is_dark else "#888888"
        text_color = "#aaaaaa" if is_dark else "#444444"

        pad = 45
        cw = img.width + pad * 2
        ch = img.height + pad * 2

        canvas = Image.new("RGBA", (cw, ch), bg_color)
        canvas.alpha_composite(img, (pad, pad))
        d = ImageDraw.Draw(canvas)

        x1, y1 = pad, pad
        x2, y2 = pad + img.width, pad + img.height

        d.rectangle([x1, y1, x2, y2], outline=line_color, width=1)
        d.line([x1, 25, x2, 25], fill=line_color, width=1)
        d.line([x1, 20, x1, 30], fill=line_color, width=1)
        d.line([x2, 20, x2, 30], fill=line_color, width=1)
        d.line([25, y1, 25, y2], fill=line_color, width=1)
        d.line([20, y1, 30, y1], fill=line_color, width=1)
        d.line([20, y2, 30, y2], fill=line_color, width=1)

        try:
            font = ImageFont.truetype("arial.ttf", 11)
        except Exception:
            font = ImageFont.load_default()

        w_text = f"{real_w} px"
        w_box = d.textbbox((0, 0), w_text, font=font)
        d.text(((x1 + x2 - (w_box[2] - w_box[0])) / 2, 10),
               w_text, fill=text_color, font=font)

        h_text = f"{real_h} px"
        h_box = d.textbbox((0, 0), h_text, font=font)
        d.text((2, (y1 + y2 - (h_box[3] - h_box[1])) / 2),
               h_text, fill=text_color, font=font)

        return canvas