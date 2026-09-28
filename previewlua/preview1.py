#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
preview_hourly.py — рендерит PNG-предпросмотр блока почасового прогноза
из Lua watchface-скрипта (TextImageRenderer + renderForecast), НЕ на часах,
а на компьютере, той же самой раскладкой/арифметикой смещений.

Логика 1-в-1 повторяет Lua:
  - формат .bin: 4-байтный LE заголовок (cf:5, w:11 бит со сдвигом 10,
    h:11 бит со сдвигом 21) + сырые пиксели BGRA8888, без паддинга;
  - TextImageRenderer: char_w x char_h ячейка на символ, spacing между
    ячейками, необязательный char_advance для "узких" символов (":", "°"),
    рисуемых по центру своей ячейки — картинка всегда в реальном размере
    файла (чтобы не портить stride), сдвигается на (char_w-advance)/2;
  - renderForecast: 4 колонки, BLOCK_X по ALIGN (left/center/right),
    время сверху, иконка погоды по центру (и по X и по Y), температура
    снизу, все с центрированием текста внутри колонки.

Если передан реальный database.db — почасовые данные (час/темп./иконка)
читаются той же арифметикой смещений (REC0_OFFSET=960, REC_STRIDE=48,
readInt16 на позициях 4 и 8), что и getHourlyForecast() в Lua. Если файл
не передан — используются тестовые данные (--sample), чтобы можно было
проверить чисто раскладку/размеры без реального снимка с часов.

Использование:
    python3 preview_hourly.py --assets ./assets --out preview.png
    python3 preview_hourly.py --assets ./assets --database database.db --out preview.png
    python3 preview_hourly.py --assets ./assets --width 466 --height 466 \
        --hours 4 --align center --out preview.png
"""
import argparse
import os
import struct
import sys

from PIL import Image


# ------------------------------------------------------------------------
# Чтение .bin (тот же формат, что и getBinImageSize()/декодер в Lua)
# ------------------------------------------------------------------------
def read_bin_image(path):
    """Возвращает PIL.Image (RGBA) и (w, h). Кидает FileNotFoundError/ValueError
    при проблемах — вызывающий код сам решает, что подставить вместо."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 4:
        raise ValueError(f"{path}: файл короче 4 байт")

    val = struct.unpack("<I", data[:4])[0]
    w = (val >> 10) & 0x7FF
    h = (val >> 21) & 0x7FF

    expected = 4 + w * h * 4
    if len(data) < expected:
        raise ValueError(
            f"{path}: заявлено {w}x{h} ({expected} байт с заголовком), "
            f"а файл всего {len(data)} байт — заголовок не бьётся с размером файла"
        )

    px = data[4:4 + w * h * 4]
    img = Image.frombuffer("RGBA", (w, h), px, "raw", "BGRA", 0, 1)
    return img, w, h


def get_bin_image_size(path):
    """Аналог Lua getBinImageSize(): (w, h) или (None, None), если что-то не так."""
    try:
        _, w, h = read_bin_image(path)
        return w, h
    except Exception:
        return None, None


class BinImageCache:
    """Чтобы не перечитывать один и тот же .bin по многу раз за прогон."""
    def __init__(self):
        self._cache = {}

    def get(self, path):
        if path not in self._cache:
            try:
                img, w, h = read_bin_image(path)
            except Exception as e:
                print(f"  [!] не удалось прочитать {path}: {e}", file=sys.stderr)
                img, w, h = None, None, None
            self._cache[path] = (img, w, h)
        return self._cache[path]


# ------------------------------------------------------------------------
# UTF-8 разбивка строки на символы (аналог utf8_chars из Lua)
# ------------------------------------------------------------------------
def utf8_chars(s):
    return list(s)  # в Python str уже unicode-код-пойнты — этого достаточно


