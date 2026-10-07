# Draft upstream issues for carbonengine

Found while building `carbon-crawler` against the public vcpkg registry (Python 3.12, x64-windows, v143).
Each issue was reproduced locally unless marked otherwise. **Not filed yet.**

---

## 1. destiny — changing `Ballpark.tickInterval` leaves `dt` and per-ball time factors stale

**Repo:** carbonengine/destiny

`tickInterval` is a plain attribute (`Ballpark_Blue.cpp`, `MAP_ATTRIBUTE("tickInterval", mTickInterval)`). Setting it:
- doesn't update `Ballpark::dt`, which is only recomputed in the constructor and in `OnTick` (`Ballpark.cpp:120`, `:244`);
- doesn't recompute each ball's cached `mTimeFactor = exp(-friction*dt/(mass*agility))` (`SetBallTimeFactor`, `Ballpark.cpp:~4981`), which is only refreshed by `SetBallMass`/`SetBallAgility` and similar.

Balls added before the first tick at the new interval keep their 1 s time factor while positions integrate with the new `dt`.

**Symptoms at 250 ms / 100 ms / 20 ms ticks:**
- acceleration happens per *tick* rather than per second (speed after N ticks is the same at every interval);
- balls first move *away* from a GotoPoint target;
- orbits oscillate by about 1 km around a 500 m orbit.

**Repro:**
```python
park = destiny.Ballpark(); park.isMaster = True; park.tickInterval = 100
# add an interactive anchor + a free ball (mass 13e6, agility 0.9, maxVel 200) at z=-100000
park.GotoPoint(ball, 0, 0, -97000); park.Start()   # pump blue.os for a few seconds
# ball.z first decreases by ~1.5 km before heading to the target
```

**Workaround:** after the first tick at the new interval, call `park.SetBallAgility(id, ball.Agility)` for every free ball. With that, the 250/100/20 ms runs match the 1000 ms trajectories closely.

**Suggested fix:** make `tickInterval` a property whose setter recomputes `dt` and calls `SetBallTimeFactor` for every ball, or add a `SetTickInterval()` method that does the same.

---

## 2. destiny.net — `Actions()` raises `AttributeError` when created after the first tick

**Repo:** carbonengine/destiny (`python/destiny/net/server/_actions.py:34`)

```python
def _get_initial_stamp_for_system(self):
    if self._park.currentTime == 0:
        return 0
    return self._park._currentTime + 1      # should be currentTime
```

**Repro:** `park = destiny.Ballpark(); park.Evolve(); Actions(park)` raises `AttributeError('_currentTime')`.

---

## 3. destiny.net — client ticker catches `StandardError` (Python 2 only)

**Repo:** carbonengine/destiny (`python/destiny/net/client/_baseticker.py:133`)

