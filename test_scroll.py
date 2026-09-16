import customtkinter as ctk
from ui.widgets import AutoHideScrollFrame


root = ctk.CTk()
root.geometry("400x300")

sf = AutoHideScrollFrame(root, width=300, height=150)
sf.pack(pady=20)

# Смотрим ВСЕХ детей sf — что там вообще есть.
def dump_children():
    print("\n--- children of AutoHideScrollFrame ---")
    for c in sf.winfo_children():
        print(f"  {c}  class={c.winfo_class()}  "
              f"mapped={c.winfo_ismapped()}  "
              f"reqh={c.winfo_reqheight()}  "
              f"h={c.winfo_height()}")

dump_children()

ctk.CTkLabel(sf, text="Строка 1").pack()
sf.update_idletasks()
sf.refresh_scrollbar()
dump_children()


def add_many():
    for i in range(2, 30):
        ctk.CTkLabel(sf, text=f"Строка {i}").pack()
    sf.update_idletasks()
    sf.refresh_scrollbar()
    dump_children()


root.after(1000, add_many)
root.mainloop()