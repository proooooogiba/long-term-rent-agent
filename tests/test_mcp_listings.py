from __future__ import annotations

from datetime import date

from src.db.seed import seed_database
from src.tools.mcp_listings import (
    CompositeRelocationDBTools,
    MCPRentalListingProvider,
    MCPRentalProviderConfig,
    MCPToolDescriptor,
    MCPTransportConfig,
)
from src.tools.relocation_db import GetListingInput, RelocationDBTools, SearchListingsInput


class FakeCianInvoker:
    def __init__(self):
        self.calls: list[tuple[str, dict[str, object]]] = []

    def list_tools(self) -> list[MCPToolDescriptor]:
        return [
            MCPToolDescriptor(
                name="igolaizola--cian-ru-scraper",
                input_schema={
                    "properties": {
                        "location": {},
                        "maxPrice": {},
                        "rooms": {},
                        "operationType": {},
                        "shortTermRent": {},
                    }
                },
            ),
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> object:
        self.calls.append((tool_name, arguments))
        return {
            "items": [
                {
                    "id": "offer-1",
                    "title": "2-комн квартира у метро",
                    "location": {"district": "Пресненский", "city": "Москва"},
                    "price": "120000",
                    "currency": "RUB",
                    "area": "54",
                    "rooms": 2,
                    "pets_allowed": True,
                    "deposit": "120000",
                    "url": "https://cian.ru/rent/offer-1",
                }
            ]
        }


class BrokenInvoker(FakeCianInvoker):
    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> object:
        raise RuntimeError("server offline")


class DatasetRunInvoker(FakeCianInvoker):
    def list_tools(self) -> list[MCPToolDescriptor]:
        base = super().list_tools()
        base.append(
            MCPToolDescriptor(
                name="get-dataset-items",
                input_schema={"properties": {"datasetId": {}, "clean": {}, "limit": {}}},
            )
        )
        return base

    def call_tool(self, tool_name: str, arguments: dict[str, object]) -> object:
        self.calls.append((tool_name, arguments))
        if tool_name == "igolaizola--cian-ru-scraper":
            return {"storages": {"datasets": {"default": {"id": "dataset-123"}}}}
        if tool_name == "get-dataset-items":
            return {
                "datasetId": "dataset-123",
                "items": [
                    {
                        "id": "offer-2",
                        "title": "Развитая локация",
                        "formattedAddress": "Москва, Уральская улица, 13",
                        "formattedFullInfo": "1-комн.кв.  •  40 м²  •  2/12 этаж",
                        "formattedFullPrice": "57 000 ₽/мес.",
                        "siteUrl": "https://www.cian.ru/rent/flat/offer-2/",
                        "hasFurniture": True,
                        "creationDate": "2026-06-01T10:00:00",
                    }
                ],
            }
        raise AssertionError(f"Unexpected tool: {tool_name}")


def _build_cian_provider(invoker: FakeCianInvoker | BrokenInvoker) -> MCPRentalListingProvider:
    return MCPRentalListingProvider(
        config=MCPRentalProviderConfig(
            provider_id="cian",
            transport=MCPTransportConfig(
                kind="streamable_http",
                url="https://mcp.apify.com/?tools=igolaizola/cian-ru-scraper&telemetry-enabled=false",
                headers={"Authorization": "Bearer ${APIFY_TOKEN}"},
            ),
            search_tool_aliases=["igolaizola/cian-ru-scraper"],
            detail_tool_aliases=[],
            fixed_search_arguments={
                "operationType": "rent",
                "category": "flatRent",
                "shortTermRent": False,
                "maxItems": 15,
                "currency": "rub",
            },
            search_argument_map={
                "location": "city",
                "maxPrice": "monthly_budget",
                "rooms": {"field": "rooms_min", "transform": "rooms_array"},
            },
            supported_cities=["Москва"],
            supported_countries=["Россия"],
            default_city_to_country={"Москва": "Россия"},
            listing_defaults={"currency": "RUB", "furnished": True, "min_lease_months": 6},
            listing_field_map={
                "city": ["location.city"],
                "district_name": ["location.district"],
            },
        ),
        invoker=invoker,
    )


def test_mcp_provider_maps_search_args_and_normalizes_results():
    invoker = FakeCianInvoker()
    provider = _build_cian_provider(invoker)

    result = provider.search_listings(
        SearchListingsInput(
            city="Москва",
            monthly_budget=120000,
            budget_currency="RUB",
            rooms_min=2,
            furnished=True,
            pet_count=1,
        )
    )

    assert invoker.calls == [
        (
            "igolaizola--cian-ru-scraper",
            {
                "operationType": "rent",
                "category": "flatRent",
                "shortTermRent": False,
                "maxItems": 15,
                "currency": "rub",
                "location": "Москва",
                "maxPrice": 120000,
                "rooms": ["2"],
            },
        )
    ]

    assert len(result.listings) == 1
    listing = result.listings[0]
    assert listing.listing_id == "cian:offer-1"
    assert listing.city == "Москва"
    assert listing.country == "Россия"
    assert listing.district_name == "Пресненский"
    assert listing.monthly_rent == 120000.0
    assert listing.deposit_months == 1.0
    assert listing.currency == "RUB"
    assert "source:cian" in listing.notes
    assert "url:https://cian.ru/rent/offer-1" in listing.notes


def test_mcp_provider_does_not_flood_schema_defaults():
    invoker = FakeCianInvoker()
    provider = _build_cian_provider(invoker)
    tool = provider._resolve_tool(provider.config.search_tool_aliases)

    arguments = provider._build_search_arguments(
        SearchListingsInput(city="Москва", monthly_budget=120000, budget_currency="RUB", rooms_min=2),
        tool.input_schema,
    )

    assert arguments == {
        "operationType": "rent",
        "category": "flatRent",
        "shortTermRent": False,
        "maxItems": 15,
        "currency": "rub",
        "location": "Москва",
        "maxPrice": 120000,
        "rooms": ["2"],
    }

    date_arguments = provider._build_search_arguments(
        SearchListingsInput(
            city="Москва",
            monthly_budget=120000,
            budget_currency="RUB",
            rooms_min=2,
            move_in_date=date(2026, 7, 1),
        ),
        tool.input_schema,
    )
    assert "onlyFlat" not in date_arguments


def test_mcp_provider_hydrates_dataset_items_from_actor_run():
    invoker = DatasetRunInvoker()
    provider = _build_cian_provider(invoker)

    result = provider.search_listings(
        SearchListingsInput(
            city="Москва",
            monthly_budget=120000,
            budget_currency="RUB",
            rooms_min=1,
        )
    )

    assert [call[0] for call in invoker.calls] == [
        "igolaizola--cian-ru-scraper",
        "get-dataset-items",
    ]
    assert len(result.listings) == 1
    listing = result.listings[0]
    assert listing.listing_id == "cian:offer-2"
    assert listing.monthly_rent == 57000.0
    assert listing.rooms == 1
    assert listing.area_sqm == 40.0
    assert listing.furnished is True
    assert "url:https://www.cian.ru/rent/flat/offer-2/" in listing.notes


def test_mcp_provider_converts_usd_budget_for_rub_query_and_normalizes_results():
    invoker = FakeCianInvoker()
    provider = _build_cian_provider(invoker)

    result = provider.search_listings(
        SearchListingsInput(
            city="Москва",
            monthly_budget=2000,
            budget_currency="USD",
            rooms_min=2,
        )
    )

    assert invoker.calls == [
        (
            "igolaizola--cian-ru-scraper",
            {
                "operationType": "rent",
                "category": "flatRent",
                "shortTermRent": False,
                "maxItems": 15,
                "currency": "rub",
                "location": "Москва",
                "maxPrice": 180000.0,
                "rooms": ["2"],
            },
        )
    ]

    assert len(result.listings) == 1
    listing = result.listings[0]
    assert listing.currency == "USD"
    assert listing.monthly_rent == 1333.33
    assert "original_price:120000 RUB" in listing.notes


def test_composite_tools_merge_external_geography_and_results(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    local_tools = RelocationDBTools(db_path)
    provider = _build_cian_provider(FakeCianInvoker())
    composite = CompositeRelocationDBTools(local_tools, [provider])

    geography = composite.get_supported_geography()
    assert "Москва" in geography.cities
    assert geography.city_to_country["Москва"] == "Россия"

    result = composite.search_listings(
        SearchListingsInput(city="Москва", monthly_budget=130000, budget_currency="RUB")
    )
    assert [listing.listing_id for listing in result.listings] == ["cian:offer-1"]

    listing = composite.get_listing(GetListingInput(listing_id="cian:offer-1"))
    assert listing is not None
    assert listing.title == "2-комн квартира у метро"


def test_composite_tools_expose_provider_failures_as_runtime_warnings(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    local_tools = RelocationDBTools(db_path)
    composite = CompositeRelocationDBTools(local_tools, [_build_cian_provider(BrokenInvoker())])

    result = composite.search_listings(
        SearchListingsInput(city="Москва", monthly_budget=130000, budget_currency="RUB")
    )
    warnings = composite.pull_runtime_warnings()

    assert result.listings == []
    assert warnings
    assert "server offline" in warnings[0]
