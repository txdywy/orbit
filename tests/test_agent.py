import math

import main


def obs(planets, player=0, fleets=None, step=0):
    return {
        "player": player,
        "planets": planets,
        "fleets": fleets or [],
        "initial_planets": [p[:] for p in planets],
        "angular_velocity": 0.03,
        "comet_planet_ids": [],
        "step": step,
    }


def test_line_crosses_sun_detects_blocked_route():
    assert main.line_crosses_sun((20, 50), (80, 50))
    assert not main.line_crosses_sun((20, 20), (30, 25))


def test_agent_avoids_sun_blocked_target():
    observation = obs(
        [
            [0, 0, 20.0, 50.0, 2.0, 80, 4],
            [1, -1, 80.0, 50.0, 2.0, 5, 5],
            [2, -1, 20.0, 90.0, 2.0, 8, 3],
        ]
    )

    moves = main.agent(observation)

    assert moves
    from_id, angle, ships = moves[0]
    assert from_id == 0
    assert ships > 0
    assert abs(angle - math.atan2(90.0 - 50.0, 20.0 - 20.0)) < 0.2


def test_agent_prefers_high_value_capture_over_nearest_low_value():
    observation = obs(
        [
            [0, 0, 20.0, 20.0, 2.0, 90, 4],
            [1, -1, 25.0, 20.0, 1.0, 18, 1],
            [2, -1, 40.0, 20.0, 2.6, 12, 5],
        ]
    )

    moves = main.agent(observation)

    assert moves
    angle = moves[0][1]
    assert abs(angle - math.atan2(20.0 - 20.0, 40.0 - 20.0)) < 0.15


def test_agent_overcommits_enough_ships_for_speed_on_good_targets():
    observation = obs(
        [
            [0, 0, 20.0, 20.0, 2.0, 100, 4],
            [1, -1, 40.0, 20.0, 2.6, 10, 5],
        ]
    )

    moves = main.agent(observation)

    assert moves
    assert moves[0][2] >= 35


def test_agent_prefers_static_targets_during_opening():
    observation = obs(
        [
            [0, 0, 20.0, 20.0, 2.0, 100, 4],
            [1, -1, 40.0, 20.0, 2.6, 5, 5],
            [2, -1, 20.0, 90.0, 2.6, 8, 3],
        ],
        step=20,
    )

    moves = main.agent(observation)

    assert moves
    assert abs(moves[0][1] - math.atan2(90.0 - 20.0, 20.0 - 20.0)) < 0.2
