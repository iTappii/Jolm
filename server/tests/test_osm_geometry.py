from geometry import representative_point

SQUARE = [(0, 0), (10, 0), (10, 10), (0, 10)]


def test_centroid_of_convex_polygon():
    assert representative_point([SQUARE]) == (5.0, 5.0)


def test_point_is_inside_concave_polygon():
    # "U" shape: the centroid falls in the notch, so a point inside the arms must be returned
    u = [(0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10)]
    x, y = representative_point([u])
    in_arm = (0 <= x <= 3 or 7 <= x <= 10) and 0 <= y <= 10
    in_base = 0 <= x <= 10 and 0 <= y <= 3
    assert in_arm or in_base


def test_point_avoids_hole():
    hole = [(4, 4), (6, 4), (6, 6), (4, 6)]
    x, y = representative_point([SQUARE], [hole])
    assert not (4 <= x <= 6 and 4 <= y <= 6)
    assert 0 <= x <= 10 and 0 <= y <= 10


def test_degenerate_input():
    assert representative_point([]) is None
    assert representative_point([[(0, 0), (1, 1)]]) is None
