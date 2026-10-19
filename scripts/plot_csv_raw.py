import os
import pandas as pd
import matplotlib.pyplot as plt

# =========================
# USER CONFIGURATION
# =========================

# Leave as None or "" to pick the file with a file-explorer dialog
csv_file = r""

# Folder the dialog opens in (falls back to current folder if missing)
dialog_start_dir = r".\results"

# Select the waveform CSV, not its .cycles.csv companion. The waveform header is
# session_id, cycle_id, session_cycle, timestamp_ns, time_s, then CH<n>_<type>.
# Older waveform CSVs also work: columns are selected by name, not position.
# Two cycle columns to choose from:
#   'session_cycle' - 1, 2, 3... within the saved session (default: a session
#                     normally saves to one file, so these are the numbers on
#                     the sample bags)
#   'cycle_id'      - the global counter that never resets; use it to line a
#                     row up with Grafana / InfluxDB
time_column = 'time_s'
cycle_column = 'session_cycle'

temperature_columns = ['CH0_T_futaba', 'CH1_T_futaba']
pressure_columns = ['CH2_P_kistler', 'CH3_P_kistler']

# Cycles to plot:
#   'all'      -> every cycle in the file
#   9          -> one cycle
#   [1, 2, 3]  -> several cycles
cycles_to_plot = 'all'

# Time filtering
start = 0
end = None

# =========================
# FILE SELECTION
# =========================

def pick_csv(initial_dir):
    # Imported here so tkinter only loads when the dialog is needed
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()                     # no empty main window
    root.attributes('-topmost', True)   # dialog appears in front
    path = filedialog.askopenfilename(
        parent=root,
        title="Select waveform CSV to display",
        initialdir=initial_dir if os.path.isdir(initial_dir) else os.getcwd(),
        filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
    )
    root.destroy()
    return path

if not csv_file or not str(csv_file).strip():
    csv_file = pick_csv(dialog_start_dir)
    if not csv_file:
        raise SystemExit("No file selected.")

# =========================
# LOAD DATA
# =========================

df = pd.read_csv(csv_file)

# Resolve which cycles to plot
available_cycles = sorted(df[cycle_column].dropna().unique())

if isinstance(cycles_to_plot, str) and cycles_to_plot.lower() == 'all':
    cycles_to_plot = list(available_cycles)
elif not isinstance(cycles_to_plot, (list, tuple)):
    cycles_to_plot = [cycles_to_plot]
else:
    cycles_to_plot = list(cycles_to_plot)

missing = [c for c in cycles_to_plot if c not in available_cycles]
if missing:
    print(f"Warning: cycles not in file: {missing}. Available: {available_cycles}")

df = df[df[cycle_column].isin(cycles_to_plot)]
if df.empty:
    raise SystemExit("No data for the selected cycles.")

# Set end time automatically if not defined
if end is None:
    end = df[time_column].max()

# Filter by time range
mask = (df[time_column] >= start) & (df[time_column] <= end)
filtered_df = df[mask].copy()

# =========================
# PLOTTING
# =========================

fig, ax1 = plt.subplots(figsize=(12, 8))
ax2 = ax1.twinx()

ax1.set_xlabel(time_column)
ax1.set_ylabel('Temperature ºC', color='tab:red')
ax1.tick_params(axis='y', labelcolor='tab:red')
ax2.set_ylabel('Pressure bar', color='tab:blue')
ax2.tick_params(axis='y', labelcolor='tab:blue')

multi = len(cycles_to_plot) > 1

# Plot each cycle as its own line so time resets don't join cycles together
for cycle, cdf in filtered_df.groupby(cycle_column):
    suffix = f" (cycle {cycle})" if multi else ""

    for col in temperature_columns:
        if col in cdf.columns:
            ax1.plot(cdf[time_column], cdf[col], label=f"{col}{suffix}")

    for col in pressure_columns:
        if col in cdf.columns:
            ax2.plot(cdf[time_column], cdf[col], linestyle='--',
                     label=f"{col}{suffix}")

# ---- COMBINED LEGEND ----
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left',
           fontsize='small', ncol=2 if len(labels1 + labels2) > 12 else 1)

# ---- GRID / TITLE ----
ax1.grid(True, alpha=0.3)
cycle_text = "all" if multi and len(cycles_to_plot) == len(available_cycles) else cycles_to_plot
plt.title(f"{os.path.basename(csv_file)} - Cycles {cycle_text}")
plt.tight_layout()

# ---- INFO PRINT ----
print(f"File: {csv_file}")
print(f"Cycles plotted: {cycles_to_plot}")
print(f"Time range: {start} to {end}")
print(f"Total data points: {len(filtered_df)}")

plt.show()
