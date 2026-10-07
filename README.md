# Carbon Crawler

A small networked action-RPG built on FC's open-source [Carbon](https://github.com/carbonengine) engine (Blue,
Destiny, Trinity, carbon-io, carbon-audio), using nothing but the public vcpkg registry. It's an engine spike: an attempt
to make something that plays nothing like EVE (fast, direct control and crowds of animated monsters) on the same stack.

![A wave in progress](docs/media/screenshot.png)

You play a mage working through a run of generated cave acts. Packs of imps, spitters, brutes, hounds, shamans,
bloaters and shieldbearers sleep in the dark until they see you; a sealed arena throws waves at you, a vault rewards a
detour, shrines are checkpoints, and the Warlord's lair opens the way to the next act. You level up and pick upgrades
along the way. Several players can join one server, and AI mages can fill in for missing friends.

- **Caves from simulation.** An act starts as a designer's graph of regions (`res/arpg/acts/`). The server lays the
  regions out, then simulates karst dissolution: groundwater flows from the entrance to a spring in the boss's lair and
  dissolves layered, fractured limestone where it flows, which focuses the flow into channels. The dissolved rock becomes
  the cave, and the next act is generated in a background process while you play this one.

- **Server-authoritative simulation.** Destiny runs the world at 10 ms ticks and replicates it with destiny.net, and
  a state channel carries HP, mana and events. Your own mage is predicted locally, so input shows up on the next frame.
- **All content comes from scripts.** One headless Blender script builds every mesh, rig, animation, texture and
  placeable. Sounds and music come from a small synthesizer, and the HUD icons from a drawing script.
- **Animation without Granny.** Trinity's skinned animation needs Granny, which the public build leaves out, so
  Blender bakes each clip into a vertex animation texture and a shader plays it.

## What you need

