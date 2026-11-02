"""
ArcCW to ARC9 Converter - Graphical User Interface (GUI)
A clean, practical, and intuitive tool for single and bulk conversions.
"""
import os
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from .addon_converter import AddonConverter
from .weapon_converter import WeaponConverter
from .attachment_converter import AttachmentConverter
from .bulk_converter import BulkConverter, detect_arccw_addons

class ConverterGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ArcCW to ARC9 Converter")
        self.geometry("740x700")
        self.minsize(660, 560)

        # Configure style
        self.style = ttk.Style(self)
        try:
            self.style.theme_use("clam")
        except Exception:
            pass

        self._init_variables()
        self._build_ui()
        self._last_output_dir: Optional[Path] = None

    def _init_variables(self):
        # Single Addon Tab
        self.single_input_var = tk.StringVar()
        self.single_output_var = tk.StringVar()
        self.single_bulk_att_var = tk.BooleanVar(value=True)
        self.single_copy_assets_var = tk.BooleanVar(value=True)

        # Bulk Tab
        self.bulk_items: List[Path] = []
        self.bulk_output_parent_var = tk.StringVar()
        self.bulk_att_var = tk.BooleanVar(value=True)
        self.bulk_copy_assets_var = tk.BooleanVar(value=True)

        # Single File Tab
        self.file_input_var = tk.StringVar()
        self.file_output_var = tk.StringVar()

        # Status
        self.status_var = tk.StringVar(value="Ready")
        self.is_converting = False

    def _build_ui(self):
        # Top banner / header
        header_frame = ttk.Frame(self, padding=(14, 10, 14, 6))
        header_frame.pack(fill="x")

        title_lbl = ttk.Label(
            header_frame,
            text="ArcCW to ARC9 Converter",
            font=("Segoe UI", 15, "bold")
        )
        title_lbl.pack(anchor="w")

        subtitle_lbl = ttk.Label(
            header_frame,
            text="Convert Garry's Mod ArcCW weapons, attachments, and full packs to ARC9.",
            font=("Segoe UI", 9)
        )
        subtitle_lbl.pack(anchor="w")

        # Main notebook (Tabs)
        self.notebook = ttk.Notebook(self, padding=8)
        self.notebook.pack(fill="x", padx=10, pady=4)

        # Tab 1: Single Addon
        self.tab_single = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_single, text="  Single Addon Folder  ")
        self._build_single_addon_tab()

        # Tab 2: Bulk Convert
        self.tab_bulk = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_bulk, text="  Bulk Convert (Multiple)  ")
        self._build_bulk_tab()

        # Tab 3: Single File
        self.tab_file = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(self.tab_file, text="  Single .Lua File  ")
        self._build_single_file_tab()

        # Action Area (Convert Button, Progress, Open Output)
        action_frame = ttk.Frame(self, padding=(14, 8, 14, 4))
        action_frame.pack(fill="x")

        self.btn_convert = tk.Button(
            action_frame,
            text="Convert to ARC9",
            font=("Segoe UI", 11, "bold"),
            bg="#2e7d32",
            fg="white",
            activebackground="#1b5e20",
            activeforeground="white",
            relief="raised",
            cursor="hand2",
            padx=16,
            pady=6,
            command=self._start_conversion
        )
        self.btn_convert.pack(side="left", padx=(0, 10))

        self.btn_open_folder = ttk.Button(
            action_frame,
            text="Open Output Folder",
            command=self._open_output_folder,
            state="disabled"
        )
        self.btn_open_folder.pack(side="left")

        # Progress bar
        self.progress_bar = ttk.Progressbar(self, mode="determinate")
        self.progress_bar.pack(fill="x", padx=14, pady=(6, 4))

        # Log Console
        log_frame = ttk.LabelFrame(self, text=" Conversion Log ", padding=6)
        log_frame.pack(fill="both", expand=True, padx=14, pady=4)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap="word",
            font=("Consolas", 9),
            bg="#1c1d22",
            fg="#e0e0e0",
            insertbackground="white",
            padx=8,
            pady=8
        )
        self.log_text.pack(fill="both", expand=True)

        # Log color tags
        self.log_text.tag_config("cyan", foreground="#4dd0e1")
        self.log_text.tag_config("green", foreground="#81c784")
        self.log_text.tag_config("yellow", foreground="#fff176")
        self.log_text.tag_config("red", foreground="#e57373")
        self.log_text.tag_config("magenta", foreground="#f06292")

        self._log("ArcCW to ARC9 Converter GUI initialized.\n", "cyan")

        # Bottom status bar
        status_bar = ttk.Frame(self, relief="sunken", padding=(8, 3))
        status_bar.pack(fill="x", side="bottom")

        status_lbl = ttk.Label(status_bar, textvariable=self.status_var, font=("Segoe UI", 9))
        status_lbl.pack(side="left")

        ver_lbl = ttk.Label(status_bar, text="v1.0.0", font=("Segoe UI", 9), foreground="#888888")
        ver_lbl.pack(side="right")

    # -------------------------------------------------------------
    # TAB 1: Single Addon
    # -------------------------------------------------------------
    def _build_single_addon_tab(self):
        # Input
        f_in = ttk.Frame(self.tab_single)
        f_in.pack(fill="x", pady=4)
        ttk.Label(f_in, text="ArcCW Addon Folder:", width=22, anchor="w").pack(side="left")
        ttk.Entry(f_in, textvariable=self.single_input_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(f_in, text="Browse...", command=self._browse_single_input).pack(side="left")

        # Output
        f_out = ttk.Frame(self.tab_single)
        f_out.pack(fill="x", pady=4)
        ttk.Label(f_out, text="Output Folder (Optional):", width=22, anchor="w").pack(side="left")
        ttk.Entry(f_out, textvariable=self.single_output_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(f_out, text="Browse...", command=self._browse_single_output).pack(side="left")

        ttk.Label(
            self.tab_single,
            text="Leave output empty to automatically create 'arc9_<name>' next to the addon.",
            font=("Segoe UI", 8),
            foreground="#666666"
        ).pack(anchor="w", padx=24, pady=(0, 6))

        # Checkboxes
        f_opts = ttk.Frame(self.tab_single)
        f_opts.pack(fill="x", pady=4)
        ttk.Checkbutton(f_opts, text="Bundle Attachments (Recommended for ARC9)", variable=self.single_bulk_att_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(f_opts, text="Copy Assets (models, materials, sounds, particles)", variable=self.single_copy_assets_var).pack(side="left")

    def _browse_single_input(self):
        d = filedialog.askdirectory(title="Select ArcCW Addon Folder")
        if d:
            self.single_input_var.set(os.path.normpath(d))
            # Auto-suggest output if not already filled
            if not self.single_output_var.get():
                p = Path(d)
                out_name = f"arc9_{p.name}" if not p.name.startswith("arccw_") else p.name.replace("arccw_", "arc9_")
                self.single_output_var.set(str(p.parent / out_name))

    def _browse_single_output(self):
        d = filedialog.askdirectory(title="Select Destination Folder")
        if d:
            self.single_output_var.set(os.path.normpath(d))

    # -------------------------------------------------------------
    # TAB 2: Bulk Convert
    # -------------------------------------------------------------
    def _build_bulk_tab(self):
        # Toolbar
        tb = ttk.Frame(self.tab_bulk)
        tb.pack(fill="x", pady=(0, 6))

        ttk.Button(tb, text="Add Addon Folder", command=self._bulk_add_folder).pack(side="left", padx=(0, 4))
        ttk.Button(tb, text="Scan Directory for Addons...", command=self._bulk_scan_dir).pack(side="left", padx=4)
        ttk.Button(tb, text="Remove Selected", command=self._bulk_remove_selected).pack(side="left", padx=4)
        ttk.Button(tb, text="Clear List", command=self._bulk_clear).pack(side="left", padx=4)

        # Queue List (Treeview)
        tree_frame = ttk.Frame(self.tab_bulk)
        tree_frame.pack(fill="both", expand=True, pady=4)

        columns = ("name", "path", "status")
        self.bulk_tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=6)
        self.bulk_tree.heading("name", text="Addon Name")
        self.bulk_tree.heading("path", text="Folder Path")
        self.bulk_tree.heading("status", text="Status")

        self.bulk_tree.column("name", width=160, anchor="w")
        self.bulk_tree.column("path", width=360, anchor="w")
        self.bulk_tree.column("status", width=100, anchor="center")

        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.bulk_tree.yview)
        self.bulk_tree.configure(yscrollcommand=tree_scroll.set)

        self.bulk_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")

        # Output parent directory
        f_out = ttk.Frame(self.tab_bulk)
        f_out.pack(fill="x", pady=(6, 2))
        ttk.Label(f_out, text="Output Directory (Optional):", width=22, anchor="w").pack(side="left")
        ttk.Entry(f_out, textvariable=self.bulk_output_parent_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(f_out, text="Browse...", command=self._browse_bulk_output).pack(side="left")

        ttk.Label(
            self.tab_bulk,
            text="Converted addons will be saved inside this directory as 'arc9_<name>'. Leave blank to place next to sources.",
            font=("Segoe UI", 8),
            foreground="#666666"
        ).pack(anchor="w", padx=24, pady=(0, 4))

        # Checkboxes
        f_opts = ttk.Frame(self.tab_bulk)
        f_opts.pack(fill="x", pady=2)
        ttk.Checkbutton(f_opts, text="Bundle Attachments", variable=self.bulk_att_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(f_opts, text="Copy Assets", variable=self.bulk_copy_assets_var).pack(side="left")

    def _bulk_add_folder(self):
        d = filedialog.askdirectory(title="Select Addon Folder to Add")
        if d:
            path = Path(d).resolve()
            if path not in self.bulk_items:
                self.bulk_items.append(path)
                self.bulk_tree.insert("", "end", iid=str(path), values=(path.name, str(path), "Pending"))
                self._log(f"[*] Added to bulk queue: {path.name}", "cyan")

    def _bulk_scan_dir(self):
        d = filedialog.askdirectory(title="Select Parent Folder to Scan (e.g. garrysmod/addons)")
        if not d:
            return

        parent = Path(d).resolve()
        self._log(f"[*] Scanning '{parent}' for ArcCW addons...", "cyan")
        detected = detect_arccw_addons(parent)

        if not detected:
            messagebox.showinfo("Scan Complete", f"No ArcCW addons were detected inside:\n{parent}")
            self._log(f"[!] No ArcCW addons found in {parent}", "yellow")
            return

        added_count = 0
        for item in detected:
            if item not in self.bulk_items:
                self.bulk_items.append(item)
                self.bulk_tree.insert("", "end", iid=str(item), values=(item.name, str(item), "Pending"))
                added_count += 1

        self._log(f"[+] Scan detected {len(detected)} addon(s) ({added_count} newly added to queue)!", "green")
        messagebox.showinfo("Scan Complete", f"Found {len(detected)} ArcCW addon(s)!\nAdded {added_count} to queue.")

    def _bulk_remove_selected(self):
        selected = self.bulk_tree.selection()
        for item_id in selected:
            path = Path(item_id)
            if path in self.bulk_items:
                self.bulk_items.remove(path)
            self.bulk_tree.delete(item_id)

    def _bulk_clear(self):
        self.bulk_items.clear()
        for item in self.bulk_tree.get_children():
            self.bulk_tree.delete(item)
        self._log("[*] Cleared bulk queue.", "yellow")

    def _browse_bulk_output(self):
        d = filedialog.askdirectory(title="Select Destination Folder for All Converted Addons")
        if d:
            self.bulk_output_parent_var.set(os.path.normpath(d))

    # -------------------------------------------------------------
    # TAB 3: Single File
    # -------------------------------------------------------------
    def _build_single_file_tab(self):
        # Input
        f_in = ttk.Frame(self.tab_file)
        f_in.pack(fill="x", pady=6)
        ttk.Label(f_in, text="ArcCW .Lua File:", width=22, anchor="w").pack(side="left")
        ttk.Entry(f_in, textvariable=self.file_input_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(f_in, text="Browse...", command=self._browse_single_file_input).pack(side="left")

        # Output
        f_out = ttk.Frame(self.tab_file)
        f_out.pack(fill="x", pady=6)
        ttk.Label(f_out, text="Output .Lua File (Optional):", width=22, anchor="w").pack(side="left")
        ttk.Entry(f_out, textvariable=self.file_output_var).pack(side="left", fill="x", expand=True, padx=6)
        ttk.Button(f_out, text="Browse...", command=self._browse_single_file_output).pack(side="left")

        ttk.Label(
            self.tab_file,
            text="Converts a single standalone SWEP weapon script or attachment file to ARC9 format.",
            font=("Segoe UI", 8),
            foreground="#666666"
        ).pack(anchor="w", padx=24, pady=4)

    def _browse_single_file_input(self):
        f = filedialog.askopenfilename(
            title="Select ArcCW Lua File",
            filetypes=[("Lua files", "*.lua"), ("All files", "*.*")]
        )
        if f:
            self.file_input_var.set(os.path.normpath(f))
            if not self.file_output_var.get():
                p = Path(f)
                out_name = p.name.replace("arccw_", "arc9_")
                if out_name == p.name:
                    out_name = f"arc9_{p.name}"
                self.file_output_var.set(str(p.parent / out_name))

    def _browse_single_file_output(self):
        f = filedialog.asksaveasfilename(
            title="Select Output Lua File",
            filetypes=[("Lua files", "*.lua"), ("All files", "*.*")]
        )
        if f:
            self.file_output_var.set(os.path.normpath(f))

    # -------------------------------------------------------------
    # Conversion Logic & Worker Thread
    # -------------------------------------------------------------
    def _log(self, text: str, tag: Optional[str] = None):
        self.log_text.insert("end", text + "\n", tag)
        self.log_text.see("end")

    def _open_output_folder(self):
        if self._last_output_dir and self._last_output_dir.exists():
            try:
                os.startfile(str(self._last_output_dir))
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open folder: {e}")
        else:
            messagebox.showwarning("Notice", "Output folder not available yet.")

    def _start_conversion(self):
        if self.is_converting:
            return

        current_tab_idx = self.notebook.index(self.notebook.select())

        # Validate inputs based on active tab
        if current_tab_idx == 0:  # Single Addon
            inp = self.single_input_var.get().strip()
            if not inp or not Path(inp).exists():
                messagebox.showwarning("Missing Input", "Please select a valid ArcCW addon directory first!")
                return
        elif current_tab_idx == 1:  # Bulk
            if not self.bulk_items:
                messagebox.showwarning("Empty Queue", "Please add at least one folder to the bulk queue, or use 'Scan Directory'!")
                return
        elif current_tab_idx == 2:  # Single File
            inp = self.file_input_var.get().strip()
            if not inp or not Path(inp).exists():
                messagebox.showwarning("Missing Input", "Please select a valid .lua file first!")
                return

        # Start worker thread
        self.is_converting = True
        self.btn_convert.config(state="disabled", text="Converting...", bg="#757575")
        self.btn_open_folder.config(state="disabled")
        self.progress_bar.config(value=0)
        self.status_var.set("Conversion in progress...")

        thread = threading.Thread(target=self._run_conversion, args=(current_tab_idx,), daemon=True)
        thread.start()

    def _run_conversion(self, tab_idx: int):
        start_time = time.time()
        success = False
        out_target: Optional[Path] = None

        try:
            if tab_idx == 0:  # Single Addon
                inp_path = Path(self.single_input_var.get().strip())
                out_str = self.single_output_var.get().strip()
                out_path = Path(out_str) if out_str else None

                self.after(0, lambda: self._log(f"\n[*] Converting single addon: {inp_path.name}...", "cyan"))
                self.after(0, lambda: self.progress_bar.config(value=20))

                converter = AddonConverter(
                    input_dir=inp_path,
                    output_dir=out_path,
                    bulk_attachments=self.single_bulk_att_var.get(),
                    copy_assets=self.single_copy_assets_var.get()
                )
                rep = converter.convert()
                out_target = converter.output_dir

                self.after(0, lambda: self.progress_bar.config(value=100))
                self.after(0, lambda: self._log(f"[+] Converted {len(rep['weapons'])} weapon(s), {len(rep['attachments'])} attachment(s).", "green"))
                self.after(0, lambda: self._log(f"[+] Output ready at: {out_target}", "cyan"))
                success = True

            elif tab_idx == 1:  # Bulk Convert
                parent_out_str = self.bulk_output_parent_var.get().strip()
                parent_out = Path(parent_out_str) if parent_out_str else None

                def log_cb(msg: str):
                    tag = "green" if "[+]" in msg or "[SUCCESS]" in msg else ("red" if "[ERROR]" in msg else "cyan")
                    self.after(0, lambda m=msg, t=tag: self._log(m, t))

                def progress_cb(cur: int, tot: int, name: str):
                    pct = int((cur / tot) * 100)
                    self.after(0, lambda p=pct, c=cur, t=tot, n=name: self._update_bulk_progress(p, c, t, n))

                bulk_conv = BulkConverter(
                    items=self.bulk_items,
                    output_parent_dir=parent_out,
                    bulk_attachments=self.bulk_att_var.get(),
                    copy_assets=self.bulk_copy_assets_var.get(),
                    log_callback=log_cb,
                    progress_callback=progress_cb
                )

                rep = bulk_conv.convert()
                out_target = parent_out or (self.bulk_items[0].parent if self.bulk_items else None)
                success = rep["successful_items"] > 0

                # Update tree statuses
                for it_rep in rep["item_reports"]:
                    item_name = it_rep["name"]
                    status_text = "Done!" if it_rep["status"] == "success" else "Failed"
                    for item_id in self.bulk_tree.get_children():
                        if Path(item_id).name == item_name:
                            self.after(0, lambda i=item_id, s=status_text: self.bulk_tree.set(i, "status", s))

            elif tab_idx == 2:  # Single File
                inp_file = Path(self.file_input_var.get().strip())
                out_file_str = self.file_output_var.get().strip()
                out_file = Path(out_file_str) if out_file_str else inp_file.parent / f"arc9_{inp_file.name}"

                self.after(0, lambda: self._log(f"\n[*] Converting single file: {inp_file.name}...", "cyan"))
                self.after(0, lambda: self.progress_bar.config(value=30))

                content = inp_file.read_text(encoding="utf-8", errors="replace")
                is_att = "att.PrintName" in content or "att.Slot" in content or "attachments" in str(inp_file).lower()

                if is_att:
                    ac = AttachmentConverter(content, att_id=inp_file.stem)
                    res = ac.convert(is_bulk=False)
                else:
                    wc = WeaponConverter(content, filename=inp_file.name)
                    res = wc.convert()

                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(res, encoding="utf-8")
                out_target = out_file.parent

                self.after(0, lambda: self.progress_bar.config(value=100))
                self.after(0, lambda: self._log(f"[+] Converted file saved to: {out_file}", "green"))
                success = True

        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._log(f"[ERROR] Conversion failed: {err_msg}", "red"))
            self.after(0, lambda: messagebox.showerror("Conversion Error", f"An error occurred during conversion:\n\n{err_msg}"))

        elapsed = round(time.time() - start_time, 2)
        self._last_output_dir = out_target

        self.after(0, lambda: self._finish_conversion(success, elapsed, out_target))

    def _update_bulk_progress(self, pct: int, cur: int, total: int, name: str):
        self.progress_bar.config(value=pct)
        self.status_var.set(f"Converting [{cur}/{total}]: {name}")
        for item_id in self.bulk_tree.get_children():
            if Path(item_id).name == name:
                self.bulk_tree.set(item_id, "status", "Converting...")

    def _finish_conversion(self, success: bool, elapsed: float, out_target: Optional[Path]):
        self.is_converting = False
        self.btn_convert.config(state="normal", text="Convert to ARC9", bg="#2e7d32")

        if success:
            self.status_var.set(f"Completed in {elapsed}s.")
            self._log(f"\n[SUCCESS] All tasks finished in {elapsed} seconds.\n", "green")
            if out_target and out_target.exists():
                self.btn_open_folder.config(state="normal")
                ans = messagebox.askyesno(
                    "Conversion Complete",
                    f"Conversion completed successfully in {elapsed}s.\n\nDestination:\n{out_target}\n\nWould you like to open the output folder now?"
                )
                if ans:
                    self._open_output_folder()
        else:
            self.status_var.set(f"Finished with errors in {elapsed}s.")

def launch_gui():
    """Entry point to launch the ArcCW to ARC9 Converter GUI."""
    app = ConverterGUI()
    app.mainloop()

if __name__ == "__main__":
    launch_gui()
