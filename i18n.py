# -*- coding: utf-8 -*-
"""
Интернационализация (переводы)
"""

import os
import json
from constants import LANGUAGES_FILE

# Встроенные переводы (английский)
DEFAULT_LANGUAGES = {
    "en": {
        "app_title": "Character Image Generator",
        "settings": "Settings",
        "font": "Font",
        "choose_font": "Choose font",
        "size": "Size",
        "align": "Align",
        "left": "Left",
        "center": "Center",
        "right": "Right",
        "text_color": "Text color",
        "transparent": "Transparent",
        "cutout": "Cutout from background",
        "background": "Background",
        "transparent_bg": "Transparent bg",
        "shadow": "Enable shadow",
        "shadow_color": "Shadow color",
        "shadow_distance": "Distance",
        "shadow_blur": "Blur",
        "shadow_direction": "Direction",
        "center_shadow": "● - center (shadow under text)",
        "characters_to_generate": "Characters to generate",
        "generate_images": "Generate Images",
        "preview": "Preview",
        "done": "Done",
        "warning": "Warning",
        "error": "Error",
        "warning_no_characters": "Please enter characters to generate",
        "warning_no_valid": "No valid characters found",
        "warning_font": "Using default bitmap font. Please select a TTF font for better quality.",
        "generated": "Generated {count} images successfully!",
        "select_text_color": "Select Text Color",
        "select_background_color": "Select Background Color",
        "select_shadow_color": "Select Shadow Color",
        "select_pattern": "Select Pattern",
        "available_patterns": "Available Patterns",
        "pattern_info": "Pattern Info",
        "name": "Name",
        "description": "Description",
        "categories": "Categories",
        "preview_pattern": "Preview",
        "load": "Load",
        "cancel": "Cancel",
        "cut": "Cut",
        "copy": "Copy",
        "paste": "Paste",
        "delete": "Delete",
        "select_all": "Select All",
        "language": "Language",
        "theme": "Theme",
        "choose": "Choose",
        "rotation": "Rotation",
        "text_style": "Character style",
        "emboss": "Emboss",
        "emboss_depth": "Depth",
        "emboss_blur": "Blur",
        "highlight_color": "Highlight",
        "shadow_color_emboss": "Shadow",
        "outline_outer": "Outer Outline",
        "outline_inner": "Inner Outline",
        "outline_color": "Color",
        "outline_width": "Width",
        "glow_outer": "Outer Glow",
        "glow_inner": "Inner Glow",
        "glow_color": "Color",
        "glow_radius": "Radius",
        "glow_intensity": "Intensity",
        "text_scale": "Compression/Expansion",
        "letter_spacing": "Letter spacing",
        "opacity": "Opacity",
        "gradient_fill": "Gradient fill",
        "gradient_color_1": "Color 1",
        "gradient_color_2": "Color 2",
        "gradient_type": "Type",
        "gradient_vertical": "Vertical",
        "gradient_horizontal": "Horizontal",
        "gradient_diagonal": "Diagonal",
        "gradient_radial": "Radial",
        "gradient_angle": "Angle",
        "gradient_stops": "Color Stops",
        "select_gradient_color": "Select Gradient Color",
        "pattern_fill": "Pattern fill",
        "choose_texture": "Choose texture",
        "no_texture": "No texture selected",
        "pattern_scale": "Scale",
        "pattern_offset_x": "Offset X",
        "pattern_offset_y": "Offset Y",
        "pattern_angle": "Angle",
        "warning_pattern_missing": "Pattern texture file not found or invalid — generating without pattern fill.",
        "arc_text": "Arc / circle text",
        "arc_radius": "Radius",
        "arc_start_angle": "Start angle",
        "arc_clockwise": "Clockwise",
        "arc_flip": "Flip",
        "inner_shadow": "Inner shadow",
        "inner_shadow_distance": "Distance",
        "inner_shadow_blur": "Blur",
        "inner_shadow_color": "Color",
        "blend_mode": "Blend",
        "blend_normal": "Normal",
        "blend_multiply": "Multiply",
        "blend_screen": "Screen",
        "blend_overlay": "Overlay",
        "reset": "Reset",
        "reset_warning": "Reset all settings to default values?",
        "reset_confirm": "This action cannot be undone.",
        "settings_reset": "Settings reset to default values.",
        "generating": "Generating",
        "processing": "Processing",
        "export": "Export",
        "export_format": "Export Format",
        "quality": "Quality",
        "export_success": "Exported successfully!",
        "no_font": "No font selected",
        "font_not_found": "Font file not found, using default",
        "generation_failed": "Generation failed",
        "filename_template": "Filename template",
        "filename_template_hint": "Placeholders: {font_size} {index} {char} (e.g. {index:03d} for 001, 002...)",
        "system_font": "Installed fonts",
        "system_font_placeholder": "Select installed font...",
        "system_font_search": "Search fonts...",
        "style_presets": "Style Presets",
        "style_preset_name": "Preset name...",
        "save": "Save",
        "no_style_presets": "No saved styles yet",
        "delete_style_confirm": "Delete style preset \"{name}\"?",
        "overwrite_style_confirm": "A style preset named \"{name}\" already exists. Overwrite it?",
        "export_style_preset": "Export style preset",
        "import_style_preset": "Import style preset",
        "import_from_file": "Import from file...",
        "invalid_style_preset_file": "Invalid style preset file",
        "multiple_presets_in_file": "This file contains multiple presets - please export/select a single preset to import.",
        "style_preset_imported": "Style preset imported!",
        "text_mode": "Text",
        "icon_mode": "Icons",
        "loaded_icons": "Loaded Icons",
        "load_icons": "Load Icons",
        "clear": "Clear",
        "no_icons_loaded": "No icons loaded yet",
        "drag_drop_hint": "or drag & drop image files here",
        "warning_no_icons": "Please load at least one icon",
        "warning_mixed_icon_sizes": "Loaded icons have different sizes. \"Size\" applies to the whole batch (based on the first icon) - other icons will be scaled to match it instead of keeping their own native size.",
        "create_bin": "Create .bin (LVGL)",
        "canvas_width_delta": "Canvas width delta (px)",
        "reflection": "Reflection",
        "reflection_gap": "Gap",
        "reflection_opacity": "Opacity",
        "reflection_fade": "Fade",
        "halftone": "Halftone",
        "halftone_cell_size": "Cell size",
        "halftone_dot_scale": "Dot scale",
        "halftone_angle": "Angle",
        "glitch": "Glitch (VHS)",
        "glitch_rgb_shift": "RGB shift",
        "glitch_slice_intensity": "Slice intensity",
        "glitch_seed": "Seed",
        "skew": "Skew",
        "skew_x": "Skew X",
        "skew_y": "Skew Y",
        "perspective": "Perspective",
        "perspective_x": "Perspective X",
        "perspective_y": "Perspective Y"
    }
}


