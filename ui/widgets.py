# -*- coding: utf-8 -*-
"""
Переиспользуемые UI-виджеты
"""

import customtkinter as ctk
from tkinter import colorchooser


class IntSliderRow(ctk.CTkFrame):
    """
    Строка с меткой, полем ввода и слайдером для целочисленного значения.
    """
    
    def __init__(self, parent, label, min_val, max_val, default, 
                 on_change, step=1, width=40):
        super().__init__(parent, fg_color="transparent")
        
        self.min_val = min_val
        self.max_val = max_val
        self.default = default
        self._on_change = on_change
        self._updating = False
        
        # Метка
        self.label = ctk.CTkLabel(self, text=label)
        self.label.pack(side="left")
        
        # Слайдер
        self.slider = WheelSlider(
            self, from_=min_val, to=max_val,
            number_of_steps=int((max_val - min_val) / step) if step > 0 else 100,
            command=self._on_slider
        )
        self.slider.set(default)
        self.slider.pack(side="left", padx=5, fill="x", expand=True)
        
        # Поле ввода
        self.entry = ctk.CTkEntry(self, width=width)
        self.entry.insert(0, str(default))
        self.entry.pack(side="right", padx=(5, 0))
        self.entry.bind("<KeyRelease>", self._on_entry)
        self.entry.bind("<FocusOut>", self._on_focus_out)
    
    def _on_slider(self, value):
        if self._updating:
            return
        val = int(value)
        self.entry.delete(0, "end")
        self.entry.insert(0, str(val))
        self._on_change(val)
    
    def _on_entry(self, event):
        self._update_from_entry(finalize=False)
    
    def _on_focus_out(self, event):
        self._update_from_entry(finalize=True)
    
    def _update_from_entry(self, finalize):
        if self._updating:
            return
        
        raw = self.entry.get().strip()
        if not raw:
            if not finalize:
                return
            val = self.default
        else:
            try:
                val = int(raw)
            except ValueError:
                return
        
        # Применяем границы
        val = max(self.min_val, min(self.max_val, val))
        
        if finalize and self.entry.get() != str(val):
            self._updating = True
            self.entry.delete(0, "end")
            self.entry.insert(0, str(val))
            self._updating = False
        
        self.slider.set(val)
        self._on_change(val)
    
    def set(self, value):
        """Устанавливает значение программно."""
        self._updating = True
        val = max(self.min_val, min(self.max_val, value))
        self.slider.set(val)
        self.entry.delete(0, "end")
        self.entry.insert(0, str(val))
        self._updating = False
    
    def get(self):
        """Возвращает текущее значение."""
        try:
            return int(self.entry.get())
        except ValueError:
            return self.default


class ColorPickerButton(ctk.CTkButton):
    """
    Кнопка выбора цвета с отображением текущего цвета.
    """
    
    def __init__(self, parent, initial_color="#ffffff", command=None, width=40, height=24):
        self._color = initial_color
        self._picker_callback = command
        self._enabled = True
        
        super().__init__(
            parent, text="", width=width, height=height,
            command=self._on_click, fg_color=initial_color if initial_color and initial_color != "transparent" else "gray"
        )
    
    def _on_click(self):
        if self._enabled and self._picker_callback:
            self._picker_callback()
    
    def set_color(self, color):
        """Устанавливает цвет кнопки."""
        self._color = color
        if color and color != "transparent":
            self.configure(fg_color=color)
        else:
            self.configure(fg_color="gray")
    
    def get_color(self):
        return self._color
    
    def configure(self, **kwargs):
        """Переопределяем configure для поддержки state."""
        if 'state' in kwargs:
            if kwargs['state'] == "disabled":
                self._enabled = False
            else:
                self._enabled = True
            del kwargs['state']
        super().configure(**kwargs)


class DirectionSelector(ctk.CTkFrame):
    """
    Выбор направления (для теней).
    """
    
    def __init__(self, parent, directions, variable, command=None):
        super().__init__(parent, fg_color="transparent")
        
        self._variable = variable
        self._command = command
        self._buttons = []
        
        for i in range(3):
            for j in range(3):
                idx = i * 3 + j
                if idx < len(directions):
                    btn = ctk.CTkRadioButton(
                        self, text=directions[idx]["symbol"],
                        variable=variable, value=directions[idx]["value"],
                        command=self._on_change,
                        width=24, radiobutton_width=16, radiobutton_height=16
                    )
                    btn.grid(row=i, column=j, padx=4, pady=2)
                    self._buttons.append(btn)
    
    def _on_change(self):
        if self._command:
            self._command(self._variable.get())
    
    def set(self, value):
        self._variable.set(value)
        
