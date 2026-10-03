# -*- coding: utf-8 -*-
import os
import struct
import math
import numpy as np
from PIL import Image, ImageDraw
from lupa import LuaRuntime

SCRIPT_DIR = os.getcwd()
BG_COLOR   = (0, 0, 0, 255)
ANIM_FRAMES = 60


def read_lvgl_v8_bin(path):
    try:
        with open(path, "rb") as f:
            data = f.read()
        if len(data) < 4:
            return None
        val = struct.unpack("<I", data[:4])[0]
        cf = val & 0x1F
        w = (val >> 10) & 0x7FF
        h = (val >> 21) & 0x7FF
        if w == 0 or h == 0:
            return None

        # cf=5: TRUE_COLOR_ALPHA (BGRA8888, 4 байта/пиксель)
        if cf == 5:
            expected = 4 + w * h * 4
            if len(data) < expected:
                return None
            px = data[4:4 + w * h * 4]
            arr = np.frombuffer(px, dtype=np.uint8).reshape(h, w, 4)
            b = arr[:, :, 0]; g = arr[:, :, 1]
            r = arr[:, :, 2]; a = arr[:, :, 3]
            rgba = np.stack([r, g, b, a], axis=-1).astype(np.uint8)
            return w, h, rgba

        # cf=4: TRUE_COLOR (RGB565, 2 байта/пиксель)
        if cf == 4:
            expected = 4 + w * h * 2
            if len(data) < expected:
                return None
            px = data[4:4 + w * h * 2]
            arr = np.frombuffer(px, dtype=np.uint8).reshape(h, w, 2)
            rgb565 = arr[:, :, 0].astype(np.uint16) | (arr[:, :, 1].astype(np.uint16) << 8)
            r = ((rgb565 >> 11) & 0x1F) << 3
            g = ((rgb565 >> 5) & 0x3F) << 2
            b = (rgb565 & 0x1F) << 3
            r = r | (r >> 5); g = g | (g >> 6); b = b | (b >> 5)
            a = np.full((h, w), 255, dtype=np.uint8)
            rgba = np.stack([r, g, b, a], axis=-1).astype(np.uint8)
            return w, h, rgba

        # cf=10: INDEXED_8BIT (палитра 256*4 BGRA + w*h индексов)
        if cf == 10:
            palette_size = 256 * 4
            expected = 4 + palette_size + w * h
            if len(data) < expected:
                return None
            palette = data[4:4 + palette_size]
            indices = data[4 + palette_size:4 + palette_size + w * h]
            pal = np.frombuffer(palette, dtype=np.uint8).reshape(256, 4)
            idx = np.frombuffer(indices, dtype=np.uint8).reshape(h, w)
            bgra = pal[idx]
            b = bgra[:, :, 0]; g = bgra[:, :, 1]
            r = bgra[:, :, 2]; a = bgra[:, :, 3]
            rgba = np.stack([r, g, b, a], axis=-1).astype(np.uint8)
            return w, h, rgba

        return None
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
        self._events = []
        self.cfg = {"x": 0, "y": 0, "w": 0, "h": 0,
                    "bg_color": None, "bg_opa": 255, "radius": 0, "hidden": False}
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
        if opa > 255: opa = 255
        a = a * opa // 255
        return (r, g, b, a)

    def _draw(self):
        col = self._color_with_opa()
        if col is None or col[3] == 0:
            self.canvas.remove(self.id)
            return
        data = (self.cfg.get("x", 0), self.cfg.get("y", 0),
                self.cfg.get("w", 0), self.cfg.get("h", 0),
                col, int(self.cfg.get("radius", 0)),
                bool(self.cfg.get("hidden", False)))
        self.canvas.add(self.id, "rect", data)

    def set(self, tbl):
        if tbl:
            for k in tbl: self.cfg[k] = tbl[k]
        self._draw()
        return self
    def add_flag(self, flag):
        if flag == 3:
            self.cfg["hidden"] = True; self._draw()
        return self
    def clear_flag(self, flag):
        if flag == 3:
            self.cfg["hidden"] = False; self._draw()
        return self
    def delete(self): self.canvas.remove(self.id)
    def onevent(self, event=None, callback=None):
        if event is not None and callback is not None:
            self._events.append((event, callback))
        return self
    def invalidate(self): self._draw(); return self
    def __getattr__(self, name):
        def noop(*a, **k): return self
        return noop
    def __getitem__(self, key):
        attr = getattr(self, key, None)
        if attr is not None: return attr
        def noop(*a, **k): return self
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
        self._events = []
        self.cfg = {}
        if cfg:
            for k in cfg: self.cfg[k] = cfg[k]
        self.parent_w = None
        self.parent_h = None
        if parent is not None and hasattr(parent, "cfg"):
            self.parent_w = parent.cfg.get("w")
            self.parent_h = parent.cfg.get("h")
        self._draw()

    def _resolve_pos(self):
        x = self.cfg.get("x"); y = self.cfg.get("y")
        align = self.cfg.get("align")
        w = self.cfg.get("w"); h = self.cfg.get("h")
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
                    if res: w, h = res[0], res[1]
            w = w or 0; h = h or 0
            if align == 0: x, y = (pw - w) // 2, (ph - h) // 2
            elif align == 1: x, y = 0, 0
            elif align == 2: x, y = (pw - w) // 2, 0
            elif align == 3: x, y = pw - w, 0
            elif align == 4: x, y = 0, (ph - h) // 2
            elif align == 5: x, y = pw - w, (ph - h) // 2
            elif align == 6: x, y = 0, ph - h
            elif align == 7: x, y = (pw - w) // 2, ph - h
            elif align == 8: x, y = pw - w, ph - h
        return int(x or 0), int(y or 0)

    def _draw(self):
        src = self.cfg.get("src")
        if not src:
            self.canvas.remove(self.id); return
        x, y = self._resolve_pos()
        w = self.cfg.get("w"); h = self.cfg.get("h")
        file_name = src
        if self.image_path and src.startswith(self.image_path):
            file_name = src[len(self.image_path):]
        full = os.path.join(self.script_dir, self.image_path, file_name)
        self.canvas.add(self.id, "bin", (full, x, y, w, h))

    def set(self, tbl):
        if tbl:
            for k in tbl: self.cfg[k] = tbl[k]
        self._draw()
        return self
    def set_src(self, src): self.cfg["src"] = src; self._draw(); return self
    def invalidate(self): self._draw(); return self
    def add_flag(self, *_): return self
    def clear_flag(self, *_): return self
    def delete(self): self.canvas.remove(self.id)
    def onevent(self, event=None, callback=None):
        if event is not None and callback is not None:
            self._events.append((event, callback))
        return self
    def __getattr__(self, name):
        def noop(*a, **k): return self
        return noop
    def __getitem__(self, key):
        attr = getattr(self, key, None)
        if attr is not None: return attr
        def noop(*a, **k): return self
        return noop


