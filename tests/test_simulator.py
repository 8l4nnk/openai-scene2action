from scene2action.simulator import segment_blocked


def test_crossing_segment_detects_obstacle_between_clear_endpoints():
    assert segment_blocked((0.1, 0.5), (0.9, 0.5), [(0.4, 0.4, 0.6, 0.6)], 0.02)


def test_carried_clearance_detects_near_miss():
    assert segment_blocked((0.1, 0.3), (0.9, 0.3), [(0.4, 0.4, 0.6, 0.6)], 0.11)
    assert not segment_blocked((0.1, 0.3), (0.9, 0.3), [(0.4, 0.4, 0.6, 0.6)], 0.02)
