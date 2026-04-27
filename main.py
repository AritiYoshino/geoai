# main.py
import tkinter as tk
from gui import GISApp

if __name__ == "__main__":
    root = tk.Tk()
    app = GISApp(root)
    root.mainloop()