class Scheduler:
    MAX_FIRES = 100000
    def __init__(self): self.now = 0; self.timers = []
    def add(self, timer): self.timers.append(timer)
    def advance(self, ms):
        target = self.now + int(ms); fired = 0
        while fired < self.MAX_FIRES:
            due = [t for t in self.timers
                   if not t.deleted and not t.paused and t.period > 0 and t.next_fire <= target]
            if not due: break
            t = min(due, key=lambda x: x.next_fire)
            self.now = t.next_fire; t.fire(); fired += 1
        self.now = target
        self.timers = [t for t in self.timers if not t.deleted]
        return fired


class TimerWrapper:
    def __init__(self, cfg, scheduler):
        self.cfg = {}
        if cfg:
            for k in cfg: self.cfg[k] = cfg[k]
        self.scheduler = scheduler
        self.period = int(self.cfg.get("period") or 0)
        rc = self.cfg.get("repeat_count")
        self.repeat = -1 if rc is None else int(rc)
        self.cb = self.cfg.get("cb")
        self.paused = False; self.deleted = False
        self.next_fire = scheduler.now + self.period
        scheduler.add(self)
    def fire(self):
        if self.cb is not None:
            try: self.cb(self)
            except Exception as e: print(f"  [Timer] ошибка: {e}")
        if self.repeat > 0:
            self.repeat -= 1
            if self.repeat == 0: self.deleted = True
        self.next_fire += self.period
    def pause(self): self.paused = True; return self
    def resume(self): self.paused = False; self.next_fire = self.scheduler.now + self.period; return self
    def reset(self): self.next_fire = self.scheduler.now + self.period; return self
    def set_period(self, ms): self.period = int(ms); return self
    def delete(self): self.deleted = True
    def __getattr__(self, name):
        def noop(*a, **k): return self
        return noop
    def __getitem__(self, key):
        attr = getattr(self, key, None)
        if attr is not None: return attr
        def noop(*a, **k): return self
        return noop


class DatamanStub:
    def __init__(self): self.subscriptions = []
    def subscribe(self, *args):
        if len(args) >= 3:
            self.subscriptions.append((args[0], args[-1]))
        return None
    def fire(self, event, times=1):
        for ev, cb in self.subscriptions:
            if ev == event:
                for i in range(times):
                    try: cb(None)
                    except Exception as e: print(f"    error: {e}")


class LVGLFacade:
    def __init__(self, canvas, script_dir, image_path, scheduler=None):
        self.canvas = canvas
        self.script_dir = script_dir
        self.image_path = image_path
        self.scheduler = scheduler or Scheduler()
        self.widgets = []

    def Image(self, parent, cfg):
        w = ImageWrapper(parent, self.canvas, self.script_dir, self.image_path, cfg)
        self.widgets.append(w); return w
    def Object(self, parent, cfg):
        w = ObjectWrapper(parent, self.canvas, cfg)
        self.widgets.append(w); return w
    def Timer(self, cfg): return TimerWrapper(cfg, self.scheduler)
    def OPA(self, v): return v
    def HOR_RES(self): return self.canvas.w
    def VER_RES(self): return self.canvas.h
    def __getattr__(self, name):
        def noop(*a, **k): return None
        return noop


