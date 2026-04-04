import tkinter as tk
from tkinter import ttk

def main():
    root = tk.Tk()
    root.title("Test")
    root.geometry("200x100")
    ttk.Label(root, text="Hello Tkinter").pack()
    root.update()
    root.after(1000, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    main()