# ------------------------------------------------------------------------
# Аналог TextImageRenderer:render() -- рисует текст картинками-символами
# на canvas (PIL.Image, RGBA), возвращает список отрисованных (file, x, y)
# для отладки/лога.
# ------------------------------------------------------------------------
def render_text(
    canvas, cache, assets_dir, text, x, y, align,
    char_w, char_h, spacing, char_map, char_advance=None,
):
    char_advance = char_advance or {}
    if not text:
        return []

    chars = utf8_chars(text)

    def advance_for(ch):
        return char_advance.get(ch, char_w)

    total_w = (len(chars) - 1) * spacing
    for ch in chars:
        total_w += advance_for(ch)

    if align == "center":
        cur_x = x - total_w // 2
    elif align == "right":
        cur_x = x - total_w
    else:
        cur_x = x

    drawn = []
    for ch in chars:
        if ch != " ":
            fname = char_map.get(ch)
            if fname:
                adv = advance_for(ch)
                draw_x = cur_x - (char_w - adv) // 2
                img, w, h = cache.get(os.path.join(assets_dir, fname))
                if img is not None:
                    canvas.alpha_composite(img, (draw_x, y))
                    drawn.append((fname, draw_x, y))
                else:
                    print(f"  [!] нет символа для {ch!r} ({fname}) — пропущен", file=sys.stderr)
        cur_x += advance_for(ch) + spacing

    return drawn


# ------------------------------------------------------------------------
# Аналог getHourlyForecast() -- парсинг реального database.db
# ------------------------------------------------------------------------
REC0_OFFSET = 960
REC_STRIDE = 48
REC_COUNT = 23


def get_current_hour(content, pos):
    ts = content[pos + 6: pos + 6 + 13]
    try:
        return int(ts[11:13])
    except Exception:
        return 0


def read_int16(rec, byte_offset):
    lo, hi = rec[byte_offset], rec[byte_offset + 1]
    v = lo + hi * 256
    if v >= 32768:
        v -= 65536
    return v


def get_hourly_forecast(database_path, count):
    result = []
    if not database_path or not os.path.exists(database_path):
        return result

    with open(database_path, "rb") as f:
        content = f.read()

    pos = content.find(b"wdata2")
    if pos == -1:
        return result

    base_hour = get_current_hour(content, pos)

    for i in range(1, min(count, REC_COUNT - 1) + 1):
        rec_start = pos + REC0_OFFSET + REC_STRIDE * i
        rec = content[rec_start: rec_start + 48]
        if len(rec) == 48:
            icon_code = read_int16(rec, 4)
            temp = read_int16(rec, 8)
            hour = (base_hour + i) % 24
            result.append({"hour": hour, "temp": temp, "icon_code": icon_code})

    return result


def sample_forecast(count):
    """Тестовые данные для проверки чистой раскладки без реального database.db."""
    base = [
        {"hour": 13, "temp": 15, "icon_code": 3},
        {"hour": 14, "temp": 17, "icon_code": 1},
        {"hour": 15, "temp": 15, "icon_code": 3},
        {"hour": 16, "temp": 14, "icon_code": 7},
        {"hour": 17, "temp": -3, "icon_code": 0},
        {"hour": 18, "temp": 0, "icon_code": 13},
    ]
    return base[:count]


# ------------------------------------------------------------------------
# weather_icons -- 1-в-1 таблица из Lua
# ------------------------------------------------------------------------
WEATHER_ICONS = {
    0: "weather00.bin",
    1: "weather01.bin",
    2: "weather02.bin",
    3: "weather07.bin",
    4: "weather04.bin",
    5: "weather05.bin",
    6: "weather06.bin",
    7: "weather07.bin",
    8: "weather08.bin",
    9: "weather09.bin",
    10: "weather09.bin",
    13: "weather13.bin",
    14: "weather13.bin",
    15: "weather15.bin",
    16: "weather16.bin",
    17: "weather16.bin",
    18: "weather18.bin",
    19: "weather19.bin",
    20: "weather20.bin",
    29: "weather29.bin",
    35: "weather18.bin",
    53: "weather53.bin",
}
DEFAULT_ICON = "weather99.bin"

DIGITS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", ":", "-", "°"]


def format_time(hour):
    return f"{hour:02d}:00"


def format_temp(temp):
    return f"{temp}°"


