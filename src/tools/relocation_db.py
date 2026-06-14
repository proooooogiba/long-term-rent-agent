from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from src.agent.state import (
    City,
    ClientProfile,
    Country,
    District,
    Household,
    Listing,
    RelocationCase,
    RelocationService,
)
from src.db.seed import DEFAULT_DB_PATH


def _loads_json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    return json.loads(raw)


class GetClientProfileInput(BaseModel):
    client_id: str


class GetRelocationCaseInput(BaseModel):
    case_id: str


class SearchListingsInput(BaseModel):
    city: str
    move_in_date: date | None = None
    monthly_budget: float | None = None
    preferred_districts: list[str] = Field(default_factory=list)
    rooms_min: int | None = None
    furnished: bool | None = None
    pet_count: int = 0
    max_commute_minutes: int | None = None
    budget_slack_ratio: float = 1.25
    include_short_term: bool = True


class SearchListingsOutput(BaseModel):
    listings: list[Listing] = Field(default_factory=list)


class GetListingInput(BaseModel):
    listing_id: str


class GetDistrictInfoInput(BaseModel):
    district_id: str


class SearchDistrictsInput(BaseModel):
    city: str
    is_central: bool | None = None


class SearchDistrictsOutput(BaseModel):
    districts: list[District] = Field(default_factory=list)


class GetCityInfoInput(BaseModel):
    city: str


class GetCountryProfileInput(BaseModel):
    country: str


class SearchServicesInput(BaseModel):
    city: str | None = None
    country: str | None = None
    service_type: str | None = None
    tags: list[str] = Field(default_factory=list)


class SearchServicesOutput(BaseModel):
    services: list[RelocationService] = Field(default_factory=list)


class SupportedGeography(BaseModel):
    cities: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    city_to_country: dict[str, str] = Field(default_factory=dict)


