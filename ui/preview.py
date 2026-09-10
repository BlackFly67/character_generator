# -*- coding: utf-8 -*-
"""
Панель предпросмотра. Использует единый compose_full из render.composer.
Значения читаются напрямую из self.settings (сайдбар их синхронизирует).
"""

import hashlib
import json
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from constants import PREVIEW_TEXT, FONT_SIZE_MIN, FONT_SIZE_MAX
from utils import parse_characters, create_checkerboard_background
from render.composer import CharSpec, compose_full


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

        self._create_widgets()

    def add_callback(self, callback):
        self._callbacks.append(callback)

    def _create_widgets(self):
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

        self.center_frame = ctk.CTkFrame(
            self,
            fg_color="#1a1a1a" if ctk.get_appearance_mode() == "Dark" else "#e5e5e5",
        )
        self.center_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

        self.image_label = ctk.CTkLabel(self.center_frame, text="")
        self.image_label.pack(expand=True)

        self.bind("<Configure>", lambda e: self._draw_zoomed())

    # --- Навигация ---
    def _prev(self):
        self.current_index -= 1
        self.update()

    def _next(self):
        self.current_index += 1
        self.update()

    # --- Зум ---
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

    # --- Перерисовка ---
    def update(self):
        try:
            self._render_preview()
        except Exception as e:
            import traceback
            print(f"Preview error: {e}")
            traceback.print_exc()

    def _get_current_spec(self):
        icon_paths = getattr(self.main_window, 'loaded_icon_paths', [])
        if self.settings.icon_mode and icon_paths:
            total = len(icon_paths)
            self.current_index %= total
            spec = CharSpec(icon_path=icon_paths[self.current_index],
                            index=self.current_index)
            return spec, total

        entry = getattr(self.main_window, 'characters_entry', None)
        raw = entry.get() if entry else ""
        chars = parse_characters(raw) if raw else parse_characters(PREVIEW_TEXT)
        if not chars:
            chars = parse_characters(PREVIEW_TEXT)
        total = len(chars)
        self.current_index %= total
        spec = CharSpec(text=chars[self.current_index], index=self.current_index)
        return spec, total

    def _signature(self, spec):
        d = {}
        for k, v in vars(self.settings).items():
            if k.startswith("_") or callable(v):
                continue
            try:
                json.dumps(v, default=str)
                d[k] = v
            except (TypeError, ValueError):
                d[k] = str(v)
        d["_spec_text"] = spec.text
        d["_spec_icon"] = spec.icon_path
        d["_spec_index"] = spec.index
        s = json.dumps(d, sort_keys=True, default=str)
        return hashlib.md5(s.encode("utf-8")).hexdigest()

    def _render_preview(self):
        spec, total = self._get_current_spec()
        self.index_label.configure(text=f"{self.current_index + 1}/{total}")

        sig = self._signature(spec)
        if sig != self._cached_signature or self._cached_full_image is None:
            self._cached_full_image = compose_full(spec, self.settings)
            self._cached_signature = sig
            self._cached_is_transparent_bg = self.settings.transparent_background

        self._draw_zoomed()

    def _draw_zoomed(self):
        if self._cached_full_image is None:
            return

        full = self._cached_full_image
        z = self.zoom / 100.0
        if z == 1.0:
            display = full
        else:
            w = max(1, int(round(full.width * z)))
            h = max(1, int(round(full.height * z)))
            display = full.resize((w, h), Image.Resampling.LANCZOS)

        if self._cached_is_transparent_bg:
            bg = create_checkerboard_background(display.width, display.height, 6)
            bg.alpha_composite(display)
            display = bg

        final = self._draw_blueprint(display, full.width, full.height)
        ctk_img = ctk.CTkImage(light_image=final, dark_image=final, size=final.size)
        self.image_label.configure(image=ctk_img, text="")
        self.image_label.image = ctk_img

    def _draw_blueprint(self, img, real_w, real_h):
        """Рамка + размеры вокруг изображения."""
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
        # Верхняя риска
        d.line([x1, 25, x2, 25], fill=line_color, width=1)
        d.line([x1, 20, x1, 30], fill=line_color, width=1)
        d.line([x2, 20, x2, 30], fill=line_color, width=1)
        # Левая риска
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