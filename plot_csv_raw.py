import pandas as pd
import matplotlib.pyplot as plt

# Configuration variables
variables_to_plot = ['CH0', 'CH1', 'CH2', 'CH3']  # List of columns to plot
start = 0  
end = None  

# Load CSV file
csv_file = r".\results\run4 v5.csv"  # Replace with your CSV file path
df = pd.read_csv(csv_file)

# Set end time to last recorded time if not specified
if end is None:
    end = df['Time(s)'].max()

# Filter data based on time range
mask = (df['Time(s)'] >= start) & (df['Time(s)'] <= end)
filtered_df = df[mask].copy()  # Use copy() to avoid warnings

# Create the plot with dual y-axes
fig, ax1 = plt.subplots(figsize=(12, 8))

# Plot Val0 and Val1 on the first y-axis (left) - TEMPERATURES
color1 = 'tab:red'
ax1.set_xlabel('Time(s)')
ax1.set_ylabel('Temperature ºC', color=color1)
ax1.tick_params(axis='y', labelcolor=color1)

# Plot Val0 and Val1 - RED and DARK ORANGE for temperatures
if 'CH0' in filtered_df.columns:
    line1 = ax1.plot(filtered_df['Time(s)'], filtered_df['CH0'], 
                     label='Val0', color='red')
if 'CH1' in filtered_df.columns:
    line2 = ax1.plot(filtered_df['Time(s)'], filtered_df['CH1'], 
                     label='Val1',color='darkorange')

# Create second y-axis for Val2 and Val3 - PRESSURES
ax2 = ax1.twinx()
color2 = 'tab:blue'
ax2.set_ylabel('Pressure bar', color=color2)
ax2.tick_params(axis='y', labelcolor=color2)

# Plot Val2 and Val3 on the second y-axis (right) - BLUE and MEDIUM BLUE for pressures
if 'CH2' in filtered_df.columns:
    line3 = ax2.plot(filtered_df['Time(s)'], filtered_df['CH2'], 
                     label='Val2', color='blue')
if 'CH3' in filtered_df.columns:
    line4 = ax2.plot(filtered_df['Time(s)'], filtered_df['CH3'], 
                     label='Val3', color='royalblue')

# Combine legends from both axes
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')

# Add grid and title
ax1.grid(True, alpha=0.3)
plt.title('Time Series Plot - Dual Y-Axis')
plt.tight_layout()

# Display plot information
print(f"Plotting time range: {start} to {end}")
print(f"Variables plotted: {[var for var in variables_to_plot if var in filtered_df.columns]}")
print(f"Total data points: {len(filtered_df)}")

# Show the plot
plt.show()