# ------------------------------------------------------------------------
# Основной рендер -- аналог renderForecast()
# ------------------------------------------------------------------------
def render_preview(assets_dir, database_path, hours_visible, align,
                    screen_w, screen_h, out_path, use_sample, bg_color):
    cache = BinImageCache()

    icon_w, icon_h = get_bin_image_size(os.path.join(assets_dir, "weather00.bin"))
    icon_w = icon_w or 50
    icon_h = icon_h or 50

    digit_w, digit_h = get_bin_image_size(os.path.join(assets_dir, "num_01.bin"))
    digit_w = digit_w or 30
    digit_h = digit_h or 37

    narrow_advance = {":": digit_w // 2, "°": digit_w // 2}

    digit_map = {ch: f"num_{i:02d}.bin" for i, ch in enumerate(DIGITS, start=1)}

    col_width = 80
    block_width = col_width * hours_visible

    if align == "center":
        block_x = (screen_w - block_width) // 2
    elif align == "right":
        block_x = screen_w - block_width
    else:
        block_x = 0

    block_y = 0
    time_y_offset = 0
    icon_y_offset = 39   # теперь трактуется как ЦЕНТР иконки по Y, не верхний край
    temp_y_offset = 78

    if database_path and not use_sample:
        data = get_hourly_forecast(database_path, hours_visible)
        if not data:
            print("  [!] не удалось прочитать почасовые данные из database.db, "
                  "использую тестовые", file=sys.stderr)
            data = sample_forecast(hours_visible)
    else:
        data = sample_forecast(hours_visible)

    canvas = Image.new("RGBA", (screen_w, screen_h), bg_color)

    for col in range(1, hours_visible + 1):
        if col - 1 >= len(data):
            break
        item = data[col - 1]

        col_x = block_x + (col - 1) * col_width
        col_center = col_x + col_width // 2

        render_text(
            canvas, cache, assets_dir, format_time(item["hour"]),
            col_center, block_y + time_y_offset, "center",
            digit_w, digit_h, -4, digit_map,
        )
        render_text(
            canvas, cache, assets_dir, format_temp(item["temp"]),
            col_center, block_y + temp_y_offset, "center",
            digit_w, digit_h, -4, digit_map, narrow_advance,
        )

        icon_file = WEATHER_ICONS.get(item["icon_code"], DEFAULT_ICON)
        icon_img, iw, ih = cache.get(os.path.join(assets_dir, icon_file))
        if icon_img is not None:
            icon_x = col_center - icon_w // 2
            icon_y = (block_y + icon_y_offset) - icon_h // 2
            canvas.alpha_composite(icon_img, (icon_x, icon_y))
        else:
            print(f"  [!] нет иконки {icon_file} (код {item['icon_code']}) — пропущена",
                  file=sys.stderr)

    canvas.save(out_path)
    print(f"Сохранено: {out_path}  ({screen_w}x{screen_h})")
    print(f"DIGIT_W/H = {digit_w}/{digit_h}   ICON_W/H = {icon_w}/{icon_h}")
    print(f"Данные ({'sample' if (use_sample or not database_path) else database_path}):")
    for item in data[:hours_visible]:
        icon_file = WEATHER_ICONS.get(item["icon_code"], DEFAULT_ICON)
        print(f"   {item['hour']:02d}:00  {item['temp']:>4}°  код={item['icon_code']:<3} -> {icon_file}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--assets", required=True, help="папка с num_XX.bin / weatherXX.bin")
    ap.add_argument("--database", default=None, help="путь к database.db (необязательно)")
    ap.add_argument("--sample", action="store_true", help="принудительно взять тестовые данные, игнорируя --database")
    ap.add_argument("--hours", type=int, default=4, help="HOURS_VISIBLE (по умолчанию 4)")
    ap.add_argument("--align", choices=["left", "center", "right"], default="center", help="ALIGN блока")
    ap.add_argument("--width", type=int, default=390, help="ширина экрана (global_w)")
    ap.add_argument("--height", type=int, default=450, help="высота холста предпросмотра")
    ap.add_argument("--bg", default="#00000000", help="фон холста, HEX, например #000000 (сам watchface прозрачный)")
    ap.add_argument("--out", default="preview.png", help="куда сохранить PNG")
    args = ap.parse_args()

    bg_hex = args.bg.lstrip("#")
    bg_rgb = tuple(int(bg_hex[i:i + 2], 16) for i in (0, 2, 4)) + (255,)

    render_preview(
        assets_dir=args.assets,
        database_path=args.database,
        hours_visible=args.hours,
        align=args.align,
        screen_w=args.width,
        screen_h=args.height,
        out_path=args.out,
        use_sample=args.sample,
        bg_color=bg_rgb,
    )


if __name__ == "__main__":
    main()