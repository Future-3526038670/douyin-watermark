import tkinter as tk
from ui.app import DouyinApp


def main():
    root = tk.Tk()
    app = DouyinApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
