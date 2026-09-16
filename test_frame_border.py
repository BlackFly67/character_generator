"""Проверка: CTkFrame с border_width + CTkLabel внутри + bind."""
import customtkinter as ctk
from PIL import Image, ImageDraw

root = ctk.CTk()
root.geometry("400x200")

# Красный круг 40×40 как «иконка».
img = Image.new("RGBA", (80, 80), (0, 0, 0, 0))
d = ImageDraw.Draw(img)
d.ellipse([4, 4, 76, 76], fill=(255, 0, 0, 255))
ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(32, 32))

frame = ctk.CTkFrame(
    root,
    fg_color=("#e8e8e8", "#3a3a3a"),
    corner_radius=4,
    width=52, height=40,
    border_width=2,
    border_color="#26a69a",
)
frame.pack(pady=20)
frame.grid_propagate(False)
frame.pack_propagate(False)

lbl = ctk.CTkLabel(frame, text="", image=ctk_img, fg_color="transparent")
lbl.place(relx=0.5, rely=0.5, anchor="center")

frame.bind("<Button-1>", lambda e: print("click"))
lbl.bind("<Button-1>", lambda e: print("click"))

root.mainloop()