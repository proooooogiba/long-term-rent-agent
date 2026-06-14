PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS listing_commute;
DROP TABLE IF EXISTS commute_targets;
DROP TABLE IF EXISTS city_cost_benchmarks;
DROP TABLE IF EXISTS listing_features;
DROP TABLE IF EXISTS listing_prices;
DROP TABLE IF EXISTS listings;
DROP TABLE IF EXISTS districts;
DROP TABLE IF EXISTS cities;
DROP TABLE IF EXISTS country_rules;
DROP TABLE IF EXISTS sources;

CREATE TABLE sources (
    source_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    base_url TEXT NOT NULL,
    country_code TEXT NOT NULL
);

CREATE TABLE cities (
    city_id TEXT PRIMARY KEY,
    country_code TEXT NOT NULL,
    name_ru TEXT NOT NULL,
    UNIQUE(country_code, name_ru)
);

CREATE TABLE districts (
    district_id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL,
    name_ru TEXT NOT NULL,
    UNIQUE(city_id, name_ru),
    FOREIGN KEY (city_id) REFERENCES cities (city_id)
);

CREATE TABLE listings (
    listing_id TEXT PRIMARY KEY,
    source_id INTEGER NOT NULL,
    source_listing_id TEXT NOT NULL UNIQUE,
    city_id TEXT NOT NULL,
    district_id TEXT,
    url TEXT NOT NULL,
    property_type TEXT,
    rooms INTEGER,
    area_m2 REAL,
    floor INTEGER,
    floors_total INTEGER,
    furnished TEXT,
    owner_type TEXT,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    last_seen_at TEXT NOT NULL,
    FOREIGN KEY (source_id) REFERENCES sources (source_id),
    FOREIGN KEY (city_id) REFERENCES cities (city_id),
    FOREIGN KEY (district_id) REFERENCES districts (district_id)
);

CREATE TABLE listing_prices (
    price_id INTEGER PRIMARY KEY AUTOINCREMENT,
    listing_id TEXT NOT NULL,
    price_local INTEGER,
    currency TEXT,
    deposit_local INTEGER,
    utilities_included INTEGER,
    captured_at TEXT NOT NULL,
    UNIQUE(listing_id, captured_at),
    FOREIGN KEY (listing_id) REFERENCES listings (listing_id)
);

CREATE TABLE listing_features (
    listing_id TEXT PRIMARY KEY,
    elevator INTEGER,
    parking INTEGER,
    balcony INTEGER,
    renovation TEXT,
    pets_allowed INTEGER,
    children_allowed INTEGER,
    FOREIGN KEY (listing_id) REFERENCES listings (listing_id)
);

CREATE TABLE city_cost_benchmarks (
    city_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    currency TEXT,
    cost_single_no_rent REAL,
    cost_family_no_rent REAL,
    rent_1br_center REAL,
    rent_1br_outside REAL,
    rent_3br_center REAL,
    rent_3br_outside REAL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (city_id) REFERENCES cities (city_id)
);

CREATE TABLE commute_targets (
    target_id TEXT PRIMARY KEY,
    city_id TEXT NOT NULL,
    name TEXT NOT NULL,
    lat REAL,
    lon REAL,
    FOREIGN KEY (city_id) REFERENCES cities (city_id)
);

CREATE TABLE listing_commute (
    listing_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    duration_min REAL,
    distance_km REAL,
    calculated_at TEXT NOT NULL,
    PRIMARY KEY (listing_id, target_id),
    FOREIGN KEY (listing_id) REFERENCES listings (listing_id),
    FOREIGN KEY (target_id) REFERENCES commute_targets (target_id)
);

CREATE TABLE country_rules (
    country_code TEXT PRIMARY KEY,
    internal_passport_entry_allowed INTEGER,
    trp_summary TEXT,
    pr_summary TEXT,
    citizenship_summary TEXT,
    source_doc TEXT
);

CREATE INDEX idx_market_city_name ON cities(name_ru);
CREATE INDEX idx_market_district_city ON districts(city_id);
CREATE INDEX idx_market_listings_city ON listings(city_id);
CREATE INDEX idx_market_listings_district ON listings(district_id);
CREATE INDEX idx_market_prices_listing ON listing_prices(listing_id);
