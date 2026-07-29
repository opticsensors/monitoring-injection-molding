TODO:

1)  add a relaticve session cycle for user readability, we have this absolute cycle number that never resets and we use it to filetr ccyles in the database by id, however user might not want to read or annotate the number of the cycle if it is big, so we need a secondary cycle that is also saved and only for that session, and resets everytime we start again new cycle or click next, what are good name for these two columns ofor cycle id? you think is good idea to add a new column just for session id?

2) add a way to display old cycles only, just for example previous cycle, intead of actuial + all old cycles in ligghter color, right now there is a way to remove 6the old cycles and leave actual, it would be nive if user could somehow naviagate to alder cycles only and just display them








MACHINE TRIGGER ISSUE --------------------------------

the trigger is two wires that goe to + and - D5 pin in DAQ
with a multimeter in the pins + and - of D5 I checked and it goes to 10v when the cycle is active
D4 and the inductive work fine, but they are not connected directly with the inductive high low volatge! they go to relay and then the nc 22 and com 21 go to D4 + and - pins! when I put metal near inductive the relays activate and thge D4 goes from 0 to 1, until I remove the metal from the pin



- a change in the config channels, for isnatnce changing v_screw (CH6) to another thing like position or whartever will not update the hardcoded names in grafana and node red... it is not robust to changes in the main program... 


- I feel that the checks of the channels to display in display tab in config window, should be an extra row in the DAQ tab, because I feel it would be cleaner


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
