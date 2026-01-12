prompt:

If I choose P,P for channels 2,3 and volatge ranges 10,10 the pressure plots go crazy: fom a value to 0 and they keep ascillating like this very fast in a regular frequency! the thing is that this does not happen in T, T, P or T, T, P, P (but it does for T,P,P too)! the hardware has not changed at all, the only thin g that has changed is the channel type selected

Similiarly, it happens for T,P that they plot the same, when it is not like this in the working cases of TTPP or TTP
For me this is very weird, can you spot why is this happening?

lets discuss it before implementing changes to the code


==============================================================================


This is a very interesting bug! Let me analyze the patterns you're describing:
Pattern Analysis
Working cases:

T, T, P ✓
T, T, P, P ✓

Broken cases:

P, P ✗ (oscillates from value to 0)
T, P, P ✗ (same issue)
T, P ✗ (both channels show the SAME value)

The key observation: Working cases all have 2 temperature channels at the start. Broken cases have 0 or 1 temperature channels.
Potential Causes I've Identified
1. Pressure Conversion Index Issue
Look at this code in convert_voltage_to_units:
pythonelif ch_type == 'P':  # Pressure
    # Use appropriate pressure scale based on channel position
    pressure_idx = sum(1 for j in range(i) if self.channel_types[j] == 'P')
    if pressure_idx % 2 == 0:
        pressure_bar = voltage * (self.xmax0 / (2**(16-1)))
    else:
        pressure_bar = voltage * (self.xmax1 / (2**(16-1)))
This uses pressure_idx to alternate between two different pressure scales (xmax0 and xmax1). This seems designed for a specific hardware setup where you have paired pressure sensors that need different calibrations.
But the logic assumes pressure channels always come in pairs after temperature channels. When you have P,P as the first two channels, or T,P,P, the pairing might not match what the hardware expects.
2. Dual-Axis ViewBox Linkage Issue
When there are no temperature channels (P,P case), the main plot (left axis) has no data items. The pressure plots are all on right_viewbox. But X-axis operations are done on the main plot:
pythonself.splotlist[0].setXRange(xpoints[0], xpoints[-1], padding=0.02)
PyQtGraph's ViewBox linking can behave unexpectedly when the source plot has no data items.
3. The "Same Value" Symptom for T,P
This is a very specific clue! If both channels display identical values, it suggests:

Data is being read from the same source/index
Or one channel's data is overwriting the other
Or there's an index alignment issue between channel_types and actual data

Questions to Help Diagnose

For the P,P oscillation: Does it oscillate between the correct value and exactly 0, or between two different values?
For T,P showing same values: Do they show the temperature-converted value or the pressure-converted value? (This tells us which conversion is being applied to both)
What are s0, s1, and Qmax calibration constants for? They seem specific to your pressure sensors. Are you always using the same physical pressure sensor hardware, or do different channels connect to different sensor types?
When you configure P,P for channels 2,3: Are physical channels 2 and 3 on your DAQ actually connected to pressure sensors? Or are they the same channels that were T,T in the working configuration?
Can you test with "separate plots" mode enabled instead of dual-axis? Does the problem persist?

This will help me pinpoint whether the issue is in:

Data conversion logic
Plot indexing/setup
ViewBox dual-axis linkage
DAQ channel configuration