from __future__ import annotations

from typing import Protocol

from src.agent.state import City, ClientProfile, Country, District, Listing, RelocationCase
from src.tools.relocation_db import (
    GetCityInfoInput,
    GetClientProfileInput,
    GetCountryProfileInput,
    GetDistrictInfoInput,
    GetListingInput,
    GetRelocationCaseInput,
    SearchDistrictsInput,
    SearchDistrictsOutput,
    SearchListingsInput,
    SearchListingsOutput,
    SearchServicesInput,
    SearchServicesOutput,
    SupportedGeography,
)


class RelocationToolsProtocol(Protocol):
    def get_supported_geography(self) -> SupportedGeography: ...

    def get_client_profile(self, payload: GetClientProfileInput) -> ClientProfile | None: ...

    def get_relocation_case(self, payload: GetRelocationCaseInput) -> RelocationCase | None: ...

    def search_listings(self, payload: SearchListingsInput) -> SearchListingsOutput: ...

    def get_listing(self, payload: GetListingInput) -> Listing | None: ...

    def get_district_info(self, payload: GetDistrictInfoInput) -> District | None: ...

    def search_districts(self, payload: SearchDistrictsInput) -> SearchDistrictsOutput: ...

    def get_city_info(self, payload: GetCityInfoInput) -> City | None: ...

    def get_country_profile(self, payload: GetCountryProfileInput) -> Country | None: ...

    def search_relocation_services(self, payload: SearchServicesInput) -> SearchServicesOutput: ...