`except StandardError:` around `blue.marshal.Load` of a `PackagedAction`. In Python 3 a malformed package raises `NameError` instead of being logged. Should be `except Exception:`. (Found by reading the source; the code path is clear, but I didn't trigger it at runtime.)

---

## 4. destiny.net — `send_batch()` docstring and server test use the wrong order

**Repo:** carbonengine/destiny (`python/destiny/net/server/_parkupdatebatcher.py:55`, `test/net/server/test_ticker.py::_perform_tick`)

- The docstring says to call `send_batch()` from `DoPostTick`.
- The server test does `ticker.tick(); park.Evolve(); batcher.send_batch()`.
- But the ticker stamps actions `currentTime + 1`, and `_check_state_timestamp` expects stamps equal to `currentTime` at send time. So sending after `Evolve` logs "Found ballpark action for mismatched timestamp" for every action, and the test doesn't catch it because a mismatch only logs.

The order that works is:
- `tick()` → `send_batch()` → `Evolve()` for replicated actions;
- then `send_full_state_update()` for new joiners → `send_batch()` after `Evolve`.

---

## 5. destiny.net test helpers — two broken methods

**Repo:** carbonengine/destiny (`python/destiny/test/net/server/helpers.py`)

- `TestClientInterests.get_all_interested_ball_ids` has no `return`.
- `TestClientInterests.remove_client_interest` calls `.remove(ball_id)` on a `defaultdict`.

They're unused by the current tests, but they're the obvious template for anyone implementing `ClientInterestsInterface`.

---

## 6. io — a socket can't be read again after a recv timeout

**Repo:** carbonengine/io

After `sock.settimeout(0.3); sock.recvpacketoob()` raises `TimeoutError`, the next `recvpacketoob()` (with or without a timeout) raises:

```
BlockingIOError: [Errno 10037] An operation was attempted on a non-blocking socket that already had an operation in progress
```

The timed-out libuv read request seems to stay pending. Repro: the two calls above on a connected carbon-io socket whose peer sends nothing.

---

## 7. destiny.net — the client's "apply now if ≥ 3 ticks ahead" rule is hardcoded

**Repo:** carbonengine/destiny (`python/destiny/net/client/_ticker.py:101`)

```python
if event_stamp > self._current_time and event_stamp - self._current_time < 3:
    break   # wait
```

The client holds an update only if it's 1–2 ticks ahead. Anything 3 or more ticks ahead is applied immediately, fast-forwarding the client. That fits 1 s ticks. At short ticks (≤ 10 ms), a client has to stay several ticks behind the server to absorb network and frame jitter, and every incoming update then snaps it forward. The result is constant rewinds and a clock controller that can't hold its target.

Making the limit a ticker attribute fixed it: with 5 ms and 1 ms ticks, 2 clients, 15 s, rewinds dropped from 1–7 to 0.

**Suggested fix:** a constructor argument or attribute (e.g. `max_future_ticks`, default 3).

The same method also drains backlog. After applying a batch, if two or more further batches are queued (`if len(self._history) > 1`), it runs an extra `_parent_Evolve()`. With traffic every tick (e.g. replicated collision corrections), that makes a client that deliberately stays a few ticks behind catch up at two ticks per tick, so it can't keep any jitter buffer.

With both limits configurable (400 colliding balls, 5 and 20 ms ticks), clients held their target lead after 1–2 adjustments with 0 rewinds, instead of being pulled forward every second.

---

## 8. destiny — collision outcomes differ between parks (question rather than bug)

With 1000 massive balls in a 3 km disc at 5 ms ticks, two clients fed the identical command stream end up 0 m and 53 m off the master park. Making them non-massive gives 0 m on both. So collision resolution depends on park-local history (join time, stored snapshots, `isMaster` branches in `Ballpark.cpp` collision code), not only on the replicated commands.

Is collision meant to be server-authoritative, with corrections replicated via `SetBallPosition`/`SetBallVelocity`? Documenting the intended approach would help anyone using destiny.net.

Doing that from Python is harder than it should be:
- `Ball::DispatchCollisions` (which raises `DoCollision`) is only called for balls in `DSTBALL_MISSILE` mode (`Ballpark.cpp:612-637`).
- Ordinary balls record their contacts in `mCollisions` but never raise the event, and nothing collision-related is exposed on `Ball`/`Ballpark`.

We fell back to a Python spatial hash after each tick. It works: two clients stay at 0.0000 m with 1000 colliding balls. But it costs about 4 ms per tick at 1000 balls.

**Suggested:** dispatch `DoCollision` for every massive ball (or behind a flag), or expose the per-tick collision list.

---

## 9. trinity — skeletal animation needs Granny, which the public build leaves out

`Tr2SkinnedObject.animationUpdater` accepts any `ITr2AnimationUpdater`, but the only implementations are
`Tr2GrannyAnimation` and `Tr2GStateAnimation`. Both do their work inside `#if WITH_GRANNY`
(`Tr2GrannyAnimation.cpp`, `Tr2GStateAnimation.h`), and `WITH_GRANNY` defaults to `OFF` (`CMakeLists.txt:41-46`).
The Granny SDK is proprietary and not in the registry. A public-build user can load skinned geometry but has no way
to drive its bones.

We worked around it with vertex animation textures: Blender bakes each frame's deformed vertices into a float DDS,
and our own vertex shader samples it using per-instance effect parameters. That works well for game characters, but
it's a workaround.

**Suggested:** a minimal non-Granny `ITr2AnimationUpdater`, for example one that takes bone matrices from Python or
from a `Tr2BoneMatrixCurve` set, so skinned models are usable without the SDK.

Related observation: calling `blue.resMan.SaveObject` before creating the `TriDevice` made every later geometry load
in that process stay `isGood = False`. We didn't isolate the cause, and writing `.red` YAML directly avoids it.

---

## 10. trinity — CPU particles can only be drawn by EVE's space-scene classes

A `Tr2ParticleSystem` simulates fine from Python (`UpdateSimulation`, `Tr2DynamicEmitter` bursts), but it never
reaches the screen in a `Tr2InteriorScene`, for two reasons:
- **Upload:** the only call that copies particle data to the GPU is `Tr2ParticleSystem::SortParticles()`. It isn't
  exposed to Python, and the only callers are `EveTransform::GetRenderables`, `EveChildParticleSystem` and
  `EveChildParticleSphere`.
- **Draw:** `Tr2InteriorPlaceable::GetBatches` builds plain geometry batches (`CreateGeometryBatch`) for every mesh,
  so a `Tr2InstancedMesh` holding the particle system is never drawn instanced. `UpdateAllSystems` also has no
  callers.

We used GPU-procedural bursts in our own shader instead: each quad carries random seeds, and one per-instance
`FxTime` parameter animates the whole burst.

**Suggested:**
- expose `SortParticles` (or an update-and-upload method) to Python;
- let `Tr2InteriorPlaceable::GetBatches` defer to `Tr2InstancedMesh::GetBatches`.

---

## 11. Docs and registry friction (lower priority)

- **destiny, blue and trinity READMEs** say building needs Perforce and `CCP_EVE_PERFORCE_BRANCH_PATH`. In CMake that's only required for `BUILD_FOR_PYTHON_2`; the Python 3 build works entirely from the public vcpkg registry.
- **SSH URLs:** several registry ports use `git@github.com:` URLs (carbon-destiny, carbon-trinity, carbon-exefile, carbon-blueexposure …), so a GitHub SSH key is needed even though the repos are public. HTTPS would remove that.
- **OpenSSL version:** `carbon-io` requires `openssl >= 1.1.1k#8`, but the registry's own `openssl` port is `1.1.1k#0`. Consumers must route openssl to the default registry and add an override (as destiny's own manifest does). Worth documenting or fixing in the registry.
- **Trinity:** `Tr2PrimitiveScene::SetupPerFrameData` zeroes `ViewInverseTransposeMat`, so shaders can't get the eye position from the standard per-frame buffer.
- **Trinity 2D text:** three behaviours that cost time to discover:
  - A text object's colour alpha scales only the glyph colour, not how much the glyph darkens what's behind it, so
    fading text turns dark instead of transparent.
  - A `Tr2Sprite2dScene` draws its children last-added first.
  - **Bug:** `Tr2FontMeasurer`'s constructor never initialises `m_limit`, and `Reset()` doesn't touch it
    (`Font/Tr2FontMeasurer.cpp:88-113`). A new measurer can start with a garbage width limit, and `AddText` then
    stops after the first glyph or two (`:354`), or lays out nothing. It shows up as text lines that intermittently
    come out blank or cut to their first letter, depending on what memory each new measurer happened to reuse.
    Workaround: set `measurer.limit = 0` after creating it. **Suggested:** add `m_limit( 0 )` to the initialiser list.
- **Trinity text:** if a glyph lookup fails and `res:/ui/fonts/arialuni.ttf` is missing, `Tr2FontMeasurer::AddText` stops the line (`break`) instead of skipping the glyph. A missing fallback font silently truncates text.
