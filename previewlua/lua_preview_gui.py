# -*- coding: utf-8 -*-
"""
lua_preview_gui.py — GUI для универсального предпросмотра Lua-циферблатов.

Лежит рядом с lua_preview.py (использует его эмулятор lvgl/io/dataman).
Зависимости: pip install lupa pillow numpy   (tkinter входит в Python)

Возможности:
  - выбор .lua и папки с .bin / database.db
  - размер экрана, масштаб, фон: чёрный / шахматка (видна прозрачность) / свой цвет
  - Render (F5), авто-перерисовка при сохранении .lua или смене файлов в папке
  - сохранение PNG на выбранном фоне и PNG с прозрачным фоном
  - лог: print() из Lua, отсутствующие файлы, ошибки со строкой
"""
import contextlib
import io
import os
import sys
import traceback
import tkinter as tk
from tkinter import colorchooser, filedialog, ttk

from PIL import Image, ImageTk

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lua_preview as lp  # noqa: E402


def checkerboard(size, cell=10):
    w, h = size
    img = Image.new("RGBA", (w, h), (60, 60, 60, 255))
    px = img.load()
    for y in range(h):
        for x in range(w):
            if ((x // cell) + (y // cell)) % 2:
                px[x, y] = (90, 90, 90, 255)
    return img


class App:
    def __init__(self, root):
        self.root = root
        root.title("Lua Preview")
        self.transparent = None      # последний отрисованный кадр (RGBA, без фона)
        self.tk_img = None
        self.watch_state = None
        self.emu = None
        self.playing = False

        self.v_lua = tk.StringVar()
        self.v_dir = tk.StringVar()
        self.v_w = tk.IntVar(value=390)
        self.v_h = tk.IntVar(value=450)
        self.v_scale = tk.IntVar(value=1)
        self.v_bg = tk.StringVar(value="black")
        self.custom_color = "#202020"
        self.v_auto = tk.BooleanVar(value=True)

        self._build()
        root.bind("<F5>", lambda e: self.render())
        root.after(1000, self._poll)

    # ---------------- интерфейс ----------------
    def _build(self):
        top = ttk.Frame(self.root, padding=6)
        top.pack(fill="x")

        ttk.Label(top, text="Lua:").grid(row=0, column=0, sticky="e")
        ttk.Entry(top, textvariable=self.v_lua, width=55).grid(row=0, column=1, sticky="we")
        ttk.Button(top, text="Обзор…", command=self.pick_lua).grid(row=0, column=2, padx=3)

        ttk.Label(top, text="Папка .bin / db:").grid(row=1, column=0, sticky="e")
        ttk.Entry(top, textvariable=self.v_dir, width=55).grid(row=1, column=1, sticky="we")
        ttk.Button(top, text="Обзор…", command=self.pick_dir).grid(row=1, column=2, padx=3)
        top.columnconfigure(1, weight=1)

        opt = ttk.Frame(self.root, padding=(6, 0))
        opt.pack(fill="x")
        ttk.Label(opt, text="Экран:").pack(side="left")
        ttk.Spinbox(opt, from_=50, to=2000, textvariable=self.v_w, width=5).pack(side="left")
        ttk.Label(opt, text="×").pack(side="left")
        ttk.Spinbox(opt, from_=50, to=2000, textvariable=self.v_h, width=5).pack(side="left")
        ttk.Label(opt, text="  Масштаб:").pack(side="left")
        ttk.Spinbox(opt, from_=1, to=8, textvariable=self.v_scale, width=3,
                    command=self.refresh_view).pack(side="left")
        ttk.Label(opt, text="  Фон:").pack(side="left")
        for text, val in (("чёрный", "black"), ("шахматка", "checker"), ("свой", "custom")):
            ttk.Radiobutton(opt, text=text, value=val, variable=self.v_bg,
                            command=self.on_bg).pack(side="left")
        ttk.Checkbutton(opt, text="авто", variable=self.v_auto).pack(side="left", padx=8)

        timer_row = ttk.Frame(self.root, padding=(6, 0))
        timer_row.pack(fill="x")
        ttk.Label(timer_row, text="Время вперёд:").pack(side="left")
        self.v_advance = tk.StringVar(value="1s")
        ttk.Entry(timer_row, textvariable=self.v_advance, width=8).pack(side="left")
        ttk.Label(timer_row, text="(500ms, 30s, 15m, 2h)").pack(side="left", padx=(2, 10))
        ttk.Button(timer_row, text="Прокрутить", command=self.advance_once).pack(side="left")
        self.v_play = tk.StringVar(value="▶ Play")
        ttk.Button(timer_row, textvariable=self.v_play, command=self.toggle_play).pack(side="left", padx=6)
        ttk.Label(timer_row, text="  t=").pack(side="left")
        self.v_clock = tk.StringVar(value="0 мс")
        ttk.Label(timer_row, textvariable=self.v_clock).pack(side="left")

        btns = ttk.Frame(self.root, padding=6)
        btns.pack(fill="x")
        ttk.Button(btns, text="Render (F5)", command=self.render).pack(side="left")
        ttk.Button(btns, text="Сохранить PNG (с фоном)",
                   command=lambda: self.save(False)).pack(side="left", padx=4)
        ttk.Button(btns, text="Сохранить PNG (прозрачный)",
                   command=lambda: self.save(True)).pack(side="left")

        body = ttk.PanedWindow(self.root, orient="vertical")
        body.pack(fill="both", expand=True)

        view = ttk.Frame(body)
        self.canvas = tk.Canvas(view, bg="#333333", highlightthickness=0)
        sx = ttk.Scrollbar(view, orient="horizontal", command=self.canvas.xview)
        sy = ttk.Scrollbar(view, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side="bottom", fill="x")
        sy.pack(side="right", fill="y")
        self.canvas.pack(fill="both", expand=True)
        body.add(view, weight=4)

        logf = ttk.Frame(body)
        self.log = tk.Text(logf, height=8, wrap="word", font=("Consolas", 9))
        ls = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=ls.set)
        ls.pack(side="right", fill="y")
        self.log.pack(fill="both", expand=True)
        self.log.tag_config("err", foreground="#c00000")
        body.add(logf, weight=1)

        self.status = ttk.Label(self.root, text="Выберите .lua файл", anchor="w")
        self.status.pack(fill="x")

    # ---------------- выбор файлов ----------------
    def pick_lua(self):
        p = filedialog.askopenfilename(filetypes=[("Lua", "*.lua"), ("Все файлы", "*.*")])
        if p:
            self.v_lua.set(p)
            if not self.v_dir.get():
                self.v_dir.set(os.path.dirname(p))
            self.render()

    def pick_dir(self):
        p = filedialog.askdirectory()
        if p:
            self.v_dir.set(p)
            self.render()

    def on_bg(self):
        if self.v_bg.get() == "custom":
            c = colorchooser.askcolor(color=self.custom_color)[1]
            if c:
                self.custom_color = c
        self.refresh_view()

    # ---------------- рендер ----------------
    def log_write(self, text, tag=None):
        self.log.insert("end", text, tag)
        self.log.see("end")

    def render(self):
        lua_path = self.v_lua.get().strip()
        if not lua_path or not os.path.isfile(lua_path):
            self.status.config(text="Lua-файл не найден")
            return
        script_dir = self.v_dir.get().strip() or os.path.dirname(lua_path)

        self.log.delete("1.0", "end")
        buf = io.StringIO()
        try:
            canvas = lp.Canvas(int(self.v_w.get()), int(self.v_h.get()))
            canvas.bg = (0, 0, 0, 0)
            canvas._redraw()
            emu = lp.LuaEmulator(canvas, script_dir, "")
            with contextlib.redirect_stdout(buf):
                emu.run(lua_path)
            self.transparent = canvas.img.copy()
            self.emu = emu
            self.v_clock.set(f"{emu.scheduler.now} мс")
            self.status.config(text=f"OK: {os.path.basename(lua_path)}  "
                                    f"{canvas.w}×{canvas.h}, объектов: {len(canvas.commands)}")
        except Exception:
            self.log_write(buf.getvalue())
            self.log_write(traceback.format_exc(), "err")
            self.status.config(text="Ошибка выполнения — см. лог")
            return
        self.log_write(buf.getvalue() or "(нет вывода)\n")
        self.watch_state = self._snapshot()
        self.refresh_view()

    # ---------------- показ ----------------
    def _composited(self):
        if self.transparent is None:
            return None
        mode = self.v_bg.get()
        if mode == "checker":
            base = checkerboard(self.transparent.size)
        else:
            color = "#000000" if mode == "black" else self.custom_color
            c = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) + (255,)
            base = Image.new("RGBA", self.transparent.size, c)
        base.alpha_composite(self.transparent)
        return base

    def refresh_view(self):
        img = self._composited()
        if img is None:
            return
        s = max(1, int(self.v_scale.get() or 1))
        if s != 1:
            img = img.resize((img.width * s, img.height * s), Image.NEAREST)
        self.tk_img = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.tk_img, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, img.width, img.height))

    # ---------------- сохранение ----------------
    def advance_once(self):
        if self.emu is None:
            self.status.config(text="Сначала сделайте Render")
            return
        try:
            ms = lp.parse_duration(self.v_advance.get())
        except Exception:
            self.status.config(text="Не понял длительность, пример: 500ms / 30s / 15m")
            return
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            fired = self.emu.scheduler.advance(ms)
        self.log_write(buf.getvalue())
        self.transparent = self.emu.canvas.img.copy()
        self.v_clock.set(f"{self.emu.scheduler.now} мс")
        self.status.config(text=f"t={self.emu.scheduler.now} мс, сработало таймеров: {fired}")
        self.refresh_view()

    def toggle_play(self):
        self.playing = not self.playing
        self.v_play.set("⏸ Stop" if self.playing else "▶ Play")
        if self.playing:
            self._play_tick()

    def _play_tick(self):
        if not self.playing:
            return
        self.advance_once()
        self.root.after(500, self._play_tick)  # каждые 500 мс реального времени -- один шаг --advance

    def save(self, transparent):
        if self.transparent is None:
            return
        p = filedialog.asksaveasfilename(defaultextension=".png",
                                         filetypes=[("PNG", "*.png")],
                                         initialfile="preview_transparent.png" if transparent
                                         else "preview.png")
        if not p:
            return
        img = self.transparent if transparent else self._composited()
        s = max(1, int(self.v_scale.get() or 1))
        if s != 1:
            img = img.resize((img.width * s, img.height * s), Image.NEAREST)
        img.save(p)
        self.status.config(text=f"Сохранено: {p}")

    # ---------------- авто-перерисовка ----------------
    def _snapshot(self):
        lua = self.v_lua.get().strip()
        d = self.v_dir.get().strip() or (os.path.dirname(lua) if lua else "")
        snap = []
        try:
            snap.append(os.path.getmtime(lua))
            for fn in sorted(os.listdir(d)):
                if fn.endswith((".bin", ".db")):
                    snap.append((fn, os.path.getmtime(os.path.join(d, fn))))
        except OSError:
            pass
        return snap

    def _poll(self):
        if self.v_auto.get() and self.watch_state is not None:
            if self._snapshot() != self.watch_state:
                self.render()
        self.root.after(1000, self._poll)


def main():
    root = tk.Tk()
    app = App(root)
    if len(sys.argv) > 1:
        app.v_lua.set(os.path.abspath(sys.argv[1]))
        app.v_dir.set(os.path.abspath(sys.argv[2]) if len(sys.argv) > 2
                      else os.path.dirname(os.path.abspath(sys.argv[1])))
        root.after(100, app.render)
    root.mainloop()


if __name__ == "__main__":
    main()
