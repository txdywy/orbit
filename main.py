import math
from collections import namedtuple


Planet = namedtuple("Planet", ["id", "owner", "x", "y", "radius", "ships", "production"])
Fleet = namedtuple("Fleet", ["id", "owner", "x", "y", "angle", "from_planet_id", "ships"])

BOARD_SIZE = 100.0
CENTER = 50.0
SUN_RADIUS = 10.0
ROTATION_RADIUS_LIMIT = 50.0
MAX_SPEED = 6.0


def get(obs, key, default=None):
    if isinstance(obs, dict):
        return obs.get(key, default)
    return getattr(obs, key, default)


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
    t = ((px - sx) * dx + (py - sy) * dy) / length2
    t = max(0.0, min(1.0, t))
    return dist(point, (sx + t * dx, sy + t * dy))


def line_crosses_sun(start, end, buffer=0.35):
    return point_to_segment_distance((CENTER, CENTER), start, end) <= SUN_RADIUS + buffer


def fleet_speed(ships):
    ships = max(1, int(ships))
    speed = 1.0 + (MAX_SPEED - 1.0) * (math.log(ships) / math.log(1000)) ** 1.5
    return min(MAX_SPEED, speed)


def is_orbiting(planet):
    return dist((planet.x, planet.y), (CENTER, CENTER)) + planet.radius < ROTATION_RADIUS_LIMIT


def planet_position_at(planet, initial_by_id, angular_velocity, future_step, comet_ids):
    if planet.id in comet_ids:
        return (planet.x, planet.y)
    initial = initial_by_id.get(planet.id)
    if initial is None:
        return (planet.x, planet.y)
    orbital_radius = dist((initial.x, initial.y), (CENTER, CENTER))
    if orbital_radius + initial.radius >= ROTATION_RADIUS_LIMIT:
        return (planet.x, planet.y)
    initial_angle = math.atan2(initial.y - CENTER, initial.x - CENTER)
    angle = initial_angle + angular_velocity * future_step
    return (
        CENTER + orbital_radius * math.cos(angle),
        CENTER + orbital_radius * math.sin(angle),
    )


def parse_planets(raw_planets):
    return [Planet(*p) for p in raw_planets]


def incoming_ships_to_owned_planets(fleets, my_planet_ids, player):
    incoming = {pid: 0 for pid in my_planet_ids}
    for fleet in fleets:
        if fleet.owner == player and fleet.from_planet_id in incoming:
            incoming[fleet.from_planet_id] += fleet.ships
    return incoming


def fleet_hits_planet(fleet, planet):
    start = (fleet.x, fleet.y)
    end = (
        fleet.x + math.cos(fleet.angle) * 130.0,
        fleet.y + math.sin(fleet.angle) * 130.0,
    )
    return point_to_segment_distance((planet.x, planet.y), start, end) <= planet.radius + 0.6


def enemy_pressure_by_planet(fleets, my_planets, player):
    pressure = {p.id: 0 for p in my_planets}
    for fleet in fleets:
        if fleet.owner in (-1, player):
            continue
        best_planet = None
        best_distance = float("inf")
        for planet in my_planets:
            if not fleet_hits_planet(fleet, planet):
                continue
            distance_to_planet = dist((fleet.x, fleet.y), (planet.x, planet.y))
            if distance_to_planet < best_distance:
                best_distance = distance_to_planet
                best_planet = planet
        if best_planet is not None:
            pressure[best_planet.id] += fleet.ships
    return pressure


def capture_need(target, owner_is_enemy, travel_turns):
    need = int(target.ships) + 1
    if owner_is_enemy:
        need += int(math.ceil(travel_turns * target.production))
    return need


def target_value(source, target, player, step, initial_by_id, angular_velocity, comet_ids, ships):
    target_pos = (target.x, target.y)
    source_pos = (source.x, source.y)
    distance_now = dist(source_pos, target_pos)
    if line_crosses_sun(source_pos, target_pos):
        return None

    speed = fleet_speed(max(1, ships))
    travel = max(1.0, distance_now / speed)
    future_pos = planet_position_at(
        target, initial_by_id, angular_velocity, step + int(round(travel)), comet_ids
    )
    if line_crosses_sun(source_pos, future_pos):
        return None

    enemy_bonus = 62.0 if target.owner not in (-1, player) else 0.0
    comet_bonus = 7.0 if target.id in comet_ids else 0.0
    static_bonus = 3.0 if not is_orbiting(target) else 0.0
    production_value = target.production * (36.0 if step < 100 else 30.0)
    cost = target.ships * (1.15 if step < 100 else 1.35) + distance_now * (1.05 if step < 80 else 0.72)
    return production_value + enemy_bonus + comet_bonus + static_bonus - cost


