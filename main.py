import tkinter as tk
from tkinter import ttk, filedialog
import serial
import serial.tools.list_ports
import threading
import queue
import time
import os
import zlib

DOWNLOAD_DIR = "LittleFS"

def center_window(window, parent, width, height):
    parent.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


class CustomMessageDialog(tk.Toplevel):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)

        try:
            self.attributes('-toolwindow', True)
        except:
            pass

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        lbl = ttk.Label(self, text=message, padding=20, justify=tk.CENTER, wraplength=350)
        lbl.pack(fill=tk.BOTH, expand=True)

        ttk.Button(self, text="ОК", command=self.destroy).pack(pady=(0, 15))

        center_window(self, parent, 320, 140)
        self.grab_set()
        self.wait_window()


class CustomConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.title(title)
        self.result = False
        self.transient(parent)
        self.resizable(False, False)
        try:
            self.attributes('-toolwindow', True)
        except:
            pass

        self.protocol("WM_DELETE_WINDOW", self.on_no)

        lbl = ttk.Label(self, text=message, padding=20, justify=tk.CENTER)
        lbl.pack(fill=tk.BOTH, expand=True)

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="Да", command=self.on_yes).pack(side=tk.LEFT, expand=True, padx=10)
        ttk.Button(btn_frame, text="Нет", command=self.on_no).pack(side=tk.RIGHT, expand=True, padx=10)

        center_window(self, parent, 320, 140)
        self.grab_set()
        self.wait_window()

    def on_yes(self):
        self.result = True
        self.destroy()

    def on_no(self):
        self.result = False
        self.destroy()


class CustomInputDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, initialvalue=""):
        super().__init__(parent)
        self.title(title)
        self.result = False
        self.transient(parent)
        self.resizable(False, False)
        try:
            self.attributes('-toolwindow', True)
        except:
            pass

        self.protocol("WM_DELETE_WINDOW", self.on_cancel)

        ttk.Label(self, text=prompt, padding=(15, 15, 15, 5)).pack(anchor=tk.W)

        self.entry_var = tk.StringVar(value=initialvalue)
        self.entry = ttk.Entry(self, textvariable=self.entry_var, width=60, font=('Arial', 10))
        self.entry.pack(padx=15, pady=5, fill=tk.X)
        self.entry.select_range(0, tk.END)
        self.entry.focus_set()

        btn_frame = ttk.Frame(self, padding=10)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="ОК", command=self.on_ok).pack(side=tk.LEFT, expand=True, padx=10)
        ttk.Button(btn_frame, text="Отмена", command=self.on_cancel).pack(side=tk.RIGHT, expand=True, padx=10)

        self.bind('<Return>', lambda e: self.on_ok())
        self.bind('<Escape>', lambda e: self.on_cancel())

        center_window(self, parent, 320, 140)
        self.grab_set()
        self.wait_window()

    def on_ok(self):
        self.result = self.entry_var.get()
        self.destroy()

    def on_cancel(self):
        self.result = None
        self.destroy()



class LFSFileManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LittleFS Desktop Manager (ESP8266/ESP32)")

        app_width = 750
        app_height = 550
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        x = (screen_width // 2) - (app_width // 2)
        y = (screen_height // 2) - (app_height // 2)

        self.root.geometry(f"{app_width}x{app_height}+{x}+{y}")

        try:
            self.root.iconbitmap("icon.ico")
        except Exception:
            pass

        self.ser = None
        self.task_queue = queue.Queue()
        self.is_connected = False

        if not os.path.exists(DOWNLOAD_DIR):
            os.makedirs(DOWNLOAD_DIR)

        self.create_widgets()
        self.root.after(100, self.process_queue)

    def create_widgets(self):
        top_frame = ttk.Frame(self.root, padding=5)
        top_frame.pack(fill=tk.X)

        ttk.Label(top_frame, text="COM Порт:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar()
        self.port_cb = ttk.Combobox(top_frame, textvariable=self.port_var, width=15)
        self.port_cb.pack(side=tk.LEFT, padx=5)
        self.refresh_ports()

        ttk.Button(top_frame, text="Обновить", command=self.refresh_ports).pack(side=tk.LEFT, padx=5)

        ttk.Label(top_frame, text="Скорость:").pack(side=tk.LEFT, padx=(15, 0))
        self.baud_var = tk.StringVar(value="115200")
        baud_cb = ttk.Combobox(top_frame, textvariable=self.baud_var, values=["9600", "19200", "38400", "57600", "115200", "230400", "460800"],
                               width=10)
        baud_cb.pack(side=tk.LEFT, padx=5)

        self.btn_connect = ttk.Button(top_frame, text="Подключить", command=self.toggle_connection)
        self.btn_connect.pack(side=tk.LEFT, padx=15)

        mid_frame = ttk.Frame(self.root, padding=5)
        mid_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("name", "size")
        self.tree = ttk.Treeview(mid_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("name", text="Имя файла")
        self.tree.heading("size", text="Размер (Байт)")
        self.tree.column("name", width=450)
        self.tree.column("size", width=150, anchor=tk.E)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(mid_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=tk.LEFT, fill=tk.Y)

        btn_frame = ttk.Frame(mid_frame, padding=5)
        btn_frame.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Button(btn_frame, text="Обновить список", command=self.req_refresh).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Скачать на ПК", command=self.req_download).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Загрузить в МК", command=self.req_upload).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Переименовать", command=self.req_rename).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Удалить", command=self.req_delete).pack(fill=tk.X, pady=2)
        ttk.Button(btn_frame, text="Форматировать", command=self.req_format).pack(fill=tk.X, pady=20)

        bot_frame = ttk.Frame(self.root, padding=5)
        bot_frame.pack(fill=tk.X)

        self.progress = ttk.Progressbar(bot_frame, orient=tk.HORIZONTAL, length=100, mode='determinate')
        self.progress.pack(fill=tk.X, pady=2)

        self.lbl_status = ttk.Label(bot_frame, text="Отключено")
        self.lbl_status.pack(side=tk.LEFT)
        self.lbl_space = ttk.Label(bot_frame, text="")
        self.lbl_space.pack(side=tk.RIGHT)

        self.set_ui_state(tk.DISABLED)

    def ui_set_status(self, text):
        self.lbl_status.config(text=text)

    def ui_set_space(self, text):
        self.lbl_space.config(text=text)

    def ui_clear_tree(self):
        self.tree.delete(*self.tree.get_children())

    def ui_add_tree_item(self, name, size):
        self.tree.insert("", tk.END, values=(name, size))

    def ui_update_progress(self, value, maximum=None):
        if maximum is not None: self.progress['maximum'] = maximum
        self.progress['value'] = value

    def ui_show_msg(self, title, msg):
        CustomMessageDialog(self.root, title, msg)

    def refresh_ports(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_cb['values'] = ports
        if ports: self.port_cb.current(0)

    def set_ui_state(self, state):
        for child in self.root.winfo_children():
            if isinstance(child, ttk.Frame) and child != self.root.winfo_children()[0]:
                for widget in child.winfo_children():
                    if isinstance(widget, ttk.Button):
                        widget.configure(state=state)

    def toggle_connection(self):
        if self.is_connected:
            self.disconnect()
        else:
            port = self.port_var.get()
            baud = self.baud_var.get()
            if not port:
                self.ui_show_msg("Ошибка", "Выберите COM порт")
                return
            threading.Thread(target=self.connect_thread, args=(port, baud), daemon=True).start()

    def disconnect(self):
        self.is_connected = False
        if self.ser and self.ser.is_open:
            self.ser.close()
        self.btn_connect.config(text="Подключить")
        self.set_ui_state(tk.DISABLED)
        self.ui_clear_tree()
        self.ui_set_space("")
        self.ui_set_status("Отключено")

    def connect_thread(self, port, baud):
        self.root.after(0, lambda: self.ui_set_status("Открытие порта..."))
        try:
            self.ser = serial.Serial(port, int(baud), timeout=1)
        except serial.SerialException:
            self.root.after(0, lambda: self.ui_show_msg("Ошибка", "Порт занят или недоступен."))
            self.root.after(0, lambda: self.ui_set_status("Ошибка доступа к порту"))
            return

        time.sleep(1)

        connected = False
        for attempt in range(3):
            self.root.after(0, lambda a=attempt: self.ui_set_status(f"Запрос (попытка {a + 1}/3)..."))
            self.ser.write(b"PING\n")
            resp = self.ser.readline().decode(errors='ignore').strip()
            if "PONG:LFS_FM" in resp:
                connected = True
                break
            time.sleep(0.5)

        if not connected:
            self.ser.close()
            self.root.after(0, lambda: self.ui_show_msg("Ошибка", "Устройство не отвечает."))
            self.root.after(0, lambda: self.ui_set_status("Сбой рукопожатия"))
            return

        self.is_connected = True
        self.root.after(0, lambda: self.btn_connect.config(text="Отключить"))
        self.root.after(0, lambda: self.set_ui_state(tk.NORMAL))
        self.root.after(0, lambda: self.ui_set_status("Подключено!"))

        threading.Thread(target=self.worker_thread, daemon=True).start()
        self.add_task("INFO")
        self.add_task("LIST")

    def add_task(self, cmd, *args):
        self.task_queue.put((cmd, args))

    def process_queue(self):
        self.root.after(100, self.process_queue)

    def worker_thread(self):
        while self.is_connected:
            try:
                task, args = self.task_queue.get(timeout=0.5)
                self.execute_task(task, args)
                self.task_queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                print(f"Ошибка в воркере: {e}")

    def execute_task(self, task, args):
        self.ser.reset_input_buffer()

        if task == "INFO":
            self.ser.write(b"INFO\n")
            resp = self.ser.readline().decode(errors='ignore').strip()
            if resp.startswith("INFO:"):
                _, total, used = resp.split(":")
                msg = f"Память: {used}/{total} Байт"
                self.root.after(0, lambda: self.ui_set_space(msg))

        elif task == "LIST":
            self.root.after(0, self.ui_clear_tree)
            self.ser.write(b"LIST\n")
            while True:
                line = self.ser.readline().decode(errors='ignore').strip()
                if line == "LIST_END": break
                if line.startswith("FILE:"):
                    parts = line.split(":")
                    if len(parts) >= 3:
                        self.root.after(0, lambda n=parts[1], s=parts[2]: self.ui_add_tree_item(n, s))
            self.root.after(0, lambda: self.ui_set_status("Список обновлен"))

        elif task == "DEL":
            filename = args[0]
            self.ser.write(f"DEL:{filename}\n".encode())
            resp = self.ser.readline().decode(errors='ignore').strip()
            if resp == "OK":
                self.root.after(0, lambda: self.ui_set_status(f"Удалено: {filename}"))
            else:
                self.root.after(0, lambda: self.ui_show_msg("Ошибка", f"Не удалось удалить {filename}"))

        elif task == "REN":
            old_name, new_name = args
            self.ser.write(f"REN:{old_name}:{new_name}\n".encode())
            resp = self.ser.readline().decode(errors='ignore').strip()
            if resp == "OK":
                self.root.after(0, lambda: self.ui_set_status("Переименовано"))
            else:
                self.root.after(0, lambda: self.ui_show_msg("Ошибка", "Ошибка переименования"))

        elif task == "FMT":
            self.ser.write(b"FMT\n")
            self.ser.timeout = 20
            resp = self.ser.readline().decode(errors='ignore').strip()
            self.ser.timeout = 1
            if resp == "OK":
                self.root.after(0, lambda: self.ui_show_msg("Успех", "Файловая система очищена."))
                self.add_task("INFO")
                self.add_task("LIST")
            else:
                self.root.after(0, lambda: self.ui_show_msg("Ошибка", "Сбой форматирования"))

        elif task == "UPLOAD":
            filepath = args[0]
            filename = os.path.basename(filepath)
            if not filename.startswith('/'): filename = '/' + filename

            with open(filepath, 'rb') as f:
                data = f.read()

            file_size = len(data)
            file_crc = zlib.crc32(data) & 0xFFFFFFFF

            self.ser.write(f"UPL_START:{filename}:{file_size}:{file_crc:08X}\n".encode())

            if self.ser.readline().decode(errors='ignore').strip() == "READY":
                ptr = 0
                chunk_size = 256
                self.root.after(0, lambda: self.ui_update_progress(0, file_size))

                while ptr < file_size:
                    chunk = data[ptr:ptr + chunk_size]
                    self.ser.write(chunk)
                    self.ser.flush()
                    ptr += len(chunk)

                    ack = self.ser.readline().decode(errors='ignore').strip()
                    if ack != "ACK":
                        self.root.after(0, lambda: self.ui_show_msg("Сбой", "Потеряна связь на этапе загрузки"))
                        break

                    self.root.after(0, lambda p=ptr: self.ui_update_progress(p))
                    self.root.after(0, lambda p=ptr: self.ui_set_status(f"Загрузка {filename}: {p}/{file_size}"))

                final_resp = self.ser.readline().decode(errors='ignore').strip()
                if "SUCCESS" in final_resp:
                    self.root.after(0, lambda: self.ui_set_status(f"Загружен: {filename}"))
                else:
                    self.root.after(0, lambda: self.ui_show_msg("Ошибка CRC", final_resp))

            self.root.after(0, lambda: self.ui_update_progress(0))

        elif task == "DOWNLOAD":
            filename = args[0]
            self.ser.write(f"DWN_START:{filename}\n".encode())

            resp = self.ser.readline().decode(errors='ignore').strip()
            if resp.startswith("DWN_HDR:"):
                file_size = int(resp.split(":")[1])
                local_path = os.path.join(DOWNLOAD_DIR, filename.lstrip('/'))
                os.makedirs(os.path.dirname(local_path), exist_ok=True)

                self.root.after(0, lambda: self.ui_update_progress(0, file_size))

                with open(local_path, 'wb') as f:
                    bytes_received = 0
                    while bytes_received < file_size:
                        self.ser.write(b"DWN_NEXT\n")
                        self.ser.flush()
                        to_read = min(256, file_size - bytes_received)
                        chunk = self.ser.read(to_read)

                        if len(chunk) != to_read:
                            self.root.after(0, lambda: self.ui_show_msg("Ошибка",
                                                                        f"Неполный чанк: {len(chunk)}/{to_read}"))
                            break

                        f.write(chunk)
                        bytes_received += len(chunk)

                        self.root.after(0, lambda p=bytes_received: self.ui_update_progress(p))
                        self.root.after(0, lambda p=bytes_received: self.ui_set_status(f"Скачивание: {p}/{file_size}"))

                final_resp = self.ser.readline().decode(errors='ignore').strip()
                self.root.after(0, lambda: self.ui_set_status(f"Скачан: {filename}"))

            self.root.after(0, lambda: self.ui_update_progress(0))

    def req_refresh(self):
        self.add_task("INFO")
        self.add_task("LIST")

    def req_delete(self):
        selected = self.tree.selection()
        if not selected: return

        dialog = CustomConfirmDialog(self.root, "Удаление", f"Удалить выбранные файлы ({len(selected)} шт.)?")
        if dialog.result:
            for item in selected:
                name = self.tree.item(item, "values")[0]
                self.add_task("DEL", name)
            self.req_refresh()

    def req_rename(self):
        selected = self.tree.selection()
        if len(selected) != 1:
            CustomMessageDialog(self.root, "Внимание", "Выберите ровно один файл для переименования.")
            return

        old_name = self.tree.item(selected[0], "values")[0]

        dialog = CustomInputDialog(self.root, "Переименовать", "Введите новое имя файла:", initialvalue=old_name)
        new_name = dialog.result

        if new_name and new_name != old_name:
            if not new_name.startswith('/'): new_name = '/' + new_name
            self.add_task("REN", old_name, new_name)
            self.req_refresh()

    def req_format(self):
        dialog = CustomConfirmDialog(self.root, "Форматировать?",
                                     "Вы уверены, что хотите отформатировать память?\nВсе данные будут безвозвратно удалены!")
        if dialog.result:
            self.add_task("FMT")

    def req_upload(self):
        files = filedialog.askopenfilenames(title="Выберите файлы для загрузки")
        for f in files: self.add_task("UPLOAD", f)
        if files: self.req_refresh()

    def req_download(self):
        selected = self.tree.selection()
        for item in selected:
            self.add_task("DOWNLOAD", self.tree.item(item, "values")[0])


if __name__ == "__main__":
    root = tk.Tk()
    app = LFSFileManagerApp(root)
    root.mainloop()