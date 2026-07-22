TODO:

- a change in teh config channels, for isnatnce changing v_screw (CH6) to another thing like position or whartever will not update the hardcoded names in grafana and noder red... it is not robust to changes in the main program... 

- change the button of machine from write to selectable box: 160t or 55t!!

- 3) The driver quirk — daq_serial isn't "bad," but collect_data_binary1 is lossy by design

Here's what it literally does each call:

i = self.ser.in_waiting                        # how many bytes are waiting
response = self.ser.read(i - i % scan)         # read ALL whole scans out (drains buffer)
for x in range(self.numofchannel): ...         # decode only the FIRST (oldest) scan
return Channel                                  # ...and silently discard the rest

So it drains the whole buffer but keeps only the oldest scan and throws the newer ones away. Two consequences: it hands you slightly stale data (oldest, not newest), and if several scans piled up since the last read, you lose all but one — meaning your effective sample rate is capped at the loop rate, not the DAQ's configured rate.

Why it still works fine for you today: your decimation is high (dec=100), so the DAQ emits scans at a modest rate. The read loop runs far faster than scans are produced, so at read time the buffer almost always holds 0 or 1 scan — the "discard the rest" branch essentially never fires, and staleness is ~one scan. The bug is basically dormant at your current settings. That's genuinely why "it works as expected."

When it would bite: the day you lower dec / raise the sample rate to catch fast pressure transients. Then scans arrive faster than the loop drains them, the buffer holds many scans per read, and you'd keep the oldest and drop the rest — losing most of your high-rate data and adding jitter to trigger-edge timing.

What it would need (only if you go high-rate):
- Proper fix: decode and return all whole scans as a list, and have the reader stamp each with its own time. No loss, full resolution — but it touches both the driver and Read_and_Process_DaqData.
- Minimal fix: return the newest scan instead of the oldest (decode the last 16 bytes). One line, keeps you current, still lossy.
- Do nothing: perfectly fine at dec=100.

I'd rank this low priority — it's not the cause of your 1 s lag (that's the debounce), and it's harmless at your current config. File it under "know this before you crank the sample rate."
