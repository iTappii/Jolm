"""Where the planner looks for places (SSOT §15: Almaty only in v1)."""

# (west, south, east, north) in degrees. Covers the city, Medeu/Shymbulak, Kok-Zhailau, Big
# Almaty Lake and Talgar's edge; excludes Charyn, Issyk and other trips out of town.
ALMATY_BBOX = (76.70, 42.95, 77.30, 43.45)

# Where a day starts when the lodging point is not known (Ш-34): Republic Square.
ALMATY_CENTRE = (43.2389, 76.9455)  # (lat, lon)
