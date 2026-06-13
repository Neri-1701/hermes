import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import pandas as pd


APP_TITLE = "Hermes - Sprint 1"
WINDOW_SIZE = "1200x720"
PREVIEW_LIMIT = 100


class HermesApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(1000, 620)

        self.inventory_df = None
        self.requirements_df = None

        self.inventory_path = tk.StringVar(value="No file loaded")
        self.requirements_path = tk.StringVar(value="No file loaded")
        self.status_text = tk.StringVar(value="Ready")

        self.inventory_description_col = tk.StringVar()
        self.inventory_code_col = tk.StringVar()
        self.inventory_quantity_col = tk.StringVar()

        self.requirements_udc_col = tk.StringVar()
        self.requirements_date_col = tk.StringVar()
        self.requirements_description_col = tk.StringVar()
        self.requirements_quantity_col = tk.StringVar()

        self._configure_style()
        self._build_ui()

    def _configure_style(self):
        self.configure(bg="#20272e")

        style = ttk.Style()
        style.theme_use("default")
        style.configure("TFrame", background="#20272e")
        style.configure("TLabelframe", background="#20272e", foreground="#f2f2f2")
        style.configure("TLabelframe.Label", background="#20272e", foreground="#f2f2f2")
        style.configure("TLabel", background="#20272e", foreground="#f2f2f2")
        style.configure("TButton", padding=6)
        style.configure("TCombobox", fieldbackground="#ffffff", background="#ffffff")
        style.configure("Treeview", rowheight=24)
        style.configure("Treeview.Heading", font=("Arial", 10, "bold"))

    def _build_ui(self):
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        title = ttk.Label(
            root,
            text="Hermes - Base funcional Sprint 1",
            font=("Arial", 18, "bold"),
        )
        title.pack(anchor="w", pady=(0, 8))

        subtitle = ttk.Label(
            root,
            text="Carga de archivos, seleccion de columnas y validacion inicial del flujo de datos.",
            font=("Arial", 10),
        )
        subtitle.pack(anchor="w", pady=(0, 14))

        top = ttk.Frame(root)
        top.pack(fill="x")

        self._build_inventory_panel(top)
        self._build_requirements_panel(top)

        actions = ttk.Frame(root)
        actions.pack(fill="x", pady=12)

        ttk.Button(actions, text="Validate Sprint 1 setup", command=self.validate_setup).pack(side="left")
        ttk.Button(actions, text="Clear preview", command=self.clear_preview).pack(side="left", padx=8)

        self.summary_label = ttk.Label(actions, textvariable=self.status_text)
        self.summary_label.pack(side="right")

        preview_frame = ttk.LabelFrame(root, text="Data preview")
        preview_frame.pack(fill="both", expand=True)

        self.preview_tree = ttk.Treeview(preview_frame, show="headings")
        self.preview_tree.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview_tree.yview)
        y_scroll.pack(side="right", fill="y")
        self.preview_tree.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(root, orient="horizontal", command=self.preview_tree.xview)
        x_scroll.pack(fill="x")
        self.preview_tree.configure(xscrollcommand=x_scroll.set)

    def _build_inventory_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Inventory file")
        frame.pack(side="left", fill="both", expand=True, padx=(0, 6))

        ttk.Button(frame, text="Load inventory .xlsx", command=self.load_inventory).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(frame, textvariable=self.inventory_path, wraplength=500).pack(anchor="w", padx=10, pady=(0, 8))

        self.inventory_description_combo = self._add_combo(
            frame,
            "Inventory description column",
            self.inventory_description_col,
        )
        self.inventory_code_combo = self._add_combo(
            frame,
            "Material code column",
            self.inventory_code_col,
        )
        self.inventory_quantity_combo = self._add_combo(
            frame,
            "Available quantity column",
            self.inventory_quantity_col,
        )

    def _build_requirements_panel(self, parent):
        frame = ttk.LabelFrame(parent, text="Requirements file")
        frame.pack(side="left", fill="both", expand=True, padx=(6, 0))

        ttk.Button(frame, text="Load requirements .xlsx", command=self.load_requirements).pack(anchor="w", padx=10, pady=(10, 4))
        ttk.Label(frame, textvariable=self.requirements_path, wraplength=500).pack(anchor="w", padx=10, pady=(0, 8))

        self.requirements_udc_combo = self._add_combo(
            frame,
            "UDC column",
            self.requirements_udc_col,
        )
        self.requirements_date_combo = self._add_combo(
            frame,
            "Program date column",
            self.requirements_date_col,
        )
        self.requirements_description_combo = self._add_combo(
            frame,
            "Requested material description column",
            self.requirements_description_col,
        )
        self.requirements_quantity_combo = self._add_combo(
            frame,
            "Required quantity column",
            self.requirements_quantity_col,
        )

    def _add_combo(self, parent, label_text, variable):
        ttk.Label(parent, text=label_text).pack(anchor="w", padx=10, pady=(4, 2))
        combo = ttk.Combobox(parent, textvariable=variable, state="readonly")
        combo.pack(fill="x", padx=10, pady=(0, 4))
        return combo

    def load_inventory(self):
        path = self._ask_excel_file()
        if not path:
            return

        try:
            df = self._read_excel(path)
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))
            return

        self.inventory_df = df
        self.inventory_path.set(path)
        self._set_inventory_columns(list(df.columns))
        self._render_preview(df, "Inventory preview")
        self.status_text.set("Inventory file loaded")

    def load_requirements(self):
        path = self._ask_excel_file()
        if not path:
            return

        try:
            df = self._read_excel(path)
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))
            return

        self.requirements_df = df
        self.requirements_path.set(path)
        self._set_requirements_columns(list(df.columns))
        self._render_preview(df, "Requirements preview")
        self.status_text.set("Requirements file loaded")

    def _ask_excel_file(self):
        return filedialog.askopenfilename(
            title="Select Excel file",
            filetypes=[("Excel files", "*.xlsx")],
        )

    def _read_excel(self, path):
        df = pd.read_excel(path)
        if df.empty:
            raise ValueError("The selected file has no rows.")
        return df

    def _set_inventory_columns(self, columns):
        self.inventory_description_combo["values"] = columns
        self.inventory_code_combo["values"] = columns
        self.inventory_quantity_combo["values"] = columns
        self._clear_inventory_selection()

    def _set_requirements_columns(self, columns):
        self.requirements_udc_combo["values"] = columns
        self.requirements_date_combo["values"] = columns
        self.requirements_description_combo["values"] = columns
        self.requirements_quantity_combo["values"] = columns
        self._clear_requirements_selection()

    def _clear_inventory_selection(self):
        self.inventory_description_col.set("")
        self.inventory_code_col.set("")
        self.inventory_quantity_col.set("")

    def _clear_requirements_selection(self):
        self.requirements_udc_col.set("")
        self.requirements_date_col.set("")
        self.requirements_description_col.set("")
        self.requirements_quantity_col.set("")

    def validate_setup(self):
        errors = []

        if self.inventory_df is None:
            errors.append("Load an inventory file.")
        if self.requirements_df is None:
            errors.append("Load a requirements file.")

        required_fields = {
            "Inventory description": self.inventory_description_col.get(),
            "Inventory material code": self.inventory_code_col.get(),
            "Inventory available quantity": self.inventory_quantity_col.get(),
            "Requirements UDC": self.requirements_udc_col.get(),
            "Requirements program date": self.requirements_date_col.get(),
            "Requirements description": self.requirements_description_col.get(),
            "Requirements required quantity": self.requirements_quantity_col.get(),
        }

        for field_name, selected_column in required_fields.items():
            if not selected_column:
                errors.append(f"Select: {field_name}.")

        if errors:
            messagebox.showwarning("Sprint 1 setup incomplete", "\n".join(errors))
            self.status_text.set("Setup incomplete")
            return

        message = self._build_setup_summary(required_fields)
        messagebox.showinfo("Sprint 1 setup validated", message)
        self.status_text.set("Sprint 1 setup validated")

    def _build_setup_summary(self, required_fields):
        lines = [
            "Hermes Sprint 1 setup is valid.",
            "",
            "Selected mapping:",
        ]

        for field_name, selected_column in required_fields.items():
            lines.append(f"- {field_name}: {selected_column}")

        lines.extend(
            [
                "",
                "Next increment:",
                "Sprint 2 will add material interpretation and inventory matching.",
            ]
        )
        return "\n".join(lines)

    def _render_preview(self, df, title):
        self.preview_tree.delete(*self.preview_tree.get_children())
        columns = [str(col) for col in df.columns]
        self.preview_tree["columns"] = columns

        for column in columns:
            self.preview_tree.heading(column, text=column)
            self.preview_tree.column(column, width=160, anchor="w")

        preview_df = df.head(PREVIEW_LIMIT)
        for _, row in preview_df.iterrows():
            values = [self._format_cell(row[col]) for col in df.columns]
            self.preview_tree.insert("", "end", values=values)

        self.status_text.set(f"{title}: showing {len(preview_df)} of {len(df)} rows")

    def _format_cell(self, value):
        if pd.isna(value):
            return ""
        return str(value)

    def clear_preview(self):
        self.preview_tree.delete(*self.preview_tree.get_children())
        self.preview_tree["columns"] = []
        self.status_text.set("Preview cleared")
