import math
from collections import namedtuple


Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])

CENTER = 50.0
SUN_RADIUS = 10.0
ROTATION_RADIUS_LIMIT = 50.0
MAX_SPEED = 6.0


def get(obs, key, default=None):
    return obs.get(key, default) if isinstance(obs, dict) else getattr(obs, key, default)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def point_to_segment_distance(point, start, end):
    sx, sy = start
    ex, ey = end
    px, py = point
    dx = ex - sx
    dy = ey - sy
    length2 = dx * dx + dy * dy
    if length2 <= 1e-12:
        return dist(point, start)
    t = max(0.0, min(1.0, ((px - sx) * dx + (py - sy) * dy) / length2))
    return dist(point, (sx + t * dx, sy + t * dy))


def crosses_sun(a, b):
    return point_to_segment_distance((CENTER, CENTER), a, b) <= SUN_RADIUS + 0.25


def speed(ships):
    ships = max(1, int(ships))
    return min(MAX_SPEED, 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000)) ** 1.5)


def is_static(p):
    return dist((p.x, p.y), (CENTER, CENTER)) + p.radius >= ROTATION_RADIUS_LIMIT


def future_pos(p, initial_by_id, angular_velocity, step, ships, source):
    initial = initial_by_id.get(p.id)
    if initial is None:
        return (p.x, p.y)
    orbital_radius = dist((initial.x, initial.y), (CENTER, CENTER))
    if orbital_radius + initial.radius >= ROTATION_RADIUS_LIMIT:
        return (p.x, p.y)
    travel = dist((source.x, source.y), (p.x, p.y)) / speed(ships)
    angle0 = math.atan2(initial.y - CENTER, initial.x - CENTER)
    angle = angle0 + angular_velocity * (step + int(round(travel)))
    return (CENTER + orbital_radius * math.cos(angle), CENTER + orbital_radius * math.sin(angle))


def score_target(source, target, player, step):
    d = dist((source.x, source.y), (target.x, target.y))
    if crosses_sun((source.x, source.y), (target.x, target.y)):
        return None
    score = target.production * 35.0 - target.ships * 1.2 - d * 0.55
    if is_static(target):
        score += 38.0 if step < 260 else 14.0
    if target.owner not in (-1, player):
        score += 55.0 if step >= 100 else 12.0
    return score


def agent(obs):
    player = get(obs, "player", 0)
    planets = [Planet(*p) for p in get(obs, "planets", []) if p[2] >= 0 and p[3] >= 0]
    initial = [Planet(*p) for p in get(obs, "initial_planets", get(obs, "planets", []))]
    initial_by_id = {p.id: p for p in initial}
    angular_velocity = float(get(obs, "angular_velocity", 0.035))
    step = int(get(obs, "step", 0) or 0)

    my_planets = [p for p in planets if p.owner == player]
    targets = [p for p in planets if p.owner != player]
    moves = []
    claimed = set()

    for source in sorted(my_planets, key=lambda p: p.ships, reverse=True):
        if source.ships < 20:
            continue
        available = int(source.ships) - max(6, source.production * 2)
        if available < 18:
            continue
        candidates = [t for t in targets if t.id not in claimed]
        if step < 220:
            static_candidates = [t for t in candidates if is_static(t)]
            if static_candidates:
                candidates = static_candidates
        best = None
        best_score = -1e9
        for target in candidates:
            target_score = score_target(source, target, player, step)
            if target_score is None:
                continue
            if target_score > best_score:
                best_score = target_score
                best = target
        if best is None:
            continue
        commit = max(best.ships + 1, int(available * (0.52 if step < 220 else 0.68)))
        if best.owner not in (-1, player):
            commit = max(commit, int(available * 0.78))
        commit = min(available, int(commit))
        if commit < 18:
            continue
        aim = future_pos(best, initial_by_id, angular_velocity, step, commit, source)
        if crosses_sun((source.x, source.y), aim):
            continue
        moves.append([source.id, math.atan2(aim[1] - source.y, aim[0] - source.x), commit])
        claimed.add(best.id)
    return moves