class LuaEmulator:
    def __init__(self, canvas, script_dir):
        self.canvas = canvas
        self.script_dir = script_dir
        self.image_path = script_dir.replace("\\", "/").rstrip("/") + "/"
        self.lua = LuaRuntime(unpack_returned_tuples=True)
        self.scheduler = Scheduler()
        self.lvgl_facade = LVGLFacade(canvas, script_dir, self.image_path, self.scheduler)
        self.dataman = DatamanStub()

    def run(self, lua_path):
        lua = self.lua
        g = lua.globals()
        g.math   = lua.eval("require('math')")
        g.string = lua.eval("require('string')")
        g.os     = lua.eval("require('os')")
        g.table  = lua.eval("require('table')")

        g.io = lua.eval("require('io')")

        script_dir_lua = self.image_path
        lua.execute(f"""
            local _script_dir = [==[{script_dir_lua}]==]
            local _real_open = io.open
            io.open = function(path, mode)
                local f = _real_open(path, mode)
                if f then return f end
                local base = path:match("([^/\\\\]+)$")
                if base then
                    local alt = _script_dir .. base
                    f = _real_open(alt, mode)
                    if f then return f end
                end
                return nil
            end
        """)

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

    def click_all(self, times=1):
        CLICKED = 1
        total = 0
        for _ in range(times):
            for w in self.lvgl_facade.widgets:
                events = getattr(w, "_events", None)
                if not events:
                    continue
                for ev, cb in events:
                    if ev == CLICKED:
                        try:
                            cb(None)
                            total += 1
                        except Exception as e:
                            print(f"  [click] ошибка: {e}")
                        break
        print(f"  [click] вызвано CLICKED-колбэков: {total}")
        return total

    def click_at(self, x, y):
        CLICKED = 1
        candidates = []
        for w in self.lvgl_facade.widgets:
            events = getattr(w, "_events", None)
            if not events:
                continue
            has_clicked = any(ev == CLICKED for ev, _ in events)
            if not has_clicked:
                continue
            cfg = getattr(w, "cfg", None)
            if not cfg:
                continue
            wx = cfg.get("x", 0)
            wy = cfg.get("y", 0)
            ww = cfg.get("w", 0)
            wh = cfg.get("h", 0)
            if wx is None or wy is None or ww is None or wh is None:
                continue
            if ww <= 0 or wh <= 0:
                continue
            if wx <= x < wx + ww and wy <= y < wy + wh:
                candidates.append((wx, wy, w))
        if not candidates:
            print(f"  [click] нет виджета в точке ({x}, {y})")
            return 0
        candidates.sort(key=lambda c: (c[0], c[1]))
        _, _, w = candidates[-1]
        total = 0
        for ev, cb in w._events:
            if ev == CLICKED:
                try:
                    cb(None)
                    total += 1
                except Exception as e:
                    print(f"  [click] ошибка: {e}")
        print(f"  [click] в точке ({x}, {y}) вызвано: {total}")
        return total


def parse_duration(text):
    t = str(text).strip().lower()
    for suffix, mul in (("ms", 1), ("s", 1000), ("m", 60000), ("h", 3600000)):
        if t.endswith(suffix) and t[:-len(suffix)].replace(".", "", 1).isdigit():
            return int(float(t[:-len(suffix)]) * mul)
    return int(float(t))


def main():
    import argparse
    global SCRIPT_DIR, BG_COLOR
    ap = argparse.ArgumentParser()
    ap.add_argument("lua")
    ap.add_argument("--dir", default=None)
    ap.add_argument("--width", type=int, default=390)
    ap.add_argument("--height", type=int, default=450)
    ap.add_argument("--bg", default="#000000")
    ap.add_argument("--scale", type=int, default=1)
    ap.add_argument("--advance", default=None)
    ap.add_argument("--click", type=int, default=0)
    ap.add_argument("--out", default="preview.png")
    args = ap.parse_args()

    lua_full = os.path.abspath(args.lua)
    SCRIPT_DIR = os.path.abspath(args.dir) if args.dir else os.path.dirname(lua_full)
    h = args.bg.lstrip("#")
    BG_COLOR = tuple(int(h[i:i + 2], 16) for i in (0, 2, 4)) + (255,)

    canvas = Canvas(args.width, args.height)
    canvas.bg = (0, 0, 0, 0)
    canvas._redraw()
    emu = LuaEmulator(canvas, SCRIPT_DIR)
    emu.run(lua_full)

    if args.advance:
        ms = parse_duration(args.advance)
        fired = emu.scheduler.advance(ms)
        print(f"Время прокручено на {ms} мс, таймеров: {fired}")

    if args.click > 0:
        emu.click_all(times=args.click)

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
    print(f"Предпросмотр: {args.out}")
    print(f"Прозрачный:   {out_transparent}")


if __name__ == "__main__":
    main()