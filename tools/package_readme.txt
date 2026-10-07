Carbon Crawler - ARPG prototype on CCP's open-source Carbon engine (Blue, Destiny, Trinity, carbon-io, carbon-audio)

Play on one machine
  1. Double-click arpg_server.cmd (a console window; the server runs until you close it or press Ctrl+C).
  2. Double-click arpg_client.cmd once per player.
  To play with an AI ally: arpg_client.cmd companion   (or companion 2, ...)

Play over a network
  On the host:     arpg_server.cmd
  On each player:  set NET_HOST=<host ip>  then  arpg_client.cmd
  The server listens on TCP port 47400 (set NET_PORT to change it on both sides).

Controls
  WASD move, left mouse firebolt at the cursor, right mouse nova, Q blink toward the cursor, Space jump.
  Shift rolls the way you're moving (or toward the cursor): a quick dodge, untouchable while it lasts, once a second.
  A jump keeps your momentum and carries you over slams and meteor rain, though not over shots.
  E chain lightning (from level 2), R meteor (level 3), F frost wave (level 4); ARPG_UNLOCK_ALL=1 opens them all.
  Click a spell slot to rebind it. U opens the upgrades. Between waves, walk to the shrine to ready up.
  Tab switches to mouse mode (hold left to move, right for firebolt). Mouse wheel zooms. P toggles prediction, F3 the network panel. Esc opens the menu.
  Click a spell slot to put another spell on it (a new run starts from the default bar).

The game
  Survive growing waves of imps, spitters (keep their distance, lob slow fireballs) and brutes (step out of the ring
  before the slam lands). Walk over red and blue orbs for health and mana. Kills give XP; each level adds max HP and
  gives an upgrade to choose: press U (or the gold + by the spell bar) any time, then pick one of three
  (click, or 1/2/3). Between waves, walk to the shrine and ready up to start the next wave early. Every fifth wave is the Warlord: step out of its slam ring,
  dodge between its fireballs, and at half health watch for red meteor rings. If everyone is down at once it's
  back to wave 1.

Settings (environment variables, set before launching)
  Server: ARPG_MODE=waves|sandbox, WAVE_SIZE=8,4, TICK_MS (default 10), ENEMIES (sandbox only)
  Client: ARPG_CONTROLS=wasd|mouse, ARPG_AUDIO=0 to mute, ARPG_MUSIC=0 for no music, NET_HOST, NET_PORT

Requires 64-bit Windows 10/11 with a DirectX 11 GPU. Nothing to install: unzip anywhere and run.

First run
  Windows SmartScreen may warn about an unrecognised app (the exe isn't code-signed): More info > Run anyway.
  Windows Firewall asks once about arpg_server.cmd; allow it on private networks for others to join.
  Each run writes its console output to logs\ next to these files.
