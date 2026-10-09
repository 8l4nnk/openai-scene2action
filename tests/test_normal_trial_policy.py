import pytest
from isaac.normal_trial_policy import point, passed


def test_invalid_geometry_fails_closed():
    for p in ([float('nan'), .2, .03], [0, .7, .03], [0, .2, -.1], [0, .2]):
        with pytest.raises(ValueError):
            point(p)


def test_success_requires_both_balls_inside_and_stable():
    zones = {'red_ball': [-.195, .377, 0], 'blue_ball': [.195, .377, 0]}
    sample = {k: [v[0], v[1], .03] for k, v in zones.items()}
    assert passed([sample, sample, sample], zones, [0,1,2])
    assert not passed([sample, sample, sample], zones, [0,.1,.2])
    assert not passed([sample], zones, [0])
    wrong = {**sample, 'red_ball': [0, .377, .03]}
    assert not passed([wrong] * 3, zones, [0,1,2])
    moving = {**sample, 'red_ball': [-.185, .377, .03]}
    assert not passed([sample, moving, sample], zones, [0,1,2])
    assert not passed([{'red_ball': sample['red_ball']}] * 3, zones, [0,1,2])
    elevated = {**sample,'blue_ball':[.195,.377,.06]}
    assert not passed([elevated]*3,zones,[0,1,2])
