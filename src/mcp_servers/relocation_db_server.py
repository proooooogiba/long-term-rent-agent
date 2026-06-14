from __future__ import annotations

from src.tools.relocation_db import (
    GetCityInfoInput,
    GetClientProfileInput,
    GetCountryProfileInput,
    GetDistrictInfoInput,
    GetListingInput,
    GetRelocationCaseInput,
    RelocationDBTools,
    SearchDistrictsInput,
    SearchListingsInput,
)


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install `mcp` to run this server.") from exc

    tools = RelocationDBTools()
    server = FastMCP("mcp-relocation-db")

    @server.tool()
    def get_client_profile(client_id: str):
        return tools.get_client_profile(GetClientProfileInput(client_id=client_id))

    @server.tool()
    def get_relocation_case(case_id: str):
        return tools.get_relocation_case(GetRelocationCaseInput(case_id=case_id))

    @server.tool()
    def search_listings(city: str, monthly_budget: float | None = None, rooms_min: int | None = None):
        return tools.search_listings(
            SearchListingsInput(
                city=city,
                monthly_budget=monthly_budget,
                rooms_min=rooms_min,
            )
        )

    @server.tool()
    def get_listing(listing_id: str):
        return tools.get_listing(GetListingInput(listing_id=listing_id))

    @server.tool()
    def get_district_info(district_id: str):
        return tools.get_district_info(GetDistrictInfoInput(district_id=district_id))

    @server.tool()
    def search_districts(city: str, is_central: bool | None = None):
        return tools.search_districts(SearchDistrictsInput(city=city, is_central=is_central))

    @server.tool()
    def get_city_info(city: str):
        return tools.get_city_info(GetCityInfoInput(city=city))

    @server.tool()
    def get_country_profile(country: str):
        return tools.get_country_profile(GetCountryProfileInput(country=country))

    return server


if __name__ == "__main__":  # pragma: no cover - optional runtime
    build_server().run()