def choose_target(source, targets, player, step, initial_by_id, angular_velocity, comet_ids, available):
    best = None
    best_score = -1e9
    for target in targets:
        if target.id == source.id:
            continue
        if step >= 70 and target.owner not in (-1, player):
            score_bias = 45.0
        else:
            score_bias = 0.0
        rough_distance = dist((source.x, source.y), (target.x, target.y))
        commit_ratio = 0.38 if step < 90 else 0.42
        if target.production >= 4:
            commit_ratio = 0.56
        if step < 140 and target.owner == -1 and not is_orbiting(target):
            commit_ratio = max(commit_ratio, 0.62)
        if target.owner not in (-1, player):
            commit_ratio = max(commit_ratio, 0.64)
        if step > 360:
            commit_ratio = max(commit_ratio, 0.72)
        planned_commit = max(1, int(available * commit_ratio))
        if step < 70 and available >= 22 and rough_distance >= 12:
            planned_commit = max(planned_commit, 18)
        rough_travel = rough_distance / fleet_speed(min(available, planned_commit))
        need = capture_need(target, target.owner not in (-1, player), rough_travel)
        if need > available:
            continue
        committed = min(available, max(need, planned_commit))
        if step < 45 and target.owner == -1 and rough_distance >= 18 and committed < 14:
            continue
        score = target_value(
            source, target, player, step, initial_by_id, angular_velocity, comet_ids, committed
        )
        if score is None:
            continue
        if step < 100 and target.owner == -1:
            score += 34.0
        score += score_bias
        score -= max(0, need - target.production * 8) * 0.18
        score += (fleet_speed(committed) - fleet_speed(need)) * 4.0
        if score > best_score:
            best_score = score
            best = (target, committed)
    return best


def agent(obs):
    player = get(obs, "player", 0)
    planets = parse_planets(get(obs, "planets", []))
    fleets = [Fleet(*f) for f in get(obs, "fleets", [])]
    initial_planets = parse_planets(get(obs, "initial_planets", get(obs, "planets", [])))
    initial_by_id = {p.id: p for p in initial_planets}
    angular_velocity = float(get(obs, "angular_velocity", 0.035))
    comet_ids = set(get(obs, "comet_planet_ids", []))
    step = int(get(obs, "step", 0) or 0)

    my_planets = [p for p in planets if p.owner == player]
    if not my_planets:
        return []

    targets = [p for p in planets if p.owner != player and p.x >= 0 and p.y >= 0]
    if not targets:
        return []

    incoming_home = incoming_ships_to_owned_planets(
        fleets, {p.id for p in my_planets}, player
    )
    pressure = enemy_pressure_by_planet(fleets, my_planets, player)
    moves = []
    claimed_targets = set()

    for source in sorted(my_planets, key=lambda p: (p.ships, p.production), reverse=True):
        reserve = max(7, int(source.production * 3.5))
        if step < 80:
            reserve = max(3, int(source.production * 1.4))
        reserve += int(pressure.get(source.id, 0) * 0.85)
        available = int(source.ships) - reserve
        if incoming_home.get(source.id, 0) > 0:
            available -= min(available, incoming_home[source.id] // 3)
        if available <= 0:
            continue

        launches = 0
        max_launches = 2 if step < 90 else 1
        while available > 0 and launches < max_launches:
            open_targets = [t for t in targets if t.id not in claimed_targets]
            enemy_targets = [t for t in open_targets if t.owner not in (-1, player)]
            static_neutrals = [
                t for t in open_targets if t.owner == -1 and not is_orbiting(t)
            ]
            if step >= 70 and enemy_targets:
                open_targets = enemy_targets
            elif step < 110 and static_neutrals:
                open_targets = static_neutrals
            chosen = choose_target(
                source, open_targets, player, step, initial_by_id, angular_velocity, comet_ids, available
            )
            if chosen is None:
                break
            target, ships = chosen
            aim = planet_position_at(
                target,
                initial_by_id,
                angular_velocity,
                step + int(round(dist((source.x, source.y), (target.x, target.y)) / fleet_speed(ships))),
                comet_ids,
            )
            angle = math.atan2(aim[1] - source.y, aim[0] - source.x)
            ships = max(1, min(int(ships), int(source.ships) - sum(m[2] for m in moves if m[0] == source.id)))
            if ships <= 0:
                break
            moves.append([source.id, angle, ships])
            claimed_targets.add(target.id)
            available -= ships
            launches += 1

    return moves
