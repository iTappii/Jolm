-- Dish dictionary (Ш-67): "бешбармак", "plov", "dim sum"... -> cuisines and Jol categories, so the
-- place search understands dishes. `cuisines` are OSM `cuisine` values (informational: the import
-- keeps only the Jol category of a place, see data/osm/tag_mapping.py CUISINE_CATEGORY);
-- `categories` are Jol category slugs of the places that likely serve the dish, primary first.
-- Aliases are stored normalised: lower case, "ё" -> "е", letters/digits/spaces only. Filled by
-- data/seed/dishes.sql (source note there).
CREATE TABLE dishes (
    slug       text   PRIMARY KEY,
    name_ru    text   NOT NULL,
    name_en    text   NOT NULL,
    cuisines   text[] NOT NULL DEFAULT '{}',
    categories text[] NOT NULL DEFAULT '{}',
    source     text   NOT NULL DEFAULT 'jol_seed'
);

CREATE TABLE dish_aliases (
    alias     text PRIMARY KEY CHECK (alias = lower(alias) AND alias !~ '[ёЁ]' AND alias <> ''),
    dish_slug text NOT NULL REFERENCES dishes (slug) ON DELETE CASCADE
);
CREATE INDEX dish_aliases_trgm ON dish_aliases USING gin (alias gin_trgm_ops);
CREATE INDEX dish_aliases_dish_idx ON dish_aliases (dish_slug);
