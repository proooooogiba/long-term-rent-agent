from __future__ import annotations

from src.db.seed import seed_database
from src.tools.calculations import CalculationTools, EstimateUpfrontCostInput
from src.tools.relocation_db import (
    GetCountryProfileInput,
    RelocationDBTools,
    SearchDistrictsInput,
    SearchListingsInput,
)


def test_search_listings_returns_expected_fields(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    tools = RelocationDBTools(db_path)
    result = tools.search_listings(SearchListingsInput(city="Алматы", monthly_budget=900, rooms_min=1, furnished=True))
    assert result.listings
    first = result.listings[0]
    assert first.listing_id
    assert first.city == "Алматы"
    assert isinstance(first.monthly_rent, float)


def test_search_listings_can_filter_by_housing_type(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    tools = RelocationDBTools(db_path)

    result = tools.search_listings(
        SearchListingsInput(city="Алматы", monthly_budget=1200, housing_type="studio")
    )

    assert result.listings
    assert all(item.property_type == "studio" for item in result.listings)


def test_estimate_upfront_cost_sums_first_month_deposit_and_fee(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    calc = CalculationTools(RelocationDBTools(db_path))
    estimate = calc.estimate_upfront_cost(EstimateUpfrontCostInput(listing_id="LS-ALM-014"))
    assert estimate.total == 1950.0
    assert estimate.deposit == 820.0
    assert estimate.first_month == 820.0


def test_search_districts_can_filter_central_districts(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    tools = RelocationDBTools(db_path)
    result = tools.search_districts(SearchDistrictsInput(city="Баку", is_central=True))
    assert [district.district_id for district in result.districts] == ["DST-BAK-01"]
    assert result.districts[0].is_central is True


def test_supported_geography_is_loaded_from_database(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    tools = RelocationDBTools(db_path)
    geography = tools.get_supported_geography()

    assert set(geography.cities) == {"Алматы", "Ереван", "Ташкент", "Минск", "Баку"}
    assert set(geography.countries) == {"Казахстан", "Армения", "Узбекистан", "Беларусь", "Азербайджан"}
    assert geography.city_to_country["Алматы"] == "Казахстан"
    assert geography.city_to_country["Минск"] == "Беларусь"


def test_country_profiles_include_official_source_links(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    tools = RelocationDBTools(db_path)

    expected_sources = {
        "Казахстан": "https://egov.kz/cms/en/articles/for_foreigners/how_to_become_kz_citizen",
        "Армения": "https://migration.e-gov.am/en/service/citizenship_application/info",
        "Узбекистан": "https://gov.uz/en/iiv/pages/fuqarolik-yoki-yashash-uchun-guvohnomani-olish-uchun-ariza-berish-tartibi-malumoti",
        "Беларусь": "https://mfa.gov.by/en/visa/registration/",
        "Азербайджан": "https://migration.gov.az/en/useful/45",
    }

    for country_name, source_url in expected_sources.items():
        profile = tools.get_country_profile(GetCountryProfileInput(country=country_name))
        assert profile is not None
        assert any(source_url in note for note in profile.notes)
