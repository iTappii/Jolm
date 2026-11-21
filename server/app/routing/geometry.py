"""Decode a precision-6 polyline into (latitude, longitude) pairs."""

from typing import List

from app.routing.base import Point


def decode_polyline6(encoded: str) -> List[Point]:
    points: List[Point] = []
    lat = lon = 0
    values: List[int] = []
    value = shift = 0
    for char in encoded:
        chunk = ord(char) - 63
        if not 0 <= chunk <= 63 or shift > 30:
            raise ValueError("Invalid polyline6")
        value |= (chunk & 31) << shift
        if chunk & 32:
            shift += 5
            continue
        values.append(~(value >> 1) if value & 1 else value >> 1)
        value = shift = 0
        if len(values) == 2:
            lat += values[0]
            lon += values[1]
            points.append((lat / 1e6, lon / 1e6))
            values.clear()
    if shift or values:
        raise ValueError("Incomplete polyline6")
    return points
