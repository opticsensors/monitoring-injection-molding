import pandas as pd
import matplotlib.pyplot as plt

# =========================
# USER CONFIGURATION
# =========================

csv_file = r".\results\5mms.csv"

# Column names (CHANGE THESE IF CSV CHANGES). The CSV header now matches the
# MQTT keys exactly: cycle_id, time_s, then CH<n>_<type> with no units.
time_column = 'time_s'
cycle_column = 'cycle_id'

temperature_columns = ['CH0_T_futaba', 'CH1_T_futaba']
pressure_columns = ['CH2_P_kistler', 'CH3_P_kistler']

# Cycles to plot (single int OR list of ints)
cycles_to_plot = [1]          # Example: [1] or [1,2,3]

# Time filtering
start = 0
end = None

# =========================
# LOAD DATA
# =========================

df = pd.read_csv(csv_file)

# Set end time automatically if not defined
if end is None:
    end = df[time_column].max()

# Filter by cycle(s)
if not isinstance(cycles_to_plot, list):
    cycles_to_plot = [cycles_to_plot]

df = df[df[cycle_column].isin(cycles_to_plot)]

# Filter by time range
mask = (df[time_column] >= start) & (df[time_column] <= end)
filtered_df = df[mask].copy()

# =========================
# PLOTTING
# =========================

fig, ax1 = plt.subplots(figsize=(12, 8))

# ---- LEFT AXIS (TEMPERATURES) ----
ax1.set_xlabel(time_column)
ax1.set_ylabel('Temperature ºC', color='tab:red')
ax1.tick_params(axis='y', labelcolor='tab:red')

for col in temperature_columns:
    if col in filtered_df.columns:
        ax1.plot(filtered_df[time_column],
                 filtered_df[col],
                 label=col)

# ---- RIGHT AXIS (PRESSURES) ----
ax2 = ax1.twinx()
ax2.set_ylabel('Pressure bar', color='tab:blue')
ax2.tick_params(axis='y', labelcolor='tab:blue')

for col in pressure_columns:
    if col in filtered_df.columns:
        ax2.plot(filtered_df[time_column],
                 filtered_df[col],
                 linestyle='--',
                 label=col)

# ---- COMBINED LEGEND ----
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

# ---- GRID / TITLE ----
ax1.grid(True, alpha=0.3)
plt.title(f"Time Series Plot - Cycles {cycles_to_plot}")
plt.tight_layout()

# ---- INFO PRINT ----
print(f"Cycles plotted: {cycles_to_plot}")
print(f"Time range: {start} to {end}")
print(f"Total data points: {len(filtered_df)}")

plt.show()
