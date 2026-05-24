import threading
import tkinter as tk
from tkinter import messagebox
import queue


class ApprovalDialog:
    def __init__(self):
        self._result_queue = queue.Queue()
        self._request_queue = queue.Queue()

    def request_approval(self, device_name, device_ip):
        event = threading.Event()
        result = [None]
        self._request_queue.put((device_name, device_ip, event, result))
        event.wait()
        return result[0]

    def _show_dialog(self, root):
        try:
            device_name, device_ip, event, result = self._request_queue.get_nowait()
        except queue.Empty:
            root.after(100, lambda: self._show_dialog(root))
            return

        dialog = tk.Toplevel(root)
        dialog.title("Lazy Boy - Connection Request")
        dialog.geometry("480x280")
        dialog.resizable(False, False)
        dialog.attributes("-topmost", True)
        dialog.grab_set()
        dialog.configure(bg="#2c3e50")

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - 480) // 2
        y = (dialog.winfo_screenheight() - 280) // 2
        dialog.geometry(f"+{x}+{y}")

        frame = tk.Frame(dialog, padx=30, pady=20, bg="#2c3e50")
        frame.pack(fill=tk.BOTH, expand=True)

        icon_label = tk.Label(frame, text="?", font=("Segoe UI", 42, "bold"),
                               fg="#f39c12", bg="#2c3e50")
        icon_label.pack()

        msg = f'"{device_name}" ({device_ip})\nwants to control your PC.'
        msg_label = tk.Label(frame, text=msg, font=("Segoe UI", 13),
                              wraplength=420, fg="white", bg="#2c3e50")
        msg_label.pack(pady=12)

        btn_frame = tk.Frame(frame, bg="#2c3e50")
        btn_frame.pack(pady=15)

        def accept():
            result[0] = True
            event.set()
            dialog.destroy()

        def deny():
            result[0] = False
            event.set()
            dialog.destroy()

        accept_btn = tk.Button(
            btn_frame, text="  Accept  ", width=14, height=2,
            bg="#27ae60", fg="white", font=("Segoe UI", 14, "bold"),
            relief="flat", cursor="hand2", activebackground="#2ecc71",
            command=accept
        )
        accept_btn.pack(side=tk.LEFT, padx=15, ipady=4)

        deny_btn = tk.Button(
            btn_frame, text="  Deny  ", width=14, height=2,
            bg="#c0392b", fg="white", font=("Segoe UI", 14, "bold"),
            relief="flat", cursor="hand2", activebackground="#e74c3c",
            command=deny
        )
        deny_btn.pack(side=tk.LEFT, padx=15, ipady=4)

        def on_close():
            result[0] = False
            event.set()

        dialog.protocol("WM_DELETE_WINDOW", on_close)
        root.after(100, lambda: self._show_dialog(root))

    def start(self):
        self._root = tk.Tk()
        self._root.title("Lazy Boy Server")
        self._root.geometry("400x140")
        self._root.resizable(False, False)
        self._root.configure(bg="#2c3e50")

        frame = tk.Frame(self._root, padx=20, pady=20, bg="#2c3e50")
        frame.pack(fill=tk.BOTH, expand=True)

        status = tk.Label(frame, text="Lazy Boy Server Running",
                          font=("Segoe UI", 16, "bold"), fg="#27ae60", bg="#2c3e50")
        status.pack()

        info = tk.Label(frame, text="Waiting for connections...",
                        font=("Segoe UI", 11), fg="#95a5a6", bg="#2c3e50")
        info.pack(pady=8)

        self._root.after(100, lambda: self._show_dialog(self._root))
        self._root.mainloop()

    def stop(self):
        if hasattr(self, "_root"):
            self._root.quit()
