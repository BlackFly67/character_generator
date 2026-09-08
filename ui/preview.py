# -*- coding: utf-8 -*-
"""
Панель предпросмотра - ПОЛНАЯ РАБОЧАЯ ВЕРСИЯ
"""


import math
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops
import numpy as np
import tkinter as tk
import os
import json
import sys

from utils import (
    create_checkerboard_background, get_color_rgb, get_color_rgba,
    get_shadow_offset, blend_layers, rotate_cleanly, parse_characters,
    format_filename, make_safe_filename
)
from fonts import load_font_safe, SYSTEM_FONTS  # <-- ПРАВИЛЬНЫЙ ИМПОРТ
from constants import PREVIEW_TEXT, FONT_SIZE_MIN, FONT_SIZE_MAX
from effects import *
from render.arc import render_arc_text_mask
from render.icons import get_icon_mask


class PreviewPanel(ctk.CTkFrame):
    """Панель предпросмотра."""
    
    def __init__(self, parent, settings, i18n, main_window):
        super().__init__(parent)
        self.settings = settings
        self.i18n = i18n
        self.main_window = main_window
        self.zoom = 100
        self.current_index = 0
        self._callbacks = []
        self.preview_letters_cache = {}
        self.gradient_stops_photo = None
        
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
        
        self.prev_btn = ctk.CTkButton(nav, text="◀", width=32, height=26,
                     font=("Arial", 12, "bold"),
                     command=self._prev)
        self.prev_btn.pack(side="left", padx=(0, 6))
        
        self.index_label = ctk.CTkLabel(nav, text="1/1",
                                       font=("Arial", 11), width=48)
        self.index_label.pack(side="left")
        
        self.next_btn = ctk.CTkButton(nav, text="▶", width=32, height=26,
                     font=("Arial", 12, "bold"),
                     command=self._next)
        self.next_btn.pack(side="left", padx=(6, 0))
        
        zoom_frame = ctk.CTkFrame(header, fg_color="transparent")
        zoom_frame.pack(side="right", padx=(0, 14))
        
        ctk.CTkLabel(zoom_frame, text="🔍",
                    font=("Arial", 12)).pack(side="left", padx=(0, 4))
        
        self.zoom_slider = ctk.CTkSlider(
            zoom_frame, from_=0, to=1000,
            number_of_steps=1000, width=110,
            command=self._on_zoom
        )
        self.zoom_slider.set(100)
        self.zoom_slider.pack(side="left")
        
        self.zoom_entry = ctk.CTkEntry(zoom_frame, width=44)
        self.zoom_entry.insert(0, "100")
        self.zoom_entry.pack(side="left", padx=(4, 2))
        self.zoom_entry.bind("<KeyRelease>", self._on_zoom_entry)
        
        ctk.CTkLabel(zoom_frame, text="%",
                    font=("Arial", 11)).pack(side="left")
        
        self.center_frame = ctk.CTkFrame(
            self,
            fg_color="#1a1a1a" if ctk.get_appearance_mode() == "Dark" else "#e5e5e5"
        )
        self.center_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))
        
        self.image_label = ctk.CTkLabel(self.center_frame, text="")
        self.image_label.pack(expand=True)
        
        self.font_size_entry = ctk.CTkEntry(self, width=55)
        self.font_size_entry.insert(0, str(self.settings.font_size))
        self.font_size_entry.bind("<KeyRelease>", self._on_font_size_change)
        
        self.font_size_slider = ctk.CTkSlider(
            self, from_=FONT_SIZE_MIN, to=FONT_SIZE_MAX,
            number_of_steps=FONT_SIZE_MAX - FONT_SIZE_MIN,
            command=self._on_font_size_slider
        )
        self.font_size_slider.set(self.settings.font_size)
        
        self.bind("<Configure>", lambda e: self.update())
    
    def _prev(self):
        self.current_index -= 1
        self.update()
    
    def _next(self):
        self.current_index += 1
        self.update()
    
    def _on_zoom(self, value):
        self.zoom = int(value)
        self.zoom_entry.delete(0, "end")
        self.zoom_entry.insert(0, str(self.zoom))
        self.update()
    
    def _on_zoom_entry(self, event):
        try:
            val = int(self.zoom_entry.get())
            val = max(0, min(1000, val))
            self.zoom = val
            self.zoom_slider.set(val)
            self.update()
        except ValueError:
            pass
    
    def _on_font_size_change(self, event):
        try:
            raw = self.font_size_entry.get().strip()
            if not raw:
                return
            val = int(raw)
            val = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, val))
            self.font_size_entry.delete(0, "end")
            self.font_size_entry.insert(0, str(val))
            self.font_size_slider.set(val)
            self.settings.font_size = val
            self.settings.save()
            self.update()
        except ValueError:
            pass
    
    def _on_font_size_slider(self, value):
        val = int(value)
        val = max(FONT_SIZE_MIN, min(FONT_SIZE_MAX, val))
        self.font_size_entry.delete(0, "end")
        self.font_size_entry.insert(0, str(val))
        self.settings.font_size = val
        self.settings.save()
        self.update()
    
    def _get_icon_paths(self):
        if self.main_window and hasattr(self.main_window, 'loaded_icon_paths'):
            return self.main_window.loaded_icon_paths
        return []
    
    def _get_sidebar(self):
        if self.main_window and hasattr(self.main_window, 'sidebar'):
            return self.main_window.sidebar
        return None
    
    def _safe_get_int(self, entry, default_val):
        try:
            if entry is None:
                return default_val
            val = entry.get().strip()
            return int(val) if val else default_val
        except (ValueError, AttributeError):
            return default_val
    
    def _safe_get_var(self, var, default_val=False):
        try:
            if var is None:
                return default_val
            return var.get()
        except Exception:
            return default_val
    
    def update(self):
        try:
            self._render_preview()
        except Exception as e:
            print(f"Preview error: {e}")
            import traceback
            traceback.print_exc()
    
    def _render_preview(self):
        """ОРИГИНАЛЬНАЯ update_preview из create_char_gui(571b).py"""
        
        # === ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ===
        def safe_get_int(entry, default_val, requires_var=None):
            try:
                if entry is None:
                    return default_val
                val = entry.get().strip()
                if not val:
                    return default_val
                if requires_var is not None and not requires_var.get():
                    return 0
                return int(val)
            except (ValueError, AttributeError):
                return default_val
        
        # === ПОЛУЧАЕМ SIDEBAR ===
        sidebar = self._get_sidebar()
        if sidebar is None:
            return
        
        # === ПОЛУЧАЕМ ВСЕ ПЕРЕМЕННЫЕ ИЗ SIDEBAR ===
        shadow_distance_entry = getattr(sidebar, 'shadow_distance_row', None)
        shadow_distance_entry = shadow_distance_entry.entry if shadow_distance_entry else None
        shadow_blur_entry = getattr(sidebar, 'shadow_blur_row', None)
        shadow_blur_entry = shadow_blur_entry.entry if shadow_blur_entry else None
        shadow_var = getattr(sidebar, 'shadow_var', None)
        shadow_direction_var = getattr(sidebar, 'shadow_dir_var', None)
        shadow_blend_mode_var = getattr(sidebar, 'shadow_blend_var', None)
        
        rotation_entry = getattr(sidebar, 'rotation_row', None)
        rotation_entry = rotation_entry.entry if rotation_entry else None
        
        skew_x_entry = getattr(sidebar, 'skew_x_row', None)
        skew_x_entry = skew_x_entry.entry if skew_x_entry else None
        skew_y_entry = getattr(sidebar, 'skew_y_row', None)
        skew_y_entry = skew_y_entry.entry if skew_y_entry else None
        skew_enabled_var = getattr(sidebar, 'skew_var', None)
        
        perspective_x_entry = getattr(sidebar, 'perspective_x_row', None)
        perspective_x_entry = perspective_x_entry.entry if perspective_x_entry else None
        perspective_y_entry = getattr(sidebar, 'perspective_y_row', None)
        perspective_y_entry = perspective_y_entry.entry if perspective_y_entry else None
        perspective_enabled_var = getattr(sidebar, 'perspective_var', None)
        
        emboss_depth_entry = getattr(sidebar, 'emboss_depth_row', None)
        emboss_depth_entry = emboss_depth_entry.entry if emboss_depth_entry else None
        emboss_blur_entry = getattr(sidebar, 'emboss_blur_row', None)
        emboss_blur_entry = emboss_blur_entry.entry if emboss_blur_entry else None
        emboss_enabled_var = getattr(sidebar, 'emboss_var', None)
        
        outline_outer_width_entry = getattr(sidebar, 'outline_outer_width_row', None)
        outline_outer_width_entry = outline_outer_width_entry.entry if outline_outer_width_entry else None
        outline_outer_enabled_var = getattr(sidebar, 'outline_outer_var', None)
        outline_inner_width_entry = getattr(sidebar, 'outline_inner_width_row', None)
        outline_inner_width_entry = outline_inner_width_entry.entry if outline_inner_width_entry else None
        outline_inner_enabled_var = getattr(sidebar, 'outline_inner_var', None)
        
        glow_outer_radius_entry = getattr(sidebar, 'glow_outer_radius_row', None)
        glow_outer_radius_entry = glow_outer_radius_entry.entry if glow_outer_radius_entry else None
        glow_outer_intensity_entry = getattr(sidebar, 'glow_outer_intensity_row', None)
        glow_outer_intensity_entry = glow_outer_intensity_entry.entry if glow_outer_intensity_entry else None
        glow_outer_enabled_var = getattr(sidebar, 'glow_outer_var', None)
        glow_inner_radius_entry = getattr(sidebar, 'glow_inner_radius_row', None)
        glow_inner_radius_entry = glow_inner_radius_entry.entry if glow_inner_radius_entry else None
        glow_inner_intensity_entry = getattr(sidebar, 'glow_inner_intensity_row', None)
        glow_inner_intensity_entry = glow_inner_intensity_entry.entry if glow_inner_intensity_entry else None
        glow_inner_enabled_var = getattr(sidebar, 'glow_inner_var', None)
        glow_inner_blend_mode_var = getattr(sidebar, 'glow_inner_blend_var', None)
        
        inner_shadow_distance_entry = getattr(sidebar, 'inner_shadow_distance_row', None)
        inner_shadow_distance_entry = inner_shadow_distance_entry.entry if inner_shadow_distance_entry else None
        inner_shadow_blur_entry = getattr(sidebar, 'inner_shadow_blur_row', None)
        inner_shadow_blur_entry = inner_shadow_blur_entry.entry if inner_shadow_blur_entry else None
        inner_shadow_enabled_var = getattr(sidebar, 'inner_shadow_var', None)
        inner_shadow_direction_var = getattr(sidebar, 'inner_shadow_dir_var', None)
        inner_shadow_blend_mode_var = getattr(sidebar, 'inner_shadow_blend_var', None)
        
        arc_radius_entry = getattr(sidebar, 'arc_radius_row', None)
        arc_radius_entry = arc_radius_entry.entry if arc_radius_entry else None
        arc_text_enabled_var = getattr(sidebar, 'arc_var', None)
        arc_start_angle_entry = getattr(sidebar, 'arc_angle_row', None)
        arc_start_angle_entry = arc_start_angle_entry.entry if arc_start_angle_entry else None
        arc_clockwise_var = getattr(sidebar, 'arc_clockwise_var', None)
        arc_flip_var = getattr(sidebar, 'arc_flip_var', None)
        
        reflection_gap_entry = getattr(sidebar, 'reflection_gap_row', None)
        reflection_gap_entry = reflection_gap_entry.entry if reflection_gap_entry else None
        reflection_opacity_entry = getattr(sidebar, 'reflection_opacity_row', None)
        reflection_opacity_entry = reflection_opacity_entry.entry if reflection_opacity_entry else None
        reflection_fade_entry = getattr(sidebar, 'reflection_fade_row', None)
        reflection_fade_entry = reflection_fade_entry.entry if reflection_fade_entry else None
        reflection_enabled_var = getattr(sidebar, 'reflection_var', None)
        
        halftone_cell_size_entry = getattr(sidebar, 'halftone_cell_size_row', None)
        halftone_cell_size_entry = halftone_cell_size_entry.entry if halftone_cell_size_entry else None
        halftone_dot_scale_entry = getattr(sidebar, 'halftone_dot_scale_row', None)
        halftone_dot_scale_entry = halftone_dot_scale_entry.entry if halftone_dot_scale_entry else None
        halftone_angle_entry = getattr(sidebar, 'halftone_angle_row', None)
        halftone_angle_entry = halftone_angle_entry.entry if halftone_angle_entry else None
        halftone_enabled_var = getattr(sidebar, 'halftone_var', None)
        
        glitch_rgb_shift_entry = getattr(sidebar, 'glitch_rgb_shift_row', None)
        glitch_rgb_shift_entry = glitch_rgb_shift_entry.entry if glitch_rgb_shift_entry else None
        glitch_slice_intensity_entry = getattr(sidebar, 'glitch_slice_intensity_row', None)
        glitch_slice_intensity_entry = glitch_slice_intensity_entry.entry if glitch_slice_intensity_entry else None
        glitch_seed_entry = getattr(sidebar, 'glitch_seed_entry', None)
        glitch_enabled_var = getattr(sidebar, 'glitch_var', None)
        
        gradient_enabled_var = getattr(sidebar, 'gradient_var', None)
        gradient_type_var = getattr(sidebar, 'gradient_type_var', None)
        gradient_angle_entry = getattr(sidebar, 'gradient_angle_row', None)
        gradient_angle_entry = gradient_angle_entry.entry if gradient_angle_entry else None
        
        pattern_enabled_var = getattr(sidebar, 'pattern_var', None)
        pattern_angle_entry = getattr(sidebar, 'pattern_angle_row', None)
        pattern_angle_entry = pattern_angle_entry.entry if pattern_angle_entry else None
        pattern_blend_mode_var = getattr(sidebar, 'pattern_blend_var', None)
        
        characters_entry = getattr(self.main_window, 'characters_entry', None)
        icon_mode_var = getattr(self.main_window, 'icon_mode_var', None)
        transparent_background_var = getattr(sidebar, 'transparent_bg_var', None)
        transparent_text_var = getattr(sidebar, 'transparent_text_var', None)
        cutout_mode_var = getattr(sidebar, 'cutout_var', None)
        text_alignment = getattr(sidebar, 'alignment_var', None)
        canvas_width_enabled_var = getattr(self.main_window, 'canvas_width_enabled_var', None)
        canvas_width_entry = getattr(self.main_window, 'canvas_width_entry', None)
        
        # === ПАРСИНГ ===
        f_size = self.settings.font_size
        if f_size <= 0:
            f_size = 64
        
        shadow_enabled = self._safe_get_var(shadow_var, False)
        shadow_dist = self._safe_get_int(shadow_distance_entry, 5)
        shadow_blur = self._safe_get_int(shadow_blur_entry, 0)
        shadow_dir = self._safe_get_var(shadow_direction_var, 8)
        shadow_blend = self._safe_get_var(shadow_blend_mode_var, "normal")
        
        text_rot = self._safe_get_int(rotation_entry, 0)
        skew_enabled = self._safe_get_var(skew_enabled_var, False)
        skew_x = self._safe_get_int(skew_x_entry, 0)
        skew_y = self._safe_get_int(skew_y_entry, 0)
        perspective_enabled = self._safe_get_var(perspective_enabled_var, False)
        perspective_x = self._safe_get_int(perspective_x_entry, 0)
        perspective_y = self._safe_get_int(perspective_y_entry, 0)
        
        emboss_enabled = self._safe_get_var(emboss_enabled_var, False)
        emboss_depth = self._safe_get_int(emboss_depth_entry, 3)
        emboss_blur = self._safe_get_int(emboss_blur_entry, 1)
        
        outline_outer_enabled = self._safe_get_var(outline_outer_enabled_var, False)
        outline_outer_width = self._safe_get_int(outline_outer_width_entry, 2)
        outline_inner_enabled = self._safe_get_var(outline_inner_enabled_var, False)
        outline_inner_width = self._safe_get_int(outline_inner_width_entry, 1)
        
        glow_outer_enabled = self._safe_get_var(glow_outer_enabled_var, False)
        glow_outer_radius = self._safe_get_int(glow_outer_radius_entry, 5)
        glow_outer_intensity = self._safe_get_int(glow_outer_intensity_entry, 10)
        glow_inner_enabled = self._safe_get_var(glow_inner_enabled_var, False)
        glow_inner_radius = self._safe_get_int(glow_inner_radius_entry, 3)
        glow_inner_intensity = self._safe_get_int(glow_inner_intensity_entry, 10)
        glow_inner_blend = self._safe_get_var(glow_inner_blend_mode_var, "normal")
        
        inner_shadow_enabled = self._safe_get_var(inner_shadow_enabled_var, False)
        inner_shadow_dist = self._safe_get_int(inner_shadow_distance_entry, 4)
        inner_shadow_blur = self._safe_get_int(inner_shadow_blur_entry, 3)
        inner_shadow_dir = self._safe_get_var(inner_shadow_direction_var, 8)
        inner_shadow_blend = self._safe_get_var(inner_shadow_blend_mode_var, "normal")
        
        arc_text_enabled = self._safe_get_var(arc_text_enabled_var, False)
        arc_radius = self._safe_get_int(arc_radius_entry, 150)
        arc_start_angle = self._safe_get_int(arc_start_angle_entry, 0)
        arc_clockwise = self._safe_get_var(arc_clockwise_var, True)
        arc_flip = self._safe_get_var(arc_flip_var, False)
        
        reflection_enabled = self._safe_get_var(reflection_enabled_var, False)
        reflection_gap = self._safe_get_int(reflection_gap_entry, 2)
        reflection_opacity = self._safe_get_int(reflection_opacity_entry, 50)
        reflection_fade = self._safe_get_int(reflection_fade_entry, 100)
        
        halftone_enabled = self._safe_get_var(halftone_enabled_var, False)
        halftone_cell = self._safe_get_int(halftone_cell_size_entry, 10)
        halftone_dot = self._safe_get_int(halftone_dot_scale_entry, 100)
        halftone_angle = self._safe_get_int(halftone_angle_entry, 0)
        
        glitch_enabled = self._safe_get_var(glitch_enabled_var, False)
        glitch_rgb = self._safe_get_int(glitch_rgb_shift_entry, 4)
        glitch_slice = self._safe_get_int(glitch_slice_intensity_entry, 30)
        glitch_seed = self._safe_get_int(glitch_seed_entry, 0)
        
        gradient_enabled = self._safe_get_var(gradient_enabled_var, False)
        gradient_type = self._safe_get_var(gradient_type_var, "linear")
        gradient_angle = self._safe_get_int(gradient_angle_entry, 0)
        
        pattern_enabled = self._safe_get_var(pattern_enabled_var, False)
        pattern_angle = self._safe_get_int(pattern_angle_entry, 0)
        pattern_blend = self._safe_get_var(pattern_blend_mode_var, "normal")
        
        transparent_bg = self._safe_get_var(transparent_background_var, True)
        transparent_text = self._safe_get_var(transparent_text_var, False)
        cutout_mode = self._safe_get_var(cutout_mode_var, False)
        text_align = self._safe_get_var(text_alignment, "center")
        canvas_width_enabled = self._safe_get_var(canvas_width_enabled_var, False)
        canvas_width_delta = self._safe_get_int(canvas_width_entry, 0)
        icon_mode = self._safe_get_var(icon_mode_var, False)
        
        # === ПОЛУЧАЕМ ТЕКСТ ===
        raw = characters_entry.get() if characters_entry else ""
        chars = parse_characters(raw) if raw else parse_characters(PREVIEW_TEXT)
        if not chars:
            chars = parse_characters(PREVIEW_TEXT)
        
        # === НАВИГАЦИЯ ===
        icon_paths = self._get_icon_paths()
        if icon_mode and icon_paths:
            total_nav_items = len(icon_paths)
        else:
            total_nav_items = len(chars)
        
        self.current_index = self.current_index % total_nav_items if total_nav_items else 0
        self.index_label.configure(text=f"{self.current_index + 1}/{total_nav_items}" if total_nav_items else "0/0")
        
        # === ТЕКУЩИЙ ЭЛЕМЕНТ ===
        if icon_mode and icon_paths:
            preview_text = None
            preview_icon_path = icon_paths[self.current_index % len(icon_paths)]
        else:
            preview_text = chars[self.current_index % len(chars)] if chars else PREVIEW_TEXT
            preview_icon_path = None
        
        # === ЗАГРУЗКА ШРИФТА ===
        font_obj = load_font_safe(self.settings.font_path, f_size)
        temp_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        
        # === ВЫЧИСЛЕНИЕ ВНЕШНИХ ЭФФЕКТОВ ===
        outer_effects_width = 0
        if outline_outer_enabled:
            outer_effects_width += outline_outer_width
        if glow_outer_enabled:
            outer_effects_width += glow_outer_radius
        if shadow_enabled:
            outer_effects_width += shadow_blur
        
        preview_icon_mask = None
        max_ascent, max_descent, max_width = 0, 0, 0
        arc_max_left, arc_max_top = 0, 0
        preview_letters_cache = {}
        
        # === ЗАМЕРЫ ДЛЯ ИКОНОК ===
        if icon_mode and preview_icon_path:
            try:
                preview_icon_mask, iw, ih = get_icon_mask(preview_icon_path, f_size)
            except Exception:
                preview_icon_mask = None
                iw, ih = f_size, f_size
            text_width = iw
            max_ascent = ih
            max_descent = 0
        
        # === ЗАМЕРЫ ДЛЯ ДУГОВОГО ТЕКСТА ===
        elif arc_text_enabled:
            arc_xmin, arc_xmax, arc_ymin, arc_ymax = float('inf'), float('-inf'), float('inf'), float('-inf')
            for w in chars:
                m, ax, ay = render_arc_text_mask(
                    w, font_obj, arc_radius, arc_start_angle,
                    arc_clockwise, arc_flip, text_align,
                    self.settings.letter_spacing
                )
                arc_xmin = min(arc_xmin, -ax)
                arc_xmax = max(arc_xmax, m.width - ax)
                arc_ymin = min(arc_ymin, -ay)
                arc_ymax = max(arc_ymax, m.height - ay)
            if arc_xmin == float('inf'):
                arc_xmin = arc_xmax = arc_ymin = arc_ymax = 0
            text_width = arc_xmax - arc_xmin
            max_ascent = arc_ymax - arc_ymin
            max_descent = 0
            arc_max_left = -arc_xmin
            arc_max_top = -arc_ymin
        
        # === ЗАМЕРЫ ДЛЯ ОБЫЧНОГО ТЕКСТА ===
        else:
            preview_letters_cache = {}
            for char in chars:
                text_bbox = temp_draw.textbbox((0, 0), char, font=font_obj, stroke_width=0, anchor="ls")
                left, top, right, bottom = text_bbox
                max_ascent = max(max_ascent, -top)
                max_descent = max(max_descent, bottom)
                
                if self.settings.letter_spacing != 0 and len(char) > 1:
                    letters_info = []
                    cum_width = 0
                    for ch in char:
                        ch_bbox = temp_draw.textbbox((0, 0), ch, font=font_obj, stroke_width=0, anchor="ls")
                        ch_left, _, ch_right, _ = ch_bbox
                        ch_width = ch_right - ch_left
                        letters_info.append((ch, ch_width, ch_left))
                        cum_width += ch_width
                    spaced_width = cum_width + (len(char) - 1) * self.settings.letter_spacing
                    preview_letters_cache[char] = (letters_info, spaced_width)
                    max_width = max(max_width, spaced_width)
                else:
                    max_width = max(max_width, right - left)
            text_width = max_width
        
        # === ВЫЧИСЛЕНИЕ РАЗМЕРОВ ХОЛСТА ===
        safe_pad = 1
        effective_scale = self.settings.text_scale_x if self.settings.text_scale_x > 0 else 1.0
        scaled_text_width = max(1, int(round(text_width * effective_scale))) if effective_scale != 1.0 else text_width
        base_height = max_ascent + max_descent + outer_effects_width * 2 + (safe_pad * 2)
        base_width = scaled_text_width + outer_effects_width * 2 + (safe_pad * 2)
        
        angle_rad = math.radians(text_rot)
        rot_base_w = int(math.ceil(abs(base_width * math.cos(angle_rad)) + abs(base_height * math.sin(angle_rad)))) + 2
        rot_base_h = int(math.ceil(abs(base_width * math.sin(angle_rad)) + abs(base_height * math.cos(angle_rad)))) + 2
        rot_base_w, rot_base_h = max(1, rot_base_w), max(1, rot_base_h)
        
        # Skew
        if skew_enabled and (skew_x != 0 or skew_y != 0):
            if skew_x != 0:
                skew_x_rad = math.radians(max(-85.0, min(85.0, skew_x)))
                rot_base_w += int(math.ceil(abs(math.tan(skew_x_rad)) * max(0, rot_base_h - 1)))
            if skew_y != 0:
                skew_y_rad = math.radians(max(-85.0, min(85.0, skew_y)))
                rot_base_h += int(math.ceil(abs(math.tan(skew_y_rad)) * max(0, rot_base_w - 1)))
        
        # Тень
        if shadow_enabled:
            margin = shadow_blur
            sh_dx, sh_dy = get_shadow_offset(shadow_dir, shadow_dist)
            min_x = min(0, sh_dx - margin)
            min_y = min(0, sh_dy - margin)
            max_x = max(rot_base_w, rot_base_w + sh_dx + margin)
            max_y = max(rot_base_h, rot_base_h + sh_dy + margin)
        else:
            min_x, min_y = 0, 0
            max_x, max_y = rot_base_w, rot_base_h
        
        real_w = int(max_x - min_x)
        real_h = int(max_y - min_y)
        
        # Отражение
        if reflection_enabled and reflection_opacity > 0:
            reflection_extra_h = max(0, reflection_gap + (max_ascent + max_descent))
            real_h += reflection_extra_h
        
        offset_x = -min_x
        offset_y = -min_y
        
        # Дельта ширины
        if canvas_width_enabled:
            real_w = max(1, real_w + canvas_width_delta)
            offset_x += canvas_width_delta // 2
        
        # === ОТРИСОВКА ===
        self.center_frame.update_idletasks()
        frame_width = max(500, self.center_frame.winfo_width() - 20)
        frame_height = max(200, self.center_frame.winfo_height() - 40)
        
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_workspace_color = "#1a1a1a" if is_dark else "#e5e5e5"
        blueprint_line_color = "#555555" if is_dark else "#888888"
        blueprint_text_color = "#aaaaaa" if is_dark else "#444444"
        
        self.center_frame.configure(fg_color=bg_workspace_color)
        
        scale = min(1.0, (frame_width - 90) / real_w, (frame_height - 90) / real_h)
        zoom_pct = self.zoom / 100.0
        scale = max(0.01, scale * zoom_pct)
        
        disp_w, disp_h = int(real_w * scale), int(real_h * scale)
        canvas_w, canvas_h = disp_w + 90, disp_h + 90
        
        final_canvas = Image.new("RGBA", (canvas_w, canvas_h), bg_workspace_color)
        canvas_draw = ImageDraw.Draw(final_canvas)
        box_x1, box_y1 = 45, 45
        
        # Фон
        if transparent_bg:
            block_img = create_checkerboard_background(disp_w, disp_h, 6)
        else:
            bg_col = self.settings.background_color or (240, 240, 240, 255)
            if isinstance(bg_col, str) and bg_col.startswith('#'):
                bg_col = tuple(int(bg_col.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (255,)
            elif isinstance(bg_col, str):
                bg_col = (255, 255, 255, 255) if bg_col == "white" else (0, 0, 0, 255)
            block_img = Image.new("RGBA", (disp_w, disp_h), bg_col)
        
        content_rgba = Image.new("RGBA", (disp_w, disp_h), (0, 0, 0, 0)) if transparent_bg else None
        checkerboard_bg = block_img if transparent_bg else None
        
        # === МАСШТАБИРОВАНИЕ ПАРАМЕТРОВ ===
        scaled_f_size = max(1, int(f_size * scale))
        scaled_outline_inner_width = max(0, int(outline_inner_width * scale))
        scaled_outline_outer_width = max(0, int(outline_outer_width * scale))
        scaled_shadow_dist = int(shadow_dist * scale)
        scaled_shadow_blur = int(shadow_blur * scale)
        scaled_glow_outer_radius = int(glow_outer_radius * scale)
        scaled_glow_inner_radius = int(glow_inner_radius * scale)
        scaled_emboss_depth = max(1, int(emboss_depth * scale))
        scaled_emboss_blur = max(0, int(emboss_blur * scale))
        scaled_inner_shadow_dist = int(inner_shadow_dist * scale)
        scaled_inner_shadow_blur = max(0, int(inner_shadow_blur * scale))
        scaled_outer_effects_width = int(outer_effects_width * scale)
        scaled_font = load_font_safe(self.settings.font_path, scaled_f_size)
        
        sc_base_w = max(1, int(base_width * scale))
        sc_base_h = max(1, int(base_height * scale))
        sc_text_base_x = scaled_outer_effects_width + (safe_pad * scale)
        sc_content_w = max(1, int(round(text_width * scale)))
        scaled_content_height = max(1, int(round((max_ascent + max_descent) * scale)))
        scaled_max_ascent = max(1, int(round(max_ascent * scale)))
        
        text_rgb = get_color_rgb(self.settings.text_color)[:3]
        transp_bg = text_rgb + (0,) if not transparent_text else (0, 0, 0, 0)
        
        # === СОЗДАНИЕ МАСКИ КОНТЕНТА ===
        if preview_icon_mask is not None:
            sw = max(1, int(preview_icon_mask.width * scale))
            sh = max(1, int(preview_icon_mask.height * scale))
            content_mask = preview_icon_mask.resize((sw, sh), Image.Resampling.LANCZOS)
        
        elif arc_text_enabled:
            scaled_radius = max(1, int(arc_radius * scale))
            scaled_arc_letter_spacing = int(round(self.settings.letter_spacing * scale))
            arc_mask_scaled, sc_anchor_x, sc_anchor_y = render_arc_text_mask(
                preview_text, scaled_font, scaled_radius,
                arc_start_angle, arc_clockwise, arc_flip,
                text_align, scaled_arc_letter_spacing
            )
            content_mask = Image.new("L", (sc_content_w, scaled_content_height), 0)
            arc_paste_x = int(round(arc_max_left * scale)) - sc_anchor_x
            arc_paste_y = int(round(arc_max_top * scale)) - sc_anchor_y
            content_mask.paste(arc_mask_scaled, (arc_paste_x, arc_paste_y))
        
        else:
            scaled_bbox = temp_draw.textbbox((0, 0), preview_text, font=scaled_font, stroke_width=0, anchor="ls")
            s_left, s_top, s_right, s_bottom = scaled_bbox
            s_width = s_right - s_left
            content_mask = Image.new("L", (sc_content_w, scaled_content_height), 0)
            m_draw = ImageDraw.Draw(content_mask)
            
            cached = preview_letters_cache.get(preview_text)
            if cached:
                _orig_letters_info, _orig_spaced_width = cached
                scaled_letters_info = []
                scaled_cum_width = 0
                for ch, _, _ in _orig_letters_info:
                    ch_bbox = temp_draw.textbbox((0, 0), ch, font=scaled_font, stroke_width=0, anchor="ls")
                    ch_left, _, ch_right, _ = ch_bbox
                    ch_width = ch_right - ch_left
                    scaled_letters_info.append((ch, ch_width, ch_left))
                    scaled_cum_width += ch_width
                scaled_spacing = int(round(self.settings.letter_spacing * scale))
                scaled_spaced_width = scaled_cum_width + (len(scaled_letters_info) - 1) * scaled_spacing
                
                if text_align == "left":
                    start_x = -scaled_letters_info[0][2]
                elif text_align == "right":
                    start_x = sc_content_w - scaled_spaced_width - scaled_letters_info[0][2]
                else:
                    start_x = (sc_content_w - scaled_spaced_width) / 2 - scaled_letters_info[0][2]
                cur_x = start_x
                for ch, ch_width, ch_left in scaled_letters_info:
                    m_draw.text((cur_x, scaled_max_ascent), ch, font=scaled_font, anchor="ls", fill=255)
                    cur_x += ch_width + scaled_spacing
            else:
                if text_align == "left":
                    sc_text_x = -s_left
                elif text_align == "right":
                    sc_text_x = sc_content_w - s_width - s_left
                else:
                    sc_text_x = (sc_content_w - s_width) / 2 - s_left
                m_draw.text((sc_text_x, scaled_max_ascent), preview_text, font=scaled_font, anchor="ls", fill=255)
        
        # Масштабирование по X
        if self.settings.text_scale_x != 1.0 and self.settings.text_scale_x > 0:
            new_content_width = max(1, int(content_mask.width * self.settings.text_scale_x))
            content_mask = content_mask.resize((new_content_width, content_mask.height), Image.Resampling.LANCZOS)
        
        # Вставка в холст
        text_mask = Image.new("L", (sc_base_w, sc_base_h), 0)
        paste_xy = int(round(sc_text_base_x))
        text_mask.paste(content_mask, (paste_xy, paste_xy))
        
        char_layer_text = Image.new("RGBA", text_mask.size, transp_bg)
        base_mask = text_mask
        
        # --- Halftone (до искажений) ---
        fill_mask = base_mask
        will_warp_geometrically = (
            text_rot != 0 or
            (skew_enabled and (skew_x != 0 or skew_y != 0)) or
            (perspective_enabled and (perspective_x != 0 or perspective_y != 0))
        )
        
        if halftone_enabled and not transparent_text and not will_warp_geometrically:
            scaled_cell_size = max(1, int(round(halftone_cell * scale)))
            fill_mask = apply_halftone(base_mask, scaled_cell_size, halftone_dot, halftone_angle)
        
        # --- Заливка ---
        if not transparent_text:
            if gradient_enabled:
                effective_gradient_stops = self.settings.gradient_stops if self.settings.gradient_stops else [{"pos": 0.0, "color": "#ff0000"}, {"pos": 1.0, "color": "#0000ff"}]
                char_layer_text = apply_gradient_fill(
                    char_layer_text, fill_mask, effective_gradient_stops,
                    gradient_type, gradient_angle
                )
            else:
                text_fill_layer = Image.new("RGBA", char_layer_text.size, text_rgb + (255,))
                text_fill_layer.putalpha(fill_mask)
                char_layer_text = Image.alpha_composite(char_layer_text, text_fill_layer)
            
            if pattern_enabled and self.settings.pattern_image_path:
                preview_pattern_image = load_pattern_image(self.settings.pattern_image_path)
                if preview_pattern_image is not None:
                    char_layer_text = apply_pattern_fill(
                        char_layer_text, fill_mask, preview_pattern_image,
                        max(1, self.settings.pattern_scale * scale),
                        int(round(self.settings.pattern_offset_x * scale)),
                        int(round(self.settings.pattern_offset_y * scale)),
                        pattern_angle, pattern_blend
                    )
        
        # --- Внутренние эффекты ---
        if outline_inner_enabled and scaled_outline_inner_width > 0:
            char_layer_text = apply_inner_outline(char_layer_text, base_mask,
                                                  self.settings.outline_inner_color,
                                                  scaled_outline_inner_width)
        
        if glow_inner_enabled:
            char_layer_text = apply_inner_glow(char_layer_text, base_mask,
                                               self.settings.glow_inner_color,
                                               scaled_glow_inner_radius,
                                               glow_inner_intensity, glow_inner_blend)
        
        if inner_shadow_enabled:
            char_layer_text = apply_inner_shadow(
                char_layer_text, base_mask, self.settings.inner_shadow_color,
                scaled_inner_shadow_dist, inner_shadow_dir,
                scaled_inner_shadow_blur, inner_shadow_blend
            )
        
        if emboss_enabled:
            char_layer_text = apply_emboss(char_layer_text, base_mask,
                                          scaled_emboss_depth, scaled_emboss_blur,
                                          self.settings.emboss_highlight,
                                          self.settings.emboss_shadow)
        
        # --- Внешние эффекты ---
        outer_mask = base_mask
        outline_outer_drawn = outline_outer_enabled and scaled_outline_outer_width > 0
        outline_outer_source = outline_outer_enabled and outline_outer_width > 0
        
        if outline_outer_drawn:
            char_layer_text, outer_mask = apply_outer_outline(char_layer_text, base_mask,
                                                              self.settings.outline_outer_color,
                                                              scaled_outline_outer_width)
        
        if glow_outer_enabled and (not transparent_text or outline_outer_source):
            char_layer_text = apply_outer_glow(char_layer_text, outer_mask,
                                               self.settings.glow_outer_color,
                                               scaled_glow_outer_radius,
                                               glow_outer_intensity)
        
        # --- Прозрачность ---
        if self.settings.text_opacity < 1.0:
            r, g, b, a = char_layer_text.split()
            a = a.point(lambda p: int(p * self.settings.text_opacity))
            char_layer_text = Image.merge("RGBA", (r, g, b, a))
        
        # --- Поворот ---
        if text_rot != 0:
            char_layer_text = rotate_cleanly(char_layer_text, -text_rot, text_rgb)
        
        # --- Skew ---
        if skew_enabled and (skew_x != 0 or skew_y != 0):
            char_layer_text = apply_skew_effect(char_layer_text, skew_x, skew_y, text_rgb)
        
        # --- Perspective ---
        if perspective_enabled and (perspective_x != 0 or perspective_y != 0):
            char_layer_text = apply_perspective_effect(char_layer_text, perspective_x,
                                                       perspective_y, text_rgb)
        
        # --- Halftone (после искажений) ---
        if halftone_enabled and not transparent_text and will_warp_geometrically:
            warped_alpha = char_layer_text.split()[3]
            scaled_cell_size_post = max(1, int(round(halftone_cell * scale)))
            halftoned_alpha = apply_halftone(warped_alpha, scaled_cell_size_post,
                                            halftone_dot, halftone_angle)
            r, g, b, _ = char_layer_text.split()
            char_layer_text = Image.merge("RGBA", (r, g, b, halftoned_alpha))
        
        paste_x = int((offset_x * scale) + (int(rot_base_w * scale) - char_layer_text.width) / 2)
        paste_y = int((offset_y * scale) + (int(rot_base_h * scale) - char_layer_text.height) / 2)
        
        # --- Тень ---
        layer_shadow = None
        if shadow_enabled:
            shadow_rgb = get_color_rgb(self.settings.shadow_color)[:3]
            transp_shadow_bg = shadow_rgb + (0,) if not transparent_text else (0, 0, 0, 0)
            shadow_mask = char_layer_text.split()[3]
            shadow_layer = Image.new("RGBA", char_layer_text.size, shadow_rgb + (255,))
            shadow_layer.putalpha(shadow_mask)
            if scaled_shadow_blur > 0:
                shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=scaled_shadow_blur))
            sh_dx, sh_dy = get_shadow_offset(shadow_dir, scaled_shadow_dist)
            shadow_paste_x = paste_x + sh_dx
            shadow_paste_y = paste_y + sh_dy
            layer_shadow = Image.new("RGBA", (disp_w, disp_h), transp_shadow_bg)
            layer_shadow.paste(shadow_layer, (shadow_paste_x, shadow_paste_y))
        
        if layer_shadow:
            effective_shadow_blend = shadow_blend
            if transparent_bg and effective_shadow_blend in ("multiply", "overlay"):
                effective_shadow_blend = "normal"
            block_img = blend_layers(block_img.convert("RGBA"), layer_shadow, effective_shadow_blend)
            if content_rgba is not None:
                content_rgba = blend_layers(content_rgba, layer_shadow, effective_shadow_blend)
        
        # --- Вставка текста ---
        layer_text = Image.new("RGBA", (disp_w, disp_h), (0, 0, 0, 0))
        layer_text.paste(char_layer_text, (paste_x, paste_y))
        block_img = Image.alpha_composite(block_img.convert("RGBA"), layer_text)
        if content_rgba is not None:
            content_rgba = Image.alpha_composite(content_rgba, layer_text)
        
        # --- Cutout ---
        if not transparent_text and cutout_mode and not transparent_bg:
            mask = text_mask.copy()
            if text_rot != 0:
                mask = mask.rotate(-text_rot, resample=Image.BICUBIC, expand=True)
            mask = mask.point(lambda p: 255 if p > 128 else 0)
            full_mask = Image.new("L", (disp_w, disp_h), 0)
            mask_paste_x = int((offset_x * scale) + (int(rot_base_w * scale) - mask.width) / 2)
            mask_paste_y = int((offset_y * scale) + (int(rot_base_h * scale) - mask.height) / 2)
            full_mask.paste(mask, (mask_paste_x, mask_paste_y))
            r, g, b, a = block_img.split()
            new_a = Image.composite(Image.new('L', block_img.size, 0), a, full_mask)
            block_img = Image.merge('RGBA', (r, g, b, new_a))
        
        # --- Отражение ---
        if reflection_enabled and reflection_opacity > 0:
            refl_opacity = reflection_opacity / 100.0
            refl_fade = reflection_fade / 100.0
            content_alpha_bbox = char_layer_text.split()[3].getbbox()
            if content_alpha_bbox is not None:
                cleft, ctop, cright, cbottom = content_alpha_bbox
                visible_preview = char_layer_text.crop((cleft, ctop, cright, cbottom))
                reflected_preview = visible_preview.transpose(Image.FLIP_TOP_BOTTOM)
                rp_w, rp_h = reflected_preview.size
                rp_r, rp_g, rp_b, rp_a = reflected_preview.split()
                fade_h_px = max(1, min(rp_h, int(round(rp_h * refl_fade))))
                grad = np.linspace(refl_opacity, 0.0, fade_h_px, dtype=np.float64)
                if rp_h > fade_h_px:
                    grad = np.concatenate([grad, np.zeros(rp_h - fade_h_px, dtype=np.float64)])
                rp_alpha_arr = np.asarray(rp_a, dtype=np.float64)
                rp_new_alpha = np.clip(rp_alpha_arr * grad.reshape(-1, 1), 0, 255).astype(np.uint8)
                reflected_preview.putalpha(Image.fromarray(rp_new_alpha))
                refl_gap_scaled = int(round(reflection_gap * scale))
                refl_dest_x = paste_x + cleft
                refl_dest_y = max(0, paste_y + cbottom + refl_gap_scaled)
                if refl_dest_x < block_img.width and refl_dest_y < block_img.height:
                    block_img.alpha_composite(reflected_preview, (refl_dest_x, refl_dest_y))
                    if content_rgba is not None and refl_dest_x < content_rgba.width and refl_dest_y < content_rgba.height:
                        content_rgba.alpha_composite(reflected_preview, (refl_dest_x, refl_dest_y))
        
        # --- Глитч ---
        if glitch_enabled and (glitch_rgb > 0 or glitch_slice > 0):
            scaled_glitch_rgb_shift = max(0, int(round(glitch_rgb * scale)))
            glitch_seed_final = (glitch_seed + self.current_index) & 0xFFFFFFFF
            if content_rgba is not None:
                content_rgba = apply_glitch_effect(content_rgba, scaled_glitch_rgb_shift,
                                                  glitch_slice, seed=glitch_seed_final)
                block_img = Image.alpha_composite(checkerboard_bg, content_rgba)
            else:
                block_img = apply_glitch_effect(block_img, scaled_glitch_rgb_shift,
                                                glitch_slice, seed=glitch_seed_final)
        
        # --- Вставка в финальный канвас ---
        final_canvas.paste(block_img, (box_x1, box_y1))
        box_x2, box_y2 = box_x1 + disp_w, box_y1 + disp_h
        
        # --- Рамка ---
        canvas_draw.rectangle([box_x1, box_y1, box_x2, box_y2], outline=blueprint_line_color, width=1)
        canvas_draw.line([box_x1, 25, box_x2, 25], fill=blueprint_line_color, width=1)
        canvas_draw.line([box_x1, 20, box_x1, 30], fill=blueprint_line_color, width=1)
        canvas_draw.line([box_x2, 20, box_x2, 30], fill=blueprint_line_color, width=1)
        canvas_draw.line([25, box_y1, 25, box_y2], fill=blueprint_line_color, width=1)
        canvas_draw.line([20, box_y1, 30, box_y1], fill=blueprint_line_color, width=1)
        canvas_draw.line([20, box_y2, 30, box_y2], fill=blueprint_line_color, width=1)
        
        # --- Размеры ---
        try:
            sys_font = ImageFont.truetype("arial.ttf", 11)
        except:
            sys_font = ImageFont.load_default()
        
        w_bbox = canvas_draw.textbbox((0, 0), f"{real_w} px", font=sys_font)
        canvas_draw.text(((box_x1 + box_x2 - (w_bbox[2] - w_bbox[0]))/2, 10),
                        f"{real_w} px", fill=blueprint_text_color, font=sys_font)
        h_bbox = canvas_draw.textbbox((0, 0), f"{real_h} px", font=sys_font)
        canvas_draw.text((2, (box_y1 + box_y2 - (h_bbox[3] - h_bbox[1]))/2),
                        f"{real_h} px", fill=blueprint_text_color, font=sys_font)
        
        # --- Отображение ---
        ctk_image = ctk.CTkImage(light_image=final_canvas, dark_image=final_canvas, size=(canvas_w, canvas_h))
        self.image_label.configure(image=ctk_image, text="")
        self.image_label.image = ctk_image