class AutoHideScrollFrame(ctk.CTkScrollableFrame):
    """
    CTkScrollableFrame, который автоматически прячет вертикальный
    скроллбар, когда контент помещается в видимую область.

    ВАЖНО: в CTk 5.2.x внутренний canvas НЕ использует create_window
    для контента — контент кладётся place-ом во внутренний фрейм
    (self). Поэтому canvas.bbox("all") возвращает размер VIEW, а не
    контента. Реальную высоту контента берём через
    self.winfo_reqheight().
    """

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._scrollbar_visible = False
        sb = self._get_scrollbar()
        if sb is not None:
            try:
                sb.grid_remove()
            except Exception:
                pass

        self.after(150, self.refresh_scrollbar)
        self.bind(
            "<Configure>",
            lambda e: self.after(50, self.refresh_scrollbar),
            add="+",
        )

    def _get_canvas(self):
        return getattr(self, "_parent_canvas", None)

    def _get_scrollbar(self):
        return getattr(self, "_scrollbar", None)

    def refresh_scrollbar(self):
        """Показать/скрыть скроллбар по реальной высоте содержимого."""
        canvas = self._get_canvas()
        sb = self._get_scrollbar()
        if canvas is None or sb is None:
            return

        try:
            # Суммируем высоты видимых детей с учётом pady.
            content_h = 0
            for w in self.winfo_children():
                if not w.winfo_ismapped():
                    continue
                content_h += w.winfo_reqheight()
                if w.winfo_manager() == "pack":
                    try:
                        pady = w.pack_info().get("pady", 0)
                        if isinstance(pady, (tuple, list)):
                            content_h += sum(pady)
                        else:
                            content_h += 2 * int(pady)
                    except Exception:
                        pass
            view_h = canvas.winfo_height()
        except Exception:
            return

        # Ждём, пока геометрия устаканится.
        if view_h <= 1:
            self.after(100, self.refresh_scrollbar)
            return

        need = content_h > view_h + 2

        if need and not self._scrollbar_visible:
            try:
                sb.grid()
            except Exception:
                pass
            self._scrollbar_visible = True
        elif not need and self._scrollbar_visible:
            try:
                sb.grid_remove()
            except Exception:
                pass
            self._scrollbar_visible = False
            
class WheelSlider(ctk.CTkSlider):
    """
    CTkSlider, который реагирует на колесо мыши при наведении.

    Поведение:
        - навёл курсор → прокрутил колесо → значение ±step;
        - без Shift — шаг 1 (как у CTkSlider по умолчанию);
        - событие НЕ всплывает дальше (return "break"),
          чтобы скролл не уходил родительскому ScrollableFrame.

    Используется вместо ctk.CTkSlider везде, где нужно колесо.
    """

    def __init__(self, master, *args, wheel_step=1, **kwargs):
        super().__init__(master, *args, **kwargs)
        self._wheel_step = wheel_step

        # Windows/macOS — <MouseWheel>, Linux — <Button-4>/<Button-5>.
        self.bind("<MouseWheel>", self._on_wheel, add="+")
        self.bind("<Button-4>", self._on_wheel_linux_up, add="+")
        self.bind("<Button-5>", self._on_wheel_linux_down, add="+")

    def _delta_to_sign(self, event):
        if event.delta > 0:
            return +1
        if event.delta < 0:
            return -1
        return 0

    def _apply(self, sign):
        if sign == 0:
            return "break"
        try:
            cur = float(self.get())
        except Exception:
            return "break"
        new = cur + sign * self._wheel_step

        # Ограничение по min/max из параметров слайдера.
        lo = self.cget("from_")
        hi = self.cget("to")
        if new < lo:
            new = lo
        elif new > hi:
            new = hi
        if new == cur:
            return "break"

        self.set(new)
        # CTkSlider не вызывает command при .set() — дёргаем вручную.
        cmd = self.cget("command")
        if cmd is not None:
            try:
                cmd(new)
            except Exception:
                pass
        return "break"

    def _on_wheel(self, event):
        return self._apply(self._delta_to_sign(event))

    def _on_wheel_linux_up(self, event):
        return self._apply(+1)

    def _on_wheel_linux_down(self, event):
        return self._apply(-1)