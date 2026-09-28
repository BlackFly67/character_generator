# -*- coding: utf-8 -*-
import os
import struct
import math
import numpy as np
from PIL import Image, ImageDraw
from lupa import LuaRuntime

SCRIPT_DIR = os.getcwd()          # переопределяется аргументом --dir
BG_COLOR   = (0, 0, 0, 255)      # переопределяется --bg
ANIM_FRAMES = 60


def read_lvgl_v8_bin(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        if len(data) < 4:
            return None
        val = struct.unpack("<I", data[:4])[0]
        w = (val >> 10) & 0x7FF
        h = (val >> 21) & 0x7FF
        if w == 0 or h == 0:
            return None
        expected = 4 + w * h * 4
        if len(data) < expected:
            return None
        px = data[4:4 + w * h * 4]
        arr = np.frombuffer(px, dtype=np.uint8).reshape(h, w, 4)
        b = arr[:, :, 0]; g = arr[:, :, 1]
        r = arr[:, :, 2]; a = arr[:, :, 3]
        rgba = np.stack([r, g, b, a], axis=-1).astype(np.uint8)
        return w, h, rgba
    except Exception:
        return None


def parse_color(c):
    if isinstance(c, int):
        r = (c >> 16) & 0xFF
        g = (c >> 8) & 0xFF
        b = c & 0xFF
        return (r, g, b, 255)
    if isinstance(c, str) and c.startswith("#"):
        h = c[1:]
        if len(h) == 6:
            r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
            return (r, g, b, 255)
        if len(h) == 8:
            a = int(h[0:2], 16); r = int(h[2:4], 16); g = int(h[4:6], 16); b = int(h[6:8], 16)
            return (r, g, b, a)
    return (255, 255, 255, 255)


class Canvas:
    def __init__(self, w, h):
        self.w = w
        self.h = h
        self.bg = BG_COLOR
        self.commands = []
        self.img = Image.new("RGBA", (w, h), self.bg)

    def add(self, owner_id, kind, data):
        self.commands = [c for c in self.commands if c[0] != owner_id]
        self.commands.append((owner_id, kind, data))
        self._redraw()

    def remove(self, owner_id):
        self.commands = [c for c in self.commands if c[0] != owner_id]
        self._redraw()

    def _redraw(self):
        self.img = Image.new("RGBA", (self.w, self.h), self.bg)
        for _, kind, data in self.commands:
            if kind == "bin":
                path, x, y, w, h = data
                res = read_lvgl_v8_bin(path)
                if not res:
                    continue
                iw, ih, rgba = res
                img = Image.fromarray(rgba, mode="RGBA")
                if w is not None and h is not None:
                    w = int(w); h = int(h)
                    if w > 0 and h > 0:
                        img = img.crop((0, 0, min(w, iw), min(h, ih)))
                self.img.alpha_composite(img, (int(x), int(y)))
            elif kind == "rect":
                x, y, w, h, color, radius, hidden = data
                if hidden:
                    continue
                x = int(x); y = int(y); w = int(w); h = int(h)
                if w <= 0 or h <= 0:
                    continue
                layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
                d = ImageDraw.Draw(layer)
                if radius >= min(w, h) / 2:
                    d.ellipse((0, 0, w - 1, h - 1), fill=color)
                elif radius > 0:
                    d.rounded_rectangle((0, 0, w - 1, h - 1), radius=radius, fill=color)
                else:
                    d.rectangle((0, 0, w - 1, h - 1), fill=color)
                self.img.alpha_composite(layer, (x, y))


class ObjectWrapper:
    _next_id = 0
    def __init__(self, parent, canvas, cfg=None):
        ObjectWrapper._next_id += 1
        self.id = ObjectWrapper._next_id
        self.parent = parent
        self.canvas = canvas
        self.cfg = {
            "x": 0, "y": 0, "w": 0, "h": 0,
            "bg_color": None, "bg_opa": 255,
            "radius": 0, "hidden": False,
        }
        if cfg:
            for k in cfg:
                self.cfg[k] = cfg[k]
        self._draw()

    def _color_with_opa(self):
        col = self.cfg.get("bg_color")
        if col is None:
            return None
        r, g, b, a = parse_color(col)
        opa = self.cfg.get("bg_opa", 255)
        try:
            opa = int(opa)
        except Exception:
            opa = 255
        if opa > 255:
            opa = 255
        a = a * opa // 255
        return (r, g, b, a)

    def _draw(self):
        col = self._color_with_opa()
        if col is None or col[3] == 0:
            self.canvas.remove(self.id)
            return
        data = (
            self.cfg.get("x", 0), self.cfg.get("y", 0),
            self.cfg.get("w", 0), self.cfg.get("h", 0),
            col, int(self.cfg.get("radius", 0)),
            bool(self.cfg.get("hidden", False)),
        )
        self.canvas.add(self.id, "rect", data)

    def set(self, tbl):
        if tbl:
            for k in tbl:
                self.cfg[k] = tbl[k]
        self._draw()
        return self

    def add_flag(self, flag):
        if flag == 3:
            self.cfg["hidden"] = True
            self._draw()
        return self

    def clear_flag(self, flag):
        if flag == 3:
            self.cfg["hidden"] = False
            self._draw()
        return self

    def delete(self):
        self.canvas.remove(self.id)

    def onevent(self, *args, **kwargs):
        return self

    def invalidate(self):
        self._draw()
        return self

    def __getattr__(self, name):
        def noop(*a, **k):
            return self
        return noop

    def __getitem__(self, key):
        # lupa транслирует Lua obj:method(...) через __getitem__ (как obj["method"]),
        # а не через обычный getattr -- поэтому сюда сначала нужно отдавать
        # РЕАЛЬНЫЙ метод/атрибут, если он есть, и только для несуществующих
        # имён возвращать no-op-заглушку. Раньше здесь был безусловный noop,
        # из-за чего вообще ВСЕ вызовы через двоеточие (:set(), :delete(),
        # :add_flag() и т.д.) молча ничего не делали.
        attr = getattr(self, key, None)
        if attr is not None:
            return attr
        def noop(*a, **k):
            return self
        return noop


class ImageWrapper:
    _next_id = 0
    def __init__(self, parent, canvas, script_dir, image_path, cfg):
        ImageWrapper._next_id += 1
        self.id = ImageWrapper._next_id
        self.parent = parent
        self.canvas = canvas
        self.script_dir = script_dir
        self.image_path = image_path
        self.cfg = {}
        if cfg:
            for k in cfg:
                self.cfg[k] = cfg[k]
        self.parent_w = None
        self.parent_h = None
        if parent is not None and hasattr(parent, "cfg"):
            self.parent_w = parent.cfg.get("w")
            self.parent_h = parent.cfg.get("h")
        self._draw()

    def _resolve_pos(self):
        x = self.cfg.get("x")
        y = self.cfg.get("y")
        align = self.cfg.get("align")
        w = self.cfg.get("w")
        h = self.cfg.get("h")
        if (x is None or y is None) and align is not None:
            pw = self.parent_w or self.canvas.w
            ph = self.parent_h or self.canvas.h
            if w is None or h is None:
                src = self.cfg.get("src")
                if src:
                    file_name = src
                    if self.image_path and src.startswith(self.image_path):
                        file_name = src[len(self.image_path):]
                    full = os.path.join(self.script_dir, self.image_path, file_name)
                    res = read_lvgl_v8_bin(full)
                    if res:
                        w, h = res[0], res[1]
            w = w or 0
            h = h or 0
            if align == 0:
                x = (pw - w) // 2; y = (ph - h) // 2
            elif align == 1:
                x, y = 0, 0
            elif align == 2:
                x = (pw - w) // 2; y = 0
            elif align == 3:
                x = pw - w; y = 0
            elif align == 4:
                x = 0; y = (ph - h) // 2
            elif align == 5:
                x = pw - w; y = (ph - h) // 2
            elif align == 6:
                x = 0; y = ph - h
            elif align == 7:
                x = (pw - w) // 2; y = ph - h
            elif align == 8:
                x = pw - w; y = ph - h
        return int(x or 0), int(y or 0)

    def _draw(self):
        src = self.cfg.get("src")
        if not src:
            self.canvas.remove(self.id)
            return
        x, y = self._resolve_pos()
        w = self.cfg.get("w")
        h = self.cfg.get("h")
        file_name = src
        if self.image_path and src.startswith(self.image_path):
            file_name = src[len(self.image_path):]
        full = os.path.join(self.script_dir, self.image_path, file_name)
        self.canvas.add(self.id, "bin", (full, x, y, w, h))

    def set(self, tbl):
        if tbl:
            for k in tbl:
                self.cfg[k] = tbl[k]
        self._draw()
        return self

    def set_src(self, src):
        self.cfg["src"] = src
        self._draw()
        return self

    def invalidate(self):
        self._draw()
        return self

    def add_flag(self, *_):
        return self
    def clear_flag(self, *_):
        return self
    def delete(self):
        self.canvas.remove(self.id)

    def onevent(self, *args, **kwargs):
        return self

    def __getattr__(self, name):
        def noop(*a, **k):
            return self
        return noop

    def __getitem__(self, key):
        # lupa транслирует Lua obj:method(...) через __getitem__ (как obj["method"]),
        # а не через обычный getattr -- поэтому сюда сначала нужно отдавать
        # РЕАЛЬНЫЙ метод/атрибут, если он есть, и только для несуществующих
        # имён возвращать no-op-заглушку. Раньше здесь был безусловный noop,
        # из-за чего вообще ВСЕ вызовы через двоеточие (:set(), :delete(),
        # :add_flag() и т.д.) молча ничего не делали.
        attr = getattr(self, key, None)
        if attr is not None:
            return attr
        def noop(*a, **k):
            return self
        return noop


class TimerWrapper:
    def __init__(self, cfg):
        self.cfg = {}
        if cfg:
            for k in cfg:
                self.cfg[k] = cfg[k]
    def pause(self): return self
    def resume(self): return self
    def reset(self): return self
    def delete(self): pass


class LuaFile:
    def __init__(self, f):
        self.f = f
        self.closed = False
    def read(self, fmt=None):
        if fmt is None or fmt == "*a" or fmt == "a":
            return self.f.read()
        if fmt == "*l" or fmt == "l":
            line = self.f.readline()
            if isinstance(line, bytes) and line.endswith(b"\n"):
                line = line[:-1]
            return line
        if fmt == "*n" or fmt == "n":
            buf = b""
            while True:
                ch = self.f.read(1)
                if not ch:
                    break
                if ch in b"0123456789+-.eE":
                    buf += ch
                else:
                    self.f.seek(self.f.tell() - 1)
                    break
            try:
                return float(buf) if (b"." in buf or b"e" in buf or b"E" in buf) else int(buf)
            except ValueError:
                return None
        if isinstance(fmt, int):
            return self.f.read(fmt)
        return self.f.read()
    def seek(self, whence, offset=None):
        if offset is None:
            return self.f.seek(0, 1)
        wmap = {"set": 0, "cur": 1, "end": 2}
        w = wmap.get(whence, 0)
        return self.f.seek(offset, w)
    def close(self):
        self.f.close()
        self.closed = True
    def write(self, *args):
        for a in args:
            self.f.write(a)
    def flush(self):
        self.f.flush()
    def lines(self):
        for line in self.f:
            yield line


def make_io(script_dir):
    real_open = open
    def open_(path, mode="r"):
        local = os.path.join(script_dir, os.path.basename(path))
        if not os.path.exists(local):
            print(f"  [io.open] нет файла: {local}")
            return None
        f = real_open(local, mode)
        return LuaFile(f)
    return {"open": open_}


class DatamanStub:
    def __init__(self):
        self.subscriptions = []
    def subscribe(self, *args):
        print(f"  [dataman.subscribe] args={len(args)}")
        if len(args) >= 3:
            event = args[0]
            callback = args[-1]
            self.subscriptions.append((event, callback))
        return None
    def fire(self, event, times=1):
        print(f"  [dataman.fire] event={event}, subs={len(self.subscriptions)}")
        for ev, cb in self.subscriptions:
            print(f"    sub: {ev}")
            if ev == event:
                for i in range(times):
                    try:
                        cb(None)
                    except Exception as e:
                        print(f"    error: {e}")


class LVGLFacade:
    def __init__(self, canvas, script_dir, image_path):
        self.canvas = canvas
        self.script_dir = script_dir
        self.image_path = image_path

    def Image(self, parent, cfg):
        return ImageWrapper(parent, self.canvas, self.script_dir, self.image_path, cfg)

    def Object(self, parent, cfg):
        return ObjectWrapper(parent, self.canvas, cfg)

    def Timer(self, cfg):
        return TimerWrapper(cfg)

    def OPA(self, v):
        return v

    def HOR_RES(self):
        return self.canvas.w

    def VER_RES(self):
        return self.canvas.h

    def __getattr__(self, name):
        def noop(*a, **k):
            return None
        return noop


class LuaEmulator:
    def __init__(self, canvas, script_dir, image_path):
        self.canvas = canvas
        self.script_dir = script_dir
        self.image_path = image_path
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.lvgl_facade = LVGLFacade(canvas, script_dir, image_path)
        self.dataman = DatamanStub()

    def run(self, lua_path):
        lua = self.lua
        g = lua.globals()
        g.math   = lua.eval("require('math')")
        g.string = lua.eval("require('string')")
        g.os     = lua.eval("require('os')")
        g.table  = lua.eval("require('table')")
        g.io = lua.table_from(make_io(self.script_dir))
        g.dataman = lua.table_from({"subscribe": self.dataman.subscribe})

        lvgl_table = lua.table()
        lvgl_table["Image"]   = self.lvgl_facade.Image
        lvgl_table["Object"]  = self.lvgl_facade.Object
        lvgl_table["Timer"]   = self.lvgl_facade.Timer
        lvgl_table["OPA"]     = self.lvgl_facade.OPA
        lvgl_table["HOR_RES"] = self.lvgl_facade.HOR_RES
        lvgl_table["VER_RES"] = self.lvgl_facade.VER_RES
        lvgl_table["FLAG"] = lua.table_from({
            "EVENT_BUBBLE": 1, "SCROLLABLE": 2, "HIDDEN": 3,
        })
        lvgl_table["ALIGN"] = lua.table_from({
            "CENTER": 0, "TOP_LEFT": 1, "TOP_MID": 2, "TOP_RIGHT": 3,
            "LEFT_MID": 4, "RIGHT_MID": 5,
            "BOTTOM_LEFT": 6, "BOTTOM_MID": 7, "BOTTOM_RIGHT": 8,
        })
        lvgl_table["EVENT"] = lua.table_from({
            "CLICKED": 1, "PRESSED": 2, "RELEASED": 3,
        })
        lvgl_table["RADIUS_CIRCLE"] = 9999
        g.lvgl = lvgl_table
        g.SCRIPT_PATH = self.image_path
        g.print = print

        def require(name):
            if name == "lvgl": return lvgl_table
            if name == "math": return g.math
            if name == "string": return g.string
            if name == "os": return g.os
            if name == "io": return g.io
            if name == "dataman": return g.dataman
            return None
        g.require = require

        with open(lua_path, "r", encoding="utf-8") as f:
            code = f.read()

        lines = code.split("\n")
        while lines and lines[0].lstrip().startswith("#"):
            lines.pop(0)
        code = "\n".join(lines)

        lua.execute(code)
        try:
            lua.eval("ScreenStateChangedCB('OFF', 'ON', 'emu')")
        except Exception as e:
            print(f"  [WARN] ScreenStateChangedCB: {e}")

        self.dataman.fire("timeCentiSecond", times=ANIM_FRAMES)


def main():
    import argparse
    global SCRIPT_DIR, BG_COLOR
    ap = argparse.ArgumentParser(
        description="Универсальный предпросмотр Lua-циферблатов: реально выполняет "
                    ".lua через lupa с заглушками lvgl/io/dataman и сохраняет PNG.")
    ap.add_argument("lua", help="путь к .lua файлу")
    ap.add_argument("--dir", default=None,
                    help="папка с .bin и database.db (по умолчанию -- папка .lua файла). "
                         "io.open() ищет файлы по ИМЕНИ в этой папке, путь игнорируется")
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=450)
    ap.add_argument("--bg", default="#000000")
    ap.add_argument("--scale", type=int, default=1, help="увеличение итогового PNG")
    ap.add_argument("--out", default="preview.png")
    args = ap.parse_args()

    lua_full = os.path.abspath(args.lua)
    SCRIPT_DIR = os.path.abspath(args.dir) if args.dir else os.path.dirname(lua_full)
    h = args.bg.lstrip("#")
    BG_COLOR = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)

    canvas = Canvas(args.width, args.height)
    canvas.bg = (0, 0, 0, 0)          # холст прозрачный: фон добавляется только в предпросмотр
    canvas._redraw()
    emu = LuaEmulator(canvas, SCRIPT_DIR, "")
    emu.run(lua_full)

    transparent = canvas.img.copy()
    preview = Image.new("RGBA", transparent.size, BG_COLOR)
    preview.alpha_composite(transparent)

    if args.scale != 1:
        size = (transparent.width * args.scale, transparent.height * args.scale)
        transparent = transparent.resize(size, Image.NEAREST)
        preview = preview.resize(size, Image.NEAREST)

    base, ext = os.path.splitext(args.out)
    out_transparent = f"{base}_transparent{ext or '.png'}"
    preview.save(args.out)
    transparent.save(out_transparent)
    print(f"Предпросмотр (фон {args.bg}): {args.out}")
    print(f"Прозрачный PNG:               {out_transparent}")


if __name__ == "__main__":
    main()