class I18n:
    """Класс для работы с переводами."""
    
    def __init__(self, lang='en'):
        self.languages = self._load_languages()
        self.current_lang = lang if lang in self.languages else 'en'
    
    def _load_languages(self):
        """Загружает переводы из файла или создаёт файл с дефолтными."""
        if os.path.exists(LANGUAGES_FILE):
            try:
                with open(LANGUAGES_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and len(data) > 0:
                        # Обновляем встроенные переводы из файла
                        for lang in DEFAULT_LANGUAGES:
                            if lang in data:
                                for key in DEFAULT_LANGUAGES[lang]:
                                    if key in data[lang]:
                                        DEFAULT_LANGUAGES[lang][key] = data[lang][key]
                        # Добавляем новые языки
                        for lang in data:
                            if lang not in DEFAULT_LANGUAGES:
                                DEFAULT_LANGUAGES[lang] = data[lang]
                        return DEFAULT_LANGUAGES
            except Exception:
                pass
        
        # Если файл не существует или повреждён, создаём его
        try:
            with open(LANGUAGES_FILE, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_LANGUAGES, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
        
        return DEFAULT_LANGUAGES
    
    def tr(self, key):
        """Возвращает перевод ключа на текущем языке."""
        # Сначала пробуем текущий язык
        if self.current_lang in self.languages:
            value = self.languages[self.current_lang].get(key)
            if value is not None:
                return value
        
        # Затем английский как fallback
        return self.languages.get('en', {}).get(key, key)
    
    def set_language(self, lang):
        """Устанавливает текущий язык."""
        if lang in self.languages:
            self.current_lang = lang
            return True
        return False
    
    def get_languages(self):
        """Возвращает список доступных языков."""
        return list(self.languages.keys())