- Windows 10 or 11 with a DirectX 11 GPU
- Visual Studio 2022 with the v143 (MSVC 14.44) toolset and ATL, and Windows SDK 10.0.26100
- Git (with Git Bash), PowerShell 7, and Python 3.12 (`py -3.12`) with `numpy`, `scipy` and `pillow` for the tools
- [Blender 5.2](https://www.blender.org/), only if you want to rebuild the art (the built assets are committed)

## Setup

Clone to a short path such as `C:\dev\carbon-crawler`: the Python build nests deep folders under `vendor/` and fails
past Windows' 260-character path limit. Then, from Git Bash in the repository folder:

```sh
git clone https://github.com/microsoft/vcpkg.git vendor/vcpkg && vendor/vcpkg/bootstrap-vcpkg.bat -disableMetrics
git clone https://github.com/carbonengine/vcpkg-registry.git vendor/vcpkg-registry
bash install_deps.sh                # builds Python 3.12, Blue, Destiny, Trinity (dx11) and audio: ~40 min the first time
pwsh -File build_shaders.ps1        # compiles res/graphics/effect/**/*.fx
bash tools/fetch_testbanks.sh       # the Wwise test banks from carbonengine/audio
py -3.12 tools/make_arpg_audio.py   # synthesizes the game's sounds and music into copies of those banks
```

`install_deps.sh` fetches the registry's `git@github.com:` URLs over HTTPS, so no SSH key is needed.

## Play

```bat
run_arpg_client.cmd                 (the main menu: host a game here, or join one from the server list)
run_arpg_server.cmd                 (a server on its own, for others to join)
run_arpg_client.cmd companion 2     (also starts two AI mages, who join the server on this machine)
set ARPG_JOIN=<server ip>:47400     (before starting the client: skip the menu and join that server)
```

The server list probes each server for its act and player count; add one by typing its address (`host` or
`host:port`), and hover one and press Delete to forget it. Esc in a game has "Leave game" to get back to the list.

| Key | Action |
|---|---|
| WASD | Move |
| Left mouse | Firebolt at the cursor |
| Right mouse | Nova |
| Q | Blink toward the cursor |
| E / R / F | Chain lightning, meteor, frost wave (unlocked at levels 2, 3 and 4) |
| Shift | Roll: a quick dodge you can't be hit during |
| Space | Jump over slams and meteor rain |
| U | Upgrades (when you have some to spend) |
| Tab | Full map (a minimap is always in the corner) |
| Esc | Menu: music and sound volume, and WASD or mouse controls (hold left to move) |

Click a spell slot to put a different spell on it. Walking past a shrine makes it your checkpoint, and spending upgrades
works at any of them. Everyone down at once ends the run: a new one starts in a new act at level 1.

The hand-built five-room dungeon is still there as a fixed test level: `set ARPG_MODE=crawl` before starting the server
plays it room by room, gates and all.

`py -3.12 tools/package.py --zip` builds a standalone copy in `dist/carbon-crawler` (and a zip), with Python, the engine
DLLs and the Visual C++ runtime included, for machines without the build tools.

## How it's put together

| Where | What |
|---|---|
| `demo/arpg_gen/` | The act generator: template instantiation, region layout, the karst simulation, interpretation into cells, repair, packs, arenas and the lightmap (server only; uses numpy) |
| `demo/arpg_game/act.py`, `packs.py` | An act's flow (checkpoints, arenas, vaults, boss, exit, the next act), and sleeping, leashed packs that follow a flow field |
| `demo/arpg_map.py` | A level: a grid of 2 m rock and floor cells plus what stands on it, as the server sends it |
| `demo/arpg_layout.py` | Sizes every level shares, and the hand-built five-room dungeon kept as a fixed test level |
| `demo/arpg_view/level_mesh.py`, `cave_mesh.py` | Builds a level's meshes at load time, one model per 16x16-cell chunk: block walls from the Blender kit (`res/arpg/kits/`), or rough cave rock by marching squares |
| `demo/arpg_world.py` | Content as data: `SPELLS`, `UPGRADES` and the enemy `KINDS` (bundles of behaviours such as `melee`, `slam`, `charge`, `mend`, `burst`, `shield`) |
| `demo/arpg_server.py`, `demo/arpg_game/` | Networking and the tick; one component per behaviour per entity, and plain system functions over them |
| `demo/arpg_client.py`, `demo/arpg_view/` | Prediction, HUD and input; an event bus feeding actors, effects, sounds and on-screen feedback |
| `demo/arpg_brain.py` | The AI mage, used by `arpg_companion.py` and by the client's autopilot (`ARPG_AUTOPLAY=1`) |
| `tools/blender/` | The Blender build: models, rigs, clips (`arpg_anims.py`), texture bakes, and the level kit pieces |
| `tools/arpg_sounds.py`, `tools/arpg_music.py` | Sound recipes and the three music loops |
| `res/graphics/effect/game/` | The shaders: lighting, vertex animation, particles, halos |

Destiny owns position, movement and collision. The state channel carries lasting fields (HP, mana, level) and one-shot
events (`state.event(id, "slam", radius=..., windup=...)`), and clients turn both into what you see and hear.

Sounds are packed into one slot of a copy of the Wwise test banks, and the client seeks to the one it wants, so new
sounds need no Wwise authoring. `ARPG_AUDIO=0` mutes the client, and `ARPG_MUSIC=0` mutes only the music.

### Tools

| Command | What |
|---|---|
| `run_act_editor.cmd [template]` | The act editor: edit a template's graph (`res/arpg/acts/`) and watch four seeds' maps follow, in layers from the cells down to the karst simulation's fields; P plays the picked seed, F2 saves |
| `blender -b --factory-startup -P tools/blender/build_arpg_assets.py` | Rebuilds every model, animation and texture in `res/arpg/` |
| `py -3.12 tools/make_arpg_ui.py` | Redraws the HUD textures in `res/arpg/ui` |
| `tools/arpg_waves_test.sh [companions] [seconds]` | Headless game: server and AI companions, printing the server's act reports |
| `tools/arpg_capture.sh [name] [frame]` | Server, bot and client on a test port; saves one frame to `demo/out/<name>.png` |
| `run_demo.ps1 -Script demo\model_gallery.py` | The placeables in a row (`GALLERY_LINEUP=hound,shaman`) |
| `run_demo.ps1 -Script demo\anim_sheet.py` | Every clip as rows of frozen poses (`SHEET_MODELS=hound:hound`) |
| `run_demo.ps1 -Script demo\fx_sheet.py` | Every particle effect at a few ages |

Server settings are environment variables: `ARPG_MODE=act|crawl|waves|sandbox` (crawl is the test dungeon, waves
endless waves in its hall), `ARPG_ACT` and `ARPG_SEED` (act), `ARPG_FIRST_ROOM` (crawl), `ARPG_FIRST_WAVE` (waves), `WAVE_SIZE=base,step`, `INTERMISSION_S`, `ENEMY_MIX` (sandbox),
`TICK_MS` and `NET_PORT`. Client settings: `NET_HOST`, `NET_PORT`,
`ARPG_CONTROLS=wasd|mouse`, `ARPG_PREDICT=1|0`, and `ARPG_DEBUG=1` for the network panel (also F3).

Test scripts use port 47410, so they don't collide with a server on the default port 47400.

`docs/upstream_issues.md` collects the problems found in the Carbon packages along the way, written up as draft bug
reports.

## Licenses

The project's own code and content are under the MIT license in `LICENSE`. The game text uses Alegreya Sans and Cinzel
(SIL Open Font License, `res/fonts/OFL_*.txt`). `res/ui/fonts/arialuni.ttf` is DejaVu Sans, saved at Trinity's fallback
font path (DejaVu license, `res/fonts/LICENSE_DEJAVU`). The Carbon packages, Python and the Wwise runtime come from the
vcpkg registry under their own licenses.
