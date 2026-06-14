PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS household_members;
DROP TABLE IF EXISTS client_preferences;
DROP TABLE IF EXISTS agent_run_history;
DROP TABLE IF EXISTS agent_case_memory;
DROP TABLE IF EXISTS relocation_cases;
DROP TABLE IF EXISTS listings;
DROP TABLE IF EXISTS districts;
DROP TABLE IF EXISTS cities;
DROP TABLE IF EXISTS countries;
DROP TABLE IF EXISTS relocation_services;
DROP TABLE IF EXISTS clients;

CREATE TABLE clients (
    client_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    citizenship TEXT NOT NULL,
    employment_type TEXT NOT NULL,
    monthly_income REAL NOT NULL,
    income_currency TEXT NOT NULL DEFAULT 'USD',
    has_local_guarantor INTEGER NOT NULL DEFAULT 0,
    has_passport INTEGER NOT NULL DEFAULT 1,
    employer_support INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE client_preferences (
    client_id TEXT PRIMARY KEY,
    preferred_districts TEXT NOT NULL DEFAULT '[]',
    furnished INTEGER,
    elevator INTEGER,
    floor_max INTEGER,
    max_commute_minutes INTEGER,
    school_requirement INTEGER,
    rooms_min INTEGER,
    lease_months INTEGER,
    comments TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE TABLE agent_case_memory (
    case_id TEXT PRIMARY KEY,
    client_id TEXT,
    last_user_message TEXT NOT NULL DEFAULT '',
    last_intent TEXT,
    last_requirements_json TEXT NOT NULL DEFAULT '{}',
    last_ranked_listings_json TEXT NOT NULL DEFAULT '[]',
    last_verification_status TEXT,
    last_final_summary TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES relocation_cases (case_id),
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE TABLE agent_run_history (
    run_id TEXT PRIMARY KEY,
    case_id TEXT,
    client_id TEXT,
    user_message TEXT NOT NULL DEFAULT '',
    intent TEXT,
    verification_status TEXT,
    ranked_count INTEGER NOT NULL DEFAULT 0,
    final_summary TEXT NOT NULL DEFAULT '',
    requirements_json TEXT NOT NULL DEFAULT '{}',
    shortlist_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (case_id) REFERENCES relocation_cases (case_id),
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE TABLE countries (
    country_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    relocation_by_internal_passport INTEGER NOT NULL,
    residence_orientation TEXT NOT NULL,
    citizenship_orientation TEXT NOT NULL,
    cost_of_living_single_range TEXT NOT NULL,
    cost_of_living_family_range TEXT NOT NULL,
    primary_city TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE cities (
    city_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    country TEXT NOT NULL,
    median_rent REAL NOT NULL,
    cost_of_living REAL NOT NULL,
    commute_guidance TEXT NOT NULL,
    popular_districts TEXT NOT NULL DEFAULT '[]',
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE districts (
    district_id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    name TEXT NOT NULL,
    avg_rent_from REAL NOT NULL,
    avg_rent_to REAL NOT NULL,
    is_central INTEGER NOT NULL DEFAULT 0,
    family_friendly INTEGER NOT NULL DEFAULT 0,
    pet_friendly INTEGER NOT NULL DEFAULT 0,
    safety_score REAL NOT NULL,
    school_score REAL NOT NULL,
    transit_score REAL NOT NULL,
    commute_to_center_minutes INTEGER NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE relocation_cases (
    case_id TEXT PRIMARY KEY,
    client_id TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    move_in_date TEXT NOT NULL,
    office_zone TEXT,
    monthly_budget REAL NOT NULL,
    upfront_budget REAL,
    max_commute_minutes INTEGER,
    preferred_districts TEXT NOT NULL DEFAULT '[]',
    furnished INTEGER,
    rooms_min INTEGER,
    lease_months INTEGER,
    urgency_level TEXT NOT NULL DEFAULT 'normal',
    document_status TEXT NOT NULL DEFAULT 'complete',
    needs_school_access INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE TABLE household_members (
    member_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    relation TEXT NOT NULL,
    age_group TEXT,
    pet_type TEXT,
    requires_school INTEGER NOT NULL DEFAULT 0,
    special_notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (case_id) REFERENCES relocation_cases (case_id),
    FOREIGN KEY (client_id) REFERENCES clients (client_id)
);

CREATE TABLE listings (
    listing_id TEXT PRIMARY KEY,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    district_id TEXT NOT NULL,
    district_name TEXT NOT NULL,
    title TEXT NOT NULL,
    property_type TEXT NOT NULL,
    monthly_rent REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    deposit_months REAL NOT NULL DEFAULT 1.0,
    agency_fee REAL NOT NULL DEFAULT 0.0,
    move_in_fee REAL NOT NULL DEFAULT 0.0,
    utilities_monthly REAL NOT NULL DEFAULT 0.0,
    area_sqm REAL NOT NULL,
    rooms INTEGER NOT NULL,
    available_from TEXT NOT NULL,
    furnished INTEGER NOT NULL DEFAULT 1,
    pet_friendly INTEGER NOT NULL DEFAULT 0,
    max_pets INTEGER,
    children_friendly INTEGER NOT NULL DEFAULT 1,
    elevator INTEGER,
    floor INTEGER,
    max_occupants INTEGER NOT NULL DEFAULT 2,
    commute_to_office_minutes INTEGER,
    commute_to_center_minutes INTEGER,
    min_lease_months INTEGER NOT NULL DEFAULT 12,
    short_term_available INTEGER NOT NULL DEFAULT 0,
    required_income_multiplier REAL,
    income_verification_required INTEGER NOT NULL DEFAULT 0,
    notes TEXT NOT NULL DEFAULT '[]',
    landlord_flags TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY (district_id) REFERENCES districts (district_id)
);

CREATE TABLE relocation_services (
    service_id TEXT PRIMARY KEY,
    city TEXT,
    country TEXT,
    service_type TEXT NOT NULL,
    name TEXT NOT NULL,
    cost REAL NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    description TEXT NOT NULL,
    suitable_for TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX idx_listings_city ON listings(city);
CREATE INDEX idx_listings_district ON listings(district_id);
CREATE INDEX idx_cases_city ON relocation_cases(city);
CREATE INDEX idx_services_city ON relocation_services(city);
CREATE INDEX idx_agent_run_history_case ON agent_run_history(case_id);
CREATE INDEX idx_agent_run_history_client ON agent_run_history(client_id);
