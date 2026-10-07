from dataclasses import dataclass, field


@dataclass(slots=True)
class Player:
    client_id: int
    spawn: tuple
    respawn_at: int = 0
    roll_until: int = 0
    jump_until: int = 0
    jump_ready: int = 0
    roll_ready: int = 0
    queued: tuple = None


@dataclass(slots=True)
class Enemy:
    kind: str
    spec: dict
    base_speed: float


@dataclass(slots=True)
class Cooldown:
    every_s: float
    jitter: float = 0.0
    ready: int = 0


@dataclass(slots=True)
class Melee:
    damage: int
    reach: float


@dataclass(slots=True)
class Slammer:
    reach: float
    radius: float
    windup_s: float
    damage: int


@dataclass(slots=True)
class Winding:
    """A slam winding up: the enemy holds still and shrugs off knockback until it lands."""
    end: int
    radius: float
    damage: int


@dataclass(slots=True)
class KeepRange:
    near: float
    far: float


@dataclass(slots=True)
class Spit:
    speed: float
    damage: int


@dataclass(slots=True)
class Ring:
    shots: int
    speed: float
    damage: int


@dataclass(slots=True)
class Rain:
    radius: float
    delay_s: float
    damage: int
    per_player: int
    enraged_only: bool = False


@dataclass(slots=True)
class Enrage:
    at: float
    cooldown_s: float
    speedup: float
    summon: int
    summon_kind: str
    active: bool = False


@dataclass(slots=True)
class Charger:
    """Aims down a line, then rushes along it; a wall at the end of the rush leaves it reeling."""
    min_range: float
    max_range: float
    windup_s: float
    speed: float
    distance: float
    damage: int
    stun_s: float
    cooldown_s: float
    ready: int = 0


@dataclass(slots=True)
class Charging:
    """A charge in progress: phase is aim, run or stunned, each lasting until a tick."""
    phase: str
    until: int
    dx: float
    dz: float
    hit: set = field(default_factory=set)


@dataclass(slots=True)
class Burster:
    """Bursts a moment after it dies, or after it lights its own fuse next to a player; the blast hits everyone."""
    radius: float
    damage: int
    fuse_s: float
    trigger_m: float
    lit: bool = False
    pops_at: int = 0


@dataclass(slots=True)
class Shield:
    """Turns, slowly, to face the nearest player; shots arriving within the arc in front are stopped."""
    arc_deg: float
    turn_rate: float
    yaw: float = 0.0
    sent: float = 99.0


@dataclass(slots=True)
class Mend:
    """Heals the enemies around it and hurries them along for a while."""
    radius: float
    heal: int
    haste: float
    haste_s: float


@dataclass(slots=True)
class Slowed:
    until: int


@dataclass(slots=True)
class Hasted:
    until: int


@dataclass(slots=True)
class Projectile:
    owner: object
    targets: str
    damage: int
    radius: float
    expires: int
    last: tuple
    pierce: int = 0
    push: float = 0.0
    hit: set = field(default_factory=set)


@dataclass(slots=True)
class Strike:
    """Area damage landing at a tick: a meteor (hits enemies, may leave a burn) or the Warlord's rain (hits players)."""
    at: int
    x: float
    z: float
    radius: float
    damage: int
    owner: object
    targets: str
    push: float = 0.0
    burn: dict = None
    ground: bool = True


@dataclass(slots=True)
class Burn:
    until: int
    next: int
    x: float
    z: float
    radius: float
    damage: int
    every_s: float
    owner: object


@dataclass(slots=True)
class Loot:
    kind: str
    x: float
    z: float
    expires: int


@dataclass(slots=True)
class Home:
    """An enemy placed in a level as part of pack: it gives up a chase beyond leash metres from home (0: never)."""
    x: float
    z: float
    pack: int
    leash: float


@dataclass(slots=True)
class Asleep:
    pass


BEHAVIOURS = {"melee": Melee, "slam": Slammer, "keep_range": KeepRange, "spit": Spit, "ring": Ring, "rain": Rain,
              "enrage": Enrage, "mend": Mend, "charge": Charger, "burst": Burster, "shield": Shield}
