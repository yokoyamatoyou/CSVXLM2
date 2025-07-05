import tkinter as tk
from tkinter import filedialog, messagebox

# Import the existing CLI entry point
from main import main as cli_main


class Application(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CSVXLM Converter")
        self._create_widgets()

    def _create_widgets(self):
        # Config file selection
        tk.Label(self, text="Config File:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.config_entry = tk.Entry(self, width=50)
        self.config_entry.insert(0, "config_rules/config.json")
        self.config_entry.grid(row=0, column=1, padx=5, pady=5)
        tk.Button(self, text="Browse", command=self._browse_config).grid(row=0, column=2, padx=5, pady=5)

        # CSV profile
        tk.Label(self, text="CSV Profile:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.profile_entry = tk.Entry(self, width=50)
        self.profile_entry.insert(0, "grouped_checkup_profile")
        self.profile_entry.grid(row=1, column=1, padx=5, pady=5)

        tk.Button(self, text="Run Conversion", command=self._run_conversion).grid(
            row=2, column=0, columnspan=3, pady=10
        )

    def _browse_config(self):
        file_path = filedialog.askopenfilename(title="Select config file", filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if file_path:
            self.config_entry.delete(0, tk.END)
            self.config_entry.insert(0, file_path)

    def _run_conversion(self):
        config = self.config_entry.get().strip()
        profile = self.profile_entry.get().strip()
        try:
            cli_main(["--config", config, "--profile", profile])
            messagebox.showinfo("Success", "Conversion completed successfully.")
        except Exception as exc:
            messagebox.showerror("Error", f"An error occurred:\n{exc}")


if __name__ == "__main__":
    Application().mainloop()
