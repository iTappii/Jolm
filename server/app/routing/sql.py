"""Parameterized queries for the directions endpoint."""

DESTINATION_BY_ID = """
SELECT ST_Y(geom::geometry) AS lat, ST_X(geom::geometry) AS lon
FROM places
WHERE id = %s AND status = 'active'
"""
