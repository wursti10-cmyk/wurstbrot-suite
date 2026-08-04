from __future__ import annotations

import sys
import threading
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "core"))

from wurstbrot_core import (  # noqa: E402
    PlayerProgress,
    ResearchSolver,
    SolveOptions,
    VehicleDatabase,
    VehicleProgress,
)
from wurstbrot_core.explain import explain_result  # noqa: E402


def main() -> int:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as exc:
        print(f"Tkinter konnte nicht gestartet werden: {exc}", file=sys.stderr)
        return 1

    class App:
        def __init__(self, root: tk.Tk) -> None:
            self.root = root
            self.root.title("Wurstbrot GE Calculator 2.0 – Milestone 1")
            self.root.geometry("1040x760")
            self.root.minsize(840, 620)
            self.db: VehicleDatabase | None = None
            self.solver: ResearchSolver | None = None
            self.vehicle_ids: list[str] = []
            self.display_to_id: dict[str, str] = {}

            self.database_var = tk.StringVar(
                value=str(ROOT / "data" / "samples" / "WT_Database_2.57.1.67.json")
            )
            self.nation_var = tk.StringVar()
            self.branch_var = tk.StringVar()
            self.start_var = tk.StringVar(value="Baumstart / kein Fahrzeug")
            self.target_var = tk.StringVar()
            self.start_partial_var = tk.BooleanVar(value=False)
            self.start_rp_var = tk.StringVar(value="0")
            self.target_rp_var = tk.StringVar(value="0")
            self.convertible_var = tk.StringVar(value="")
            self.owned_ge_var = tk.StringVar(value="0")
            self.discount_var = tk.StringVar(value="0")
            self.optimize_var = tk.StringVar(value="ge")
            self.status_var = tk.StringVar(value="Datenbank laden.")

            self.build_ui(ttk)
            self.load_database()

        def build_ui(self, ttk) -> None:
            outer = ttk.Frame(self.root, padding=16)
            outer.pack(fill="both", expand=True)

            ttk.Label(
                outer,
                text="🥪 Wurstbrot GE Calculator 2.0",
                font=("Segoe UI", 20, "bold"),
            ).pack(anchor="w")
            ttk.Label(
                outer,
                text="Milestone 1 · A→B-Solver · Rangfreischaltungen · Explain Mode",
            ).pack(anchor="w", pady=(0, 12))

            dbrow = ttk.Frame(outer)
            dbrow.pack(fill="x", pady=(0, 10))
            ttk.Entry(dbrow, textvariable=self.database_var).pack(side="left", fill="x", expand=True)
            ttk.Button(dbrow, text="Datenbank wählen", command=self.choose_database).pack(side="left", padx=6)
            ttk.Button(dbrow, text="Laden", command=self.load_database).pack(side="left")

            controls = ttk.LabelFrame(outer, text="Berechnung", padding=12)
            controls.pack(fill="x")
            for col in range(4): controls.columnconfigure(col, weight=1)

            self.add_control(controls, ttk, "Nation", self.nation_var, 0, 0, "combo")
            self.add_control(controls, ttk, "Fahrzeugart", self.branch_var, 0, 1, "combo")
            self.add_control(controls, ttk, "Von Fahrzeug A", self.start_var, 0, 2, "combo")
            self.add_control(controls, ttk, "Zu Fahrzeug B", self.target_var, 0, 3, "combo")

            self.nation_combo = controls.grid_slaves(row=1, column=0)[0]
            self.branch_combo = controls.grid_slaves(row=1, column=1)[0]
            self.start_combo = controls.grid_slaves(row=1, column=2)[0]
            self.target_combo = controls.grid_slaves(row=1, column=3)[0]
            self.nation_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_branches())
            self.branch_combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_vehicles())

            ttk.Checkbutton(
                controls,
                text="A ist nur angeforscht und soll mitgerechnet werden",
                variable=self.start_partial_var,
            ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(12, 2))
            self.add_control(controls, ttk, "RP auf A", self.start_rp_var, 3, 0, "entry")
            self.add_control(controls, ttk, "RP auf Ziel B", self.target_rp_var, 3, 1, "entry")
            self.add_control(controls, ttk, "Convertible RP (leer = unbegrenzt)", self.convertible_var, 3, 2, "entry")
            self.add_control(controls, ttk, "Vorhandene GE", self.owned_ge_var, 3, 3, "entry")

            self.add_control(controls, ttk, "Optimieren nach", self.optimize_var, 5, 0, "combo", ("ge", "rp", "sl", "vehicles"))
            self.add_control(controls, ttk, "SL-Rabatt (%)", self.discount_var, 5, 1, "combo", ("0", "30", "50"))
            ttk.Button(controls, text="Berechnen", command=self.calculate).grid(row=6, column=2, columnspan=2, sticky="ew", padx=5, pady=(18, 4))

            result_frame = ttk.LabelFrame(outer, text="Explain Mode", padding=8)
            result_frame.pack(fill="both", expand=True, pady=(12, 0))
            self.result = tk.Text(result_frame, wrap="word", font=("Consolas", 10), state="disabled")
            scroll = ttk.Scrollbar(result_frame, command=self.result.yview)
            self.result.configure(yscrollcommand=scroll.set)
            self.result.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")
            ttk.Label(outer, textvariable=self.status_var).pack(anchor="w", pady=(6, 0))

        def add_control(self, parent, ttk, label, variable, row, column, kind, values=()):
            ttk.Label(parent, text=label).grid(row=row, column=column, sticky="w", padx=5, pady=(3, 1))
            if kind == "combo":
                widget = ttk.Combobox(parent, textvariable=variable, values=values, state="readonly")
            else:
                widget = ttk.Entry(parent, textvariable=variable)
            widget.grid(row=row + 1, column=column, sticky="ew", padx=5, pady=(0, 3))

        def choose_database(self) -> None:
            selected = filedialog.askopenfilename(filetypes=[("Wurstbrot-Datenbank", "*.json")])
            if selected: self.database_var.set(selected)

        def load_database(self) -> None:
            try:
                self.db = VehicleDatabase.from_json(self.database_var.get())
                self.solver = ResearchSolver(self.db)
                nations = sorted({v.country_id for v in self.db.vehicles.values()})
                self.nation_combo["values"] = nations
                if nations:
                    self.nation_var.set(nations[0])
                    self.refresh_branches()
                self.status_var.set(f"Datenbank {self.db.game_version}: {len(self.db.vehicles)} Fahrzeuge geladen.")
            except Exception as exc:
                messagebox.showerror("Datenbankfehler", str(exc))

        def refresh_branches(self) -> None:
            if not self.db: return
            branches = sorted({v.branch_id for v in self.db.vehicles.values() if v.country_id == self.nation_var.get()})
            self.branch_combo["values"] = branches
            if branches:
                self.branch_var.set(branches[0])
                self.refresh_vehicles()

        def refresh_vehicles(self) -> None:
            if not self.db: return
            vehicles = self.db.tree_vehicles(self.nation_var.get(), self.branch_var.get())
            self.display_to_id = {
                f"Rang {v.rank} · {v.name} [{v.id}]": v.id for v in vehicles if not v.hidden_research
            }
            displays = list(self.display_to_id)
            self.start_combo["values"] = ["Baumstart / kein Fahrzeug"] + displays
            self.target_combo["values"] = displays
            self.start_var.set("Baumstart / kein Fahrzeug")
            if displays: self.target_var.set(displays[-1])

        @staticmethod
        def parse_int(value: str, *, optional: bool = False) -> int | None:
            value = value.strip().replace(".", "").replace(",", "")
            if optional and not value: return None
            number = int(value or "0")
            if number < 0: raise ValueError("Negative Werte sind nicht erlaubt.")
            return number

        def calculate(self) -> None:
            if not self.solver or not self.db: return
            try:
                target_id = self.display_to_id[self.target_var.get()]
                start_id = self.display_to_id.get(self.start_var.get())
                progress_map: dict[str, VehicleProgress] = {}
                if target_id:
                    progress_map[target_id] = VehicleProgress(researched_rp=self.parse_int(self.target_rp_var.get()) or 0)
                if start_id and self.start_partial_var.get():
                    progress_map[start_id] = VehicleProgress(researched_rp=self.parse_int(self.start_rp_var.get()) or 0)
                progress = PlayerProgress(
                    vehicles=progress_map,
                    convertible_rp=self.parse_int(self.convertible_var.get(), optional=True),
                    owned_ge=self.parse_int(self.owned_ge_var.get()) or 0,
                )
                result = self.solver.solve(
                    target_vehicle_id=target_id,
                    start_vehicle_id=start_id,
                    progress=progress,
                    options=SolveOptions(
                        optimize_for=self.optimize_var.get(),
                        include_start_vehicle=bool(start_id and self.start_partial_var.get()),
                        sl_discount_percent=int(self.discount_var.get()),
                    ),
                )
                output = explain_result(result)
                self.result.configure(state="normal")
                self.result.delete("1.0", "end")
                self.result.insert("1.0", output)
                self.result.configure(state="disabled")
                self.status_var.set(f"Berechnet: {result.total_rp:,} RP · {result.total_ge_after_owned:,} GE · {result.total_sl:,} SL")
            except Exception as exc:
                messagebox.showerror("Berechnungsfehler", str(exc))

    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