class RelocationDBTools:
    def __init__(self, db_path: Path = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self._supported_geography_cache: SupportedGeography | None = None

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _row_to_household(rows: list[sqlite3.Row]) -> Household:
        adults = sum(1 for row in rows if row["relation"].startswith("adult") or row["relation"] == "self")
        children = sum(1 for row in rows if row["relation"] == "child")
        pets = [row["pet_type"] for row in rows if row["relation"] == "pet" and row["pet_type"]]
        return Household(adults=adults or 1, children=children, pets=pets)

    def load_household_for_case(self, case_id: str) -> Household:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT relation, pet_type
                FROM household_members
                WHERE case_id = ?
                ORDER BY member_id
                """,
                (case_id,),
            ).fetchall()
        return self._row_to_household(rows)

    def get_supported_geography(self) -> SupportedGeography:
        if self._supported_geography_cache is not None:
            return self._supported_geography_cache

        with self._connect() as connection:
            city_rows = connection.execute(
                """
                SELECT name, country
                FROM cities
                ORDER BY name
                """
            ).fetchall()
            country_rows = connection.execute(
                """
                SELECT name
                FROM countries
                ORDER BY name
                """
            ).fetchall()

        countries = [row["name"] for row in country_rows]
        if not countries:
            countries = sorted({row["country"] for row in city_rows})

        self._supported_geography_cache = SupportedGeography(
            cities=[row["name"] for row in city_rows],
            countries=countries,
            city_to_country={row["name"]: row["country"] for row in city_rows},
        )
        return self._supported_geography_cache

    @staticmethod
    def _row_to_client_profile(row: sqlite3.Row, household: Household) -> ClientProfile:
        return ClientProfile(
            client_id=row["client_id"],
            full_name=row["full_name"],
            citizenship=row["citizenship"],
            employment_type=row["employment_type"],
            monthly_income=row["monthly_income"],
            income_currency=row["income_currency"],
            has_local_guarantor=bool(row["has_local_guarantor"]),
            has_passport=bool(row["has_passport"]),
            employer_support=bool(row["employer_support"]),
            household=household,
            notes=_loads_json_list(row["notes"]),
        )

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> RelocationCase:
        return RelocationCase(
            case_id=row["case_id"],
            client_id=row["client_id"],
            city=row["city"],
            country=row["country"],
            move_in_date=date.fromisoformat(row["move_in_date"]),
            office_zone=row["office_zone"],
            monthly_budget=row["monthly_budget"],
            upfront_budget=row["upfront_budget"],
            max_commute_minutes=row["max_commute_minutes"],
            preferred_districts=_loads_json_list(row["preferred_districts"]),
            furnished=None if row["furnished"] is None else bool(row["furnished"]),
            rooms_min=row["rooms_min"],
            lease_months=row["lease_months"],
            urgency_level=row["urgency_level"],
            document_status=row["document_status"],
            needs_school_access=bool(row["needs_school_access"]),
            notes=_loads_json_list(row["notes"]),
        )

    @staticmethod
    def _row_to_listing(row: sqlite3.Row) -> Listing:
        return Listing(
            listing_id=row["listing_id"],
            city=row["city"],
            country=row["country"],
            district_id=row["district_id"],
            district_name=row["district_name"],
            title=row["title"],
            property_type=row["property_type"],
            monthly_rent=row["monthly_rent"],
            currency=row["currency"],
            deposit_months=row["deposit_months"],
            agency_fee=row["agency_fee"],
            move_in_fee=row["move_in_fee"],
            utilities_monthly=row["utilities_monthly"],
            area_sqm=row["area_sqm"],
            rooms=row["rooms"],
            available_from=date.fromisoformat(row["available_from"]),
            furnished=bool(row["furnished"]),
            pet_friendly=bool(row["pet_friendly"]),
            max_pets=row["max_pets"],
            children_friendly=bool(row["children_friendly"]),
            elevator=None if row["elevator"] is None else bool(row["elevator"]),
            floor=row["floor"],
            max_occupants=row["max_occupants"],
            commute_to_office_minutes=row["commute_to_office_minutes"],
            commute_to_center_minutes=row["commute_to_center_minutes"],
            min_lease_months=row["min_lease_months"],
            short_term_available=bool(row["short_term_available"]),
            required_income_multiplier=row["required_income_multiplier"],
            income_verification_required=bool(row["income_verification_required"]),
            notes=_loads_json_list(row["notes"]),
            landlord_flags=_loads_json_list(row["landlord_flags"]),
        )

    @staticmethod
    def _row_to_district(row: sqlite3.Row) -> District:
        return District(
            district_id=row["district_id"],
            city=row["city"],
            country=row["country"],
            name=row["name"],
            avg_rent_from=row["avg_rent_from"],
            avg_rent_to=row["avg_rent_to"],
            is_central=bool(row["is_central"]),
            family_friendly=bool(row["family_friendly"]),
            pet_friendly=bool(row["pet_friendly"]),
            safety_score=row["safety_score"],
            school_score=row["school_score"],
            transit_score=row["transit_score"],
            commute_to_center_minutes=row["commute_to_center_minutes"],
            description=row["description"],
        )

    @staticmethod
    def _row_to_city(row: sqlite3.Row) -> City:
        return City(
            name=row["name"],
            country=row["country"],
            median_rent=row["median_rent"],
            cost_of_living=row["cost_of_living"],
            commute_guidance=row["commute_guidance"],
            popular_districts=_loads_json_list(row["popular_districts"]),
            description=row["description"],
        )

    @staticmethod
    def _row_to_country(row: sqlite3.Row) -> Country:
        return Country(
            name=row["name"],
            relocation_by_internal_passport=bool(row["relocation_by_internal_passport"]),
            residence_orientation=row["residence_orientation"],
            citizenship_orientation=row["citizenship_orientation"],
            cost_of_living_single_range=row["cost_of_living_single_range"],
            cost_of_living_family_range=row["cost_of_living_family_range"],
            primary_city=row["primary_city"],
            notes=_loads_json_list(row["notes"]),
        )

    @staticmethod
    def _row_to_service(row: sqlite3.Row) -> RelocationService:
        return RelocationService(
            service_id=row["service_id"],
            city=row["city"],
            country=row["country"],
            service_type=row["service_type"],
            name=row["name"],
            cost=row["cost"],
            currency=row["currency"],
            description=row["description"],
            suitable_for=_loads_json_list(row["suitable_for"]),
        )

    def get_client_profile(self, payload: GetClientProfileInput) -> ClientProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM clients WHERE client_id = ?",
                (payload.client_id,),
            ).fetchone()
            if row is None:
                return None

            household_rows = connection.execute(
                """
                SELECT relation, pet_type
                FROM household_members
                WHERE client_id = ?
                ORDER BY member_id
                """,
                (payload.client_id,),
            ).fetchall()

        return self._row_to_client_profile(row, self._row_to_household(household_rows))

    def get_relocation_case(self, payload: GetRelocationCaseInput) -> RelocationCase | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM relocation_cases WHERE case_id = ?",
                (payload.case_id,),
            ).fetchone()
        return None if row is None else self._row_to_case(row)

    def search_listings(self, payload: SearchListingsInput) -> SearchListingsOutput:
        query = ["SELECT * FROM listings WHERE city = ?"]
        params: list[Any] = [payload.city]

        if payload.monthly_budget is not None:
            query.append("AND monthly_rent <= ?")
            params.append(round(payload.monthly_budget * payload.budget_slack_ratio, 2))

        if payload.rooms_min is not None:
            query.append("AND rooms >= ?")
            params.append(payload.rooms_min)

        if payload.furnished is not None:
            query.append("AND furnished = ?")
            params.append(1 if payload.furnished else 0)

        if not payload.include_short_term:
            query.append("AND short_term_available = 0")

        query.append("ORDER BY monthly_rent ASC, available_from ASC")

        with self._connect() as connection:
            rows = connection.execute(" ".join(query), tuple(params)).fetchall()

        listings = [self._row_to_listing(row) for row in rows]
        return SearchListingsOutput(listings=listings)

    def get_listing(self, payload: GetListingInput) -> Listing | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM listings WHERE listing_id = ?",
                (payload.listing_id,),
            ).fetchone()
        return None if row is None else self._row_to_listing(row)

    def get_district_info(self, payload: GetDistrictInfoInput) -> District | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM districts WHERE district_id = ?",
                (payload.district_id,),
            ).fetchone()
        return None if row is None else self._row_to_district(row)

    def search_districts(self, payload: SearchDistrictsInput) -> SearchDistrictsOutput:
        query = ["SELECT * FROM districts WHERE city = ?"]
        params: list[Any] = [payload.city]

        if payload.is_central is not None:
            query.append("AND is_central = ?")
            params.append(1 if payload.is_central else 0)

        query.append("ORDER BY is_central DESC, transit_score DESC, avg_rent_from ASC")

        with self._connect() as connection:
            rows = connection.execute(" ".join(query), tuple(params)).fetchall()

        return SearchDistrictsOutput(districts=[self._row_to_district(row) for row in rows])

    def get_city_info(self, payload: GetCityInfoInput) -> City | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM cities WHERE name = ?",
                (payload.city,),
            ).fetchone()
        return None if row is None else self._row_to_city(row)

    def get_country_profile(self, payload: GetCountryProfileInput) -> Country | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM countries WHERE name = ?",
                (payload.country,),
            ).fetchone()
        return None if row is None else self._row_to_country(row)

    def search_relocation_services(self, payload: SearchServicesInput) -> SearchServicesOutput:
        query = ["SELECT * FROM relocation_services WHERE 1 = 1"]
        params: list[Any] = []

        if payload.city:
            query.append("AND (city = ? OR city IS NULL)")
            params.append(payload.city)
        if payload.country:
            query.append("AND (country = ? OR country IS NULL)")
            params.append(payload.country)
        if payload.service_type:
            query.append("AND service_type = ?")
            params.append(payload.service_type)

        query.append("ORDER BY cost ASC")
        with self._connect() as connection:
            rows = connection.execute(" ".join(query), tuple(params)).fetchall()

        services = [self._row_to_service(row) for row in rows]
        if payload.tags:
            filtered = []
            for service in services:
                if any(tag in service.suitable_for for tag in payload.tags):
                    filtered.append(service)
            services = filtered

        return SearchServicesOutput(services=services)
