from __future__ import annotations

import asyncio
from datetime import date, datetime
import hashlib
import json
import os
from pathlib import Path
from queue import Queue
import re
import threading
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from src.agent.state import Listing
from src.runtime_config import load_agent_runtime_config
from src.tools.contracts import RelocationToolsProtocol
from src.tools.relocation_db import (
    GetListingInput,
    RelocationDBTools,
    SearchListingsInput,
    SearchListingsOutput,
    SupportedGeography,
)


DEFAULT_RESULT_LIST_KEYS = [
    "listings",
    "items",
    "results",
    "offers",
    "properties",
    "data",
    "ads",
]

DEFAULT_LISTING_FIELD_ALIASES: dict[str, list[str]] = {
    "listing_id": ["listing_id", "id", "offer_id", "offerId", "property_id", "propertyId"],
    "title": ["title", "name", "description", "headline"],
    "city": ["city", "city_name", "location", "settlement"],
    "country": ["country", "country_name"],
    "district_id": ["district_id", "districtId", "area_id", "areaId"],
    "district_name": ["district_name", "district", "area", "districtTitle", "location_name", "formattedAddress"],
    "property_type": ["property_type", "propertyType", "type", "category"],
    "monthly_rent": ["monthly_rent", "price", "rent", "price_rub", "amount", "formattedFullPrice", "formattedShortPrice"],
    "currency": ["currency", "price_currency", "currencyCode"],
    "deposit_months": ["deposit_months", "depositMonths"],
    "deposit_amount": ["deposit_amount", "deposit", "security_deposit"],
    "agency_fee": ["agency_fee", "fee", "commission", "broker_fee"],
    "move_in_fee": ["move_in_fee", "service_fee", "booking_fee"],
    "utilities_monthly": ["utilities_monthly", "utilities", "utility_fee"],
    "area_sqm": ["area_sqm", "area", "square", "total_area"],
    "rooms": ["rooms", "room_count", "rooms_count", "bedrooms"],
    "available_from": ["available_from", "availableAt", "availability_date", "creationDate"],
    "furnished": ["furnished", "is_furnished", "with_furniture", "hasFurniture"],
    "pet_friendly": ["pet_friendly", "pets_allowed", "isPetFriendly"],
    "max_pets": ["max_pets", "pet_limit"],
    "children_friendly": ["children_friendly", "kids_allowed"],
    "elevator": ["elevator", "has_elevator"],
    "floor": ["floor", "floor_number"],
    "max_occupants": ["max_occupants", "max_tenants", "occupancy_limit"],
    "commute_to_office_minutes": ["commute_to_office_minutes", "commute_minutes"],
    "commute_to_center_minutes": ["commute_to_center_minutes"],
    "min_lease_months": ["min_lease_months", "lease_months", "minLeaseMonths"],
    "short_term_available": ["short_term_available", "short_term", "shortStay"],
    "required_income_multiplier": ["required_income_multiplier", "income_multiplier"],
    "income_verification_required": ["income_verification_required", "income_verification"],
    "url": ["url", "link", "full_url", "fullUrl", "siteUrl"],
}


class SearchArgumentBinding(BaseModel):
    field: str
    transform: Literal["identity", "iso_date", "positive_to_bool", "bool", "rooms_array"] = "identity"


class MCPTransportConfig(BaseModel):
    kind: Literal["stdio", "streamable_http"]
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    env: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    timeout_seconds: float = 20.0

    @model_validator(mode="after")
    def validate_transport(self) -> "MCPTransportConfig":
        if self.kind == "stdio" and not self.command:
            raise ValueError("stdio transport requires `command`.")
        if self.kind == "streamable_http" and not self.url:
            raise ValueError("streamable_http transport requires `url`.")
        return self


class MCPRentalProviderConfig(BaseModel):
    provider_id: str
    enabled: bool = True
    transport: MCPTransportConfig
    search_tool_aliases: list[str] = Field(default_factory=lambda: ["search_market", "list_listings"])
    detail_tool_aliases: list[str] = Field(default_factory=lambda: ["get_property", "get_listing"])
    search_argument_map: dict[str, str | SearchArgumentBinding] = Field(default_factory=dict)
    detail_argument_map: dict[str, str | SearchArgumentBinding] = Field(default_factory=dict)
    fixed_search_arguments: dict[str, Any] = Field(default_factory=dict)
    fixed_detail_arguments: dict[str, Any] = Field(default_factory=dict)
    supported_cities: list[str] = Field(default_factory=list)
    supported_countries: list[str] = Field(default_factory=list)
    default_country: str | None = None
    default_city_to_country: dict[str, str] = Field(default_factory=dict)
    listing_defaults: dict[str, Any] = Field(default_factory=dict)
    listing_field_map: dict[str, str | list[str]] = Field(default_factory=dict)
    result_list_keys: list[str] = Field(default_factory=lambda: list(DEFAULT_RESULT_LIST_KEYS))
    max_results: int = 15


class MCPRuntimeConfig(BaseModel):
    include_local_listings: bool = True
    providers: list[MCPRentalProviderConfig] = Field(default_factory=list)


class MCPToolDescriptor(BaseModel):
    name: str
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MCPToolInvoker(Protocol):
    def list_tools(self) -> list[MCPToolDescriptor]: ...

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any: ...


def _expand_env_value(raw: str) -> str:
    return os.path.expandvars(raw)


def _run_async_sync(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    results: Queue[tuple[bool, Any]] = Queue()

    def _runner() -> None:
        try:
            results.put((True, asyncio.run(coro)))
        except BaseException as exc:  # pragma: no cover - defensive bridge
            results.put((False, exc))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    ok, payload = results.get()
    thread.join()
    if ok:
        return payload
    raise payload


class PythonSDKMCPToolInvoker:
    def __init__(self, transport: MCPTransportConfig):
        self.transport = transport

    def list_tools(self) -> list[MCPToolDescriptor]:
        return _run_async_sync(self._list_tools_async())

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        return _run_async_sync(self._call_tool_async(tool_name, arguments))

    async def _list_tools_async(self) -> list[MCPToolDescriptor]:
        async def _collect(session: Any) -> list[MCPToolDescriptor]:
            result = await asyncio.wait_for(session.list_tools(), timeout=self.transport.timeout_seconds)
            tools = getattr(result, "tools", result)
            descriptors: list[MCPToolDescriptor] = []
            for tool in tools:
                descriptors.append(
                    MCPToolDescriptor(
                        name=getattr(tool, "name"),
                        input_schema=getattr(tool, "inputSchema", {}) or getattr(tool, "input_schema", {}) or {},
                    )
                )
            return descriptors

        return await self._with_session(_collect)

    async def _call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        async def _invoke(session: Any) -> Any:
            result = await asyncio.wait_for(
                session.call_tool(tool_name, arguments=arguments),
                timeout=self.transport.timeout_seconds,
            )
            if getattr(result, "isError", False):
                payload = _extract_tool_payload(result)
                raise RuntimeError(f"MCP tool `{tool_name}` failed: {payload}")
            return _extract_tool_payload(result)

        return await self._with_session(_invoke)

    async def _with_session(self, callback: Any) -> Any:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError(
                "Install `mcp>=1.27,<2` to use external MCP rental providers."
            ) from exc

        if self.transport.kind == "stdio":
            env = os.environ.copy()
            env.update({key: _expand_env_value(value) for key, value in self.transport.env.items()})
            server_params = StdioServerParameters(
                command=self.transport.command,
                args=self.transport.args,
                env=env,
            )
            async with stdio_client(server_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await asyncio.wait_for(session.initialize(), timeout=self.transport.timeout_seconds)
                    return await callback(session)

        headers = {key: _expand_env_value(value) for key, value in self.transport.headers.items()}
        async with streamablehttp_client(
            _expand_env_value(self.transport.url or ""),
            headers=headers or None,
        ) as (read, write, _):
            async with ClientSession(read, write) as session:
                await asyncio.wait_for(session.initialize(), timeout=self.transport.timeout_seconds)
                return await callback(session)


class MCPRentalListingProvider:
    def __init__(
        self,
        config: MCPRentalProviderConfig,
        invoker: MCPToolInvoker | None = None,
    ):
        self.config = config
        self.invoker = invoker or PythonSDKMCPToolInvoker(config.transport)
        self._tool_cache: list[MCPToolDescriptor] | None = None
        self._listing_cache: dict[str, Listing] = {}

    @property
    def provider_id(self) -> str:
        return self.config.provider_id

    def get_supported_geography(self) -> SupportedGeography:
        city_to_country = dict(self.config.default_city_to_country)
        default_country = self.config.default_country or (self.config.supported_countries[0] if self.config.supported_countries else None)
        if default_country:
            for city in self.config.supported_cities:
                city_to_country.setdefault(city, default_country)
        countries = list(dict.fromkeys([*self.config.supported_countries, *city_to_country.values()]))
        return SupportedGeography(
            cities=list(dict.fromkeys(self.config.supported_cities)),
            countries=countries,
            city_to_country=city_to_country,
        )

    def search_listings(self, payload: SearchListingsInput) -> SearchListingsOutput:
        tool = self._resolve_tool(self.config.search_tool_aliases)
        arguments = self._build_search_arguments(payload, tool.input_schema)
        raw_result = self.invoker.call_tool(tool.name, arguments)
        raw_result = self._hydrate_search_records(raw_result)
        normalized = [
            listing
            for record in self._extract_records(raw_result)
            if (listing := self._normalize_listing(record, payload)) is not None
        ]
        for listing in normalized:
            self._listing_cache[listing.listing_id] = listing
        normalized.sort(key=lambda item: (item.monthly_rent, item.available_from))
        return SearchListingsOutput(listings=normalized[: self.config.max_results])

    def _hydrate_search_records(self, raw_result: Any) -> Any:
        dataset_id = self._extract_dataset_id(raw_result)
        if not dataset_id:
            return raw_result

        dataset_tool = self._resolve_tool(["get-dataset-items"], required=False)
        if dataset_tool is None:
            return raw_result

        return self.invoker.call_tool(
            dataset_tool.name,
            {
                "datasetId": dataset_id,
                "clean": True,
                "limit": self.config.max_results,
            },
        )

    def _extract_dataset_id(self, raw_result: Any) -> str | None:
        if not isinstance(raw_result, dict):
            return None

        dataset_id = _resolve_path(raw_result, "storages.datasets.default.id")
        if isinstance(dataset_id, str) and dataset_id.strip():
            return dataset_id.strip()

        direct_dataset_id = raw_result.get("datasetId")
        if isinstance(direct_dataset_id, str) and direct_dataset_id.strip():
            return direct_dataset_id.strip()

        return None

    def get_listing(self, listing_id: str) -> Listing | None:
        cached = self._listing_cache.get(listing_id)
        if cached is not None:
            return cached.model_copy(deep=True)

        tool = self._resolve_tool(self.config.detail_tool_aliases, required=False)
        if tool is None:
            return None

        external_id = self._strip_provider_prefix(listing_id)
        arguments = self._build_detail_arguments(tool.input_schema, external_id)
        raw_result = self.invoker.call_tool(tool.name, arguments)
        record = self._extract_single_record(raw_result)
        if record is None:
            return None
        listing = self._normalize_listing(record, None, listing_id_hint=listing_id)
        if listing is None:
            return None
        self._listing_cache[listing.listing_id] = listing
        return listing.model_copy(deep=True)

    def _resolve_tool(
        self,
        aliases: list[str],
        *,
        required: bool = True,
    ) -> MCPToolDescriptor | None:
        if self._tool_cache is None:
            self._tool_cache = self.invoker.list_tools()

        normalized_aliases = {_normalize_tool_name(alias) for alias in aliases}
        for tool in self._tool_cache:
            if _normalize_tool_name(tool.name) in normalized_aliases:
                return tool
        for tool in self._tool_cache:
            normalized_name = _normalize_tool_name(tool.name)
            if any(alias in normalized_name or normalized_name in alias for alias in normalized_aliases):
                return tool

        if not required:
            return None
        available = ", ".join(tool.name for tool in self._tool_cache) or "none"
        expected = ", ".join(aliases)
        raise RuntimeError(
            f"MCP provider `{self.provider_id}` is missing expected tools ({expected}). Available: {available}."
        )

    def _build_search_arguments(self, payload: SearchListingsInput, input_schema: dict[str, Any]) -> dict[str, Any]:
        arguments = dict(self.config.fixed_search_arguments)
        for name, binding in self.config.search_argument_map.items():
            value = _resolve_binding_value(payload, binding)
            if value is not None:
                arguments[name] = value

        schema_properties = input_schema.get("properties", {})
        property_names = _schema_properties(input_schema)
        for property_name in property_names:
            if property_name in arguments:
                continue
            if _semantic_argument_already_present(arguments, property_name):
                continue
            guessed = _guess_search_argument(property_name, payload, self.config.default_country)
            if guessed is not None:
                arguments[property_name] = guessed

        for property_name, value in list(arguments.items()):
            schema = schema_properties.get(property_name)
            if isinstance(schema, dict):
                arguments[property_name] = _coerce_argument_value_for_schema(value, schema)
        return arguments

    def _build_detail_arguments(self, input_schema: dict[str, Any], listing_id: str) -> dict[str, Any]:
        arguments = dict(self.config.fixed_detail_arguments)
        synthetic = _DetailPayload(listing_id=listing_id)
        for name, binding in self.config.detail_argument_map.items():
            value = _resolve_binding_value(synthetic, binding)
            if value is not None:
                arguments[name] = value

        schema_properties = _schema_properties(input_schema)
        for property_name in schema_properties:
            if property_name in arguments:
                continue
            lowered = property_name.lower()
            if lowered in {"id", "listing_id", "property_id", "offer_id"} or lowered.endswith("_id"):
                arguments[property_name] = listing_id
        if not arguments:
            arguments["id"] = listing_id
        return arguments

    def _extract_records(self, raw_result: Any) -> list[dict[str, Any]]:
        if isinstance(raw_result, list):
            return [item for item in raw_result if isinstance(item, dict)]
        if isinstance(raw_result, dict):
            for key in self.config.result_list_keys:
                value = _resolve_path(raw_result, key)
                if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                    return list(value)
            for value in raw_result.values():
                if isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
                    return list(value)
        return []

    def _extract_single_record(self, raw_result: Any) -> dict[str, Any] | None:
        if isinstance(raw_result, dict):
            for key in self.config.result_list_keys:
                value = _resolve_path(raw_result, key)
                if isinstance(value, dict):
                    return value
            for key in ("listing", "property", "result", "item", "data"):
                value = raw_result.get(key)
                if isinstance(value, dict):
                    return value
            return raw_result
        records = self._extract_records(raw_result)
        return records[0] if records else None

    def _normalize_listing(
        self,
        record: dict[str, Any],
        search_payload: SearchListingsInput | None,
        *,
        listing_id_hint: str | None = None,
    ) -> Listing | None:
        raw_id = _extract_from_record(record, self._field_aliases("listing_id"))
        url = _extract_from_record(record, self._field_aliases("url"))
        resolved_id = listing_id_hint or self._compose_listing_id(raw_id, url, record)

        city = _to_string(_extract_from_record(record, self._field_aliases("city"))) or (search_payload.city if search_payload else None)
        city = city or self._infer_city_from_record(record)
        if city is None:
            city = "Не указан"

        country = _to_string(_extract_from_record(record, self._field_aliases("country")))
        if not country:
            geography = self.get_supported_geography()
            country = geography.city_to_country.get(city) or self.config.default_country or "Не указана"

        district_name = _to_string(_extract_from_record(record, self._field_aliases("district_name"))) or "Район не указан"
        district_id = _to_string(_extract_from_record(record, self._field_aliases("district_id"))) or self._build_district_id(district_name)
        title = _to_string(_extract_from_record(record, self._field_aliases("title"))) or f"{self.provider_id}:{district_name}"

        monthly_rent = _to_float(_extract_from_record(record, self._field_aliases("monthly_rent")))
        if monthly_rent is None or monthly_rent <= 0:
            return None

        raw_area = _extract_from_record(record, self._field_aliases("area_sqm"))
        area_sqm = _to_float(raw_area)
        if area_sqm is None and isinstance(raw_area, str):
            area_sqm = _infer_area_from_text(raw_area)
        if area_sqm is None:
            area_sqm = _infer_area_from_text(
                " ".join(
                    filter(
                        None,
                        [
                            _to_string(record.get("formattedFullInfo")),
                            _to_string(record.get("formattedCardInfo")),
                            title,
                        ],
                    )
                )
            )
        if area_sqm is None or area_sqm <= 0:
            area_sqm = _to_float(self.config.listing_defaults.get("area_sqm")) or 30.0

        raw_rooms = _extract_from_record(record, self._field_aliases("rooms"))
        rooms = _to_int(raw_rooms)
        if rooms is None and isinstance(raw_rooms, str):
            rooms = _infer_rooms_from_text(raw_rooms)
        if rooms is None:
            rooms = _infer_rooms_from_text(
                " ".join(
                    filter(
                        None,
                        [
                            title,
                            _to_string(record.get("formattedFullInfo")),
                            _to_string(record.get("formattedCardInfo")),
                        ],
                    )
                )
            )
        if rooms is None:
            rooms = _infer_rooms_from_text(title) or _to_int(self.config.listing_defaults.get("rooms")) or 1

        currency = _to_string(_extract_from_record(record, self._field_aliases("currency"))) or _to_string(
            self.config.listing_defaults.get("currency")
        ) or "RUB"
        property_type = _to_string(_extract_from_record(record, self._field_aliases("property_type"))) or self._infer_property_type(title)

        available_from = _to_date(_extract_from_record(record, self._field_aliases("available_from"))) or date.today()
        furnished = _coerce_bool(_extract_from_record(record, self._field_aliases("furnished")))
        if furnished is None:
            furnished = bool(self.config.listing_defaults.get("furnished", True))

        pet_friendly = _coerce_bool(_extract_from_record(record, self._field_aliases("pet_friendly")))
        if pet_friendly is None:
            pet_friendly = bool(self.config.listing_defaults.get("pet_friendly", False))

        children_friendly = _coerce_bool(_extract_from_record(record, self._field_aliases("children_friendly")))
        if children_friendly is None:
            children_friendly = bool(self.config.listing_defaults.get("children_friendly", True))

        short_term_available = _coerce_bool(_extract_from_record(record, self._field_aliases("short_term_available")))
        if short_term_available is None:
            short_term_available = bool(self.config.listing_defaults.get("short_term_available", False))

        income_verification_required = _coerce_bool(
            _extract_from_record(record, self._field_aliases("income_verification_required"))
        )
        if income_verification_required is None:
            income_verification_required = bool(self.config.listing_defaults.get("income_verification_required", False))

        deposit_months = self._derive_deposit_months(record, monthly_rent)
        agency_fee = _to_float(_extract_from_record(record, self._field_aliases("agency_fee"))) or _to_float(
            self.config.listing_defaults.get("agency_fee")
        ) or 0.0
        move_in_fee = _to_float(_extract_from_record(record, self._field_aliases("move_in_fee"))) or _to_float(
            self.config.listing_defaults.get("move_in_fee")
        ) or 0.0
        utilities_monthly = _to_float(_extract_from_record(record, self._field_aliases("utilities_monthly"))) or _to_float(
            self.config.listing_defaults.get("utilities_monthly")
        ) or 0.0
        max_pets = _to_int(_extract_from_record(record, self._field_aliases("max_pets")))
        floor = _to_int(_extract_from_record(record, self._field_aliases("floor")))
        max_occupants = _to_int(_extract_from_record(record, self._field_aliases("max_occupants"))) or _to_int(
            self.config.listing_defaults.get("max_occupants")
        ) or 2
        commute_to_office_minutes = _to_int(_extract_from_record(record, self._field_aliases("commute_to_office_minutes")))
        commute_to_center_minutes = _to_int(_extract_from_record(record, self._field_aliases("commute_to_center_minutes")))
        min_lease_months = _to_int(_extract_from_record(record, self._field_aliases("min_lease_months"))) or _to_int(
            self.config.listing_defaults.get("min_lease_months")
        ) or 6
        required_income_multiplier = _to_float(
            _extract_from_record(record, self._field_aliases("required_income_multiplier"))
        ) or _to_float(self.config.listing_defaults.get("required_income_multiplier"))
        elevator = _coerce_bool(_extract_from_record(record, self._field_aliases("elevator")))

        notes = _normalize_string_list(self.config.listing_defaults.get("notes"))
        notes.extend(_normalize_string_list(record.get("notes")))
        notes.append(f"source:{self.provider_id}")
        if url:
            notes.append(f"url:{url}")

        landlord_flags = _normalize_string_list(self.config.listing_defaults.get("landlord_flags"))
        landlord_flags.extend(_normalize_string_list(record.get("landlord_flags")))
        if income_verification_required and "full_docs_required" not in landlord_flags:
            landlord_flags.append("full_docs_required")

        listing = Listing(
            listing_id=resolved_id,
            city=city,
            country=country,
            district_id=district_id,
            district_name=district_name,
            title=title,
            property_type=property_type,
            monthly_rent=monthly_rent,
            currency=currency,
            deposit_months=deposit_months,
            agency_fee=agency_fee,
            move_in_fee=move_in_fee,
            utilities_monthly=utilities_monthly,
            area_sqm=area_sqm,
            rooms=rooms,
            available_from=available_from,
            furnished=furnished,
            pet_friendly=pet_friendly,
            max_pets=max_pets,
            children_friendly=children_friendly,
            elevator=elevator,
            floor=floor,
            max_occupants=max_occupants,
            commute_to_office_minutes=commute_to_office_minutes,
            commute_to_center_minutes=commute_to_center_minutes,
            min_lease_months=min_lease_months,
            short_term_available=short_term_available,
            required_income_multiplier=required_income_multiplier,
            income_verification_required=income_verification_required,
            notes=list(dict.fromkeys(notes)),
            landlord_flags=list(dict.fromkeys(landlord_flags)),
        )
        return listing

    def _field_aliases(self, field_name: str) -> list[str]:
        configured = self.config.listing_field_map.get(field_name)
        aliases = []
        if isinstance(configured, str):
            aliases.append(configured)
        elif isinstance(configured, list):
            aliases.extend(item for item in configured if isinstance(item, str))
        aliases.extend(DEFAULT_LISTING_FIELD_ALIASES.get(field_name, []))
        return list(dict.fromkeys(aliases))

    def _compose_listing_id(self, raw_id: Any, url: Any, record: dict[str, Any]) -> str:
        base_id = _to_string(raw_id)
        if base_id:
            return f"{self.provider_id}:{base_id}"
        if url:
            return f"{self.provider_id}:{hashlib.md5(str(url).encode('utf-8')).hexdigest()[:12]}"
        record_hash = hashlib.md5(json.dumps(record, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
        return f"{self.provider_id}:{record_hash}"

    def _build_district_id(self, district_name: str) -> str:
        normalized = re.sub(r"\s+", "_", district_name.strip().lower())
        return f"{self.provider_id}:district:{normalized or 'unknown'}"

    def _strip_provider_prefix(self, listing_id: str) -> str:
        prefix = f"{self.provider_id}:"
        return listing_id[len(prefix) :] if listing_id.startswith(prefix) else listing_id

    def _derive_deposit_months(self, record: dict[str, Any], monthly_rent: float) -> float:
        deposit_months = _to_float(_extract_from_record(record, self._field_aliases("deposit_months")))
        if deposit_months is not None:
            return deposit_months

        deposit_amount = _to_float(_extract_from_record(record, self._field_aliases("deposit_amount")))
        if deposit_amount is not None and monthly_rent > 0:
            return round(max(deposit_amount / monthly_rent, 0.0), 2)

        default_deposit = _to_float(self.config.listing_defaults.get("deposit_months"))
        return default_deposit if default_deposit is not None else 1.0

    def _infer_property_type(self, title: str) -> str:
        lowered = title.lower()
        if "студ" in lowered or "studio" in lowered:
            return "studio"
        return _to_string(self.config.listing_defaults.get("property_type")) or "apartment"

    def _infer_city_from_record(self, record: dict[str, Any]) -> str | None:
        geography = self.get_supported_geography()
        for city in geography.cities:
            if city.lower() in json.dumps(record, ensure_ascii=False).lower():
                return city
        return None


class _DetailPayload(BaseModel):
    listing_id: str


class CompositeRelocationDBTools:
    def __init__(
        self,
        local_db: RelocationToolsProtocol,
        external_providers: list[MCPRentalListingProvider],
        *,
        include_local_listings: bool = True,
    ):
        self.local_db = local_db
        self.external_providers = external_providers
        self.include_local_listings = include_local_listings
        self._runtime_warnings: list[str] = []
        self._supported_geography_cache: SupportedGeography | None = None

    def pull_runtime_warnings(self) -> list[str]:
        warnings = self._runtime_warnings[:]
        self._runtime_warnings.clear()
        return warnings

    def get_supported_geography(self) -> SupportedGeography:
        if self._supported_geography_cache is not None:
            return self._supported_geography_cache

        base = self.local_db.get_supported_geography()
        cities = list(base.cities)
        countries = list(base.countries)
        city_to_country = dict(base.city_to_country)

        for provider in self.external_providers:
            geography = provider.get_supported_geography()
            cities.extend(geography.cities)
            countries.extend(geography.countries)
            city_to_country.update(geography.city_to_country)

        self._supported_geography_cache = SupportedGeography(
            cities=list(dict.fromkeys(cities)),
            countries=list(dict.fromkeys(countries)),
            city_to_country=city_to_country,
        )
        return self._supported_geography_cache

    def get_client_profile(self, payload: Any) -> Any:
        return self.local_db.get_client_profile(payload)

    def get_relocation_case(self, payload: Any) -> Any:
        return self.local_db.get_relocation_case(payload)

    def search_listings(self, payload: SearchListingsInput) -> SearchListingsOutput:
        listings: list[Listing] = []

        if self.include_local_listings:
            listings.extend(self.local_db.search_listings(payload).listings)

        for provider in self.external_providers:
            try:
                listings.extend(provider.search_listings(payload).listings)
            except Exception as exc:
                self._runtime_warnings.append(
                    f"Внешний MCP-провайдер `{provider.provider_id}` недоступен: {exc}"
                )

        listings.sort(key=lambda item: (item.monthly_rent, item.available_from))
        return SearchListingsOutput(listings=listings)

    def get_listing(self, payload: GetListingInput) -> Listing | None:
        listing = self.local_db.get_listing(payload)
        if listing is not None:
            return listing

        provider = self._provider_for_listing_id(payload.listing_id)
        if provider is None:
            return None
        try:
            return provider.get_listing(payload.listing_id)
        except Exception as exc:
            self._runtime_warnings.append(
                f"Не удалось загрузить детальную карточку `{payload.listing_id}` из `{provider.provider_id}`: {exc}"
            )
            return None

    def get_district_info(self, payload: Any) -> Any:
        return self.local_db.get_district_info(payload)

    def search_districts(self, payload: Any) -> Any:
        return self.local_db.search_districts(payload)

    def get_city_info(self, payload: Any) -> Any:
        return self.local_db.get_city_info(payload)

    def get_country_profile(self, payload: Any) -> Any:
        return self.local_db.get_country_profile(payload)

    def search_relocation_services(self, payload: Any) -> Any:
        return self.local_db.search_relocation_services(payload)

    def _provider_for_listing_id(self, listing_id: str) -> MCPRentalListingProvider | None:
        prefix, _, _ = listing_id.partition(":")
        for provider in self.external_providers:
            if provider.provider_id == prefix:
                return provider
        return None


def load_mcp_runtime_config() -> MCPRuntimeConfig | None:
    project_root = Path(__file__).resolve().parents[2]
    inline_config = os.getenv("AGENT_MCP_CONFIG_JSON")
    if inline_config:
        return MCPRuntimeConfig.model_validate(json.loads(inline_config))

    explicit_path = os.getenv("AGENT_MCP_CONFIG_PATH")
    runtime_config = load_agent_runtime_config()
    runtime_mcp_settings = runtime_config.mcp if runtime_config else None
    if runtime_mcp_settings and runtime_mcp_settings.providers:
        return MCPRuntimeConfig.model_validate(
            {
                "include_local_listings": (
                    True
                    if runtime_mcp_settings.include_local_listings is None
                    else runtime_mcp_settings.include_local_listings
                ),
                "providers": runtime_mcp_settings.providers,
            }
        )

    runtime_config_path = runtime_mcp_settings.config_path if runtime_mcp_settings else None
    default_path = project_root / "config" / "mcp_connectors.json"

    config_path: Path | None = None
    if explicit_path:
        config_path = Path(explicit_path)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        if not config_path.exists():
            raise FileNotFoundError(f"AGENT_MCP_CONFIG_PATH points to missing file: {config_path}")
    elif runtime_config_path:
        config_path = Path(runtime_config_path)
        if not config_path.is_absolute():
            config_path = project_root / config_path
        if not config_path.exists():
            raise FileNotFoundError(
                f"mcp.config_path in agent runtime config points to missing file: {config_path}"
            )
    elif default_path.exists():
        config_path = default_path

    if config_path is None:
        return None
    return MCPRuntimeConfig.model_validate(json.loads(config_path.read_text(encoding="utf-8")))


def build_listing_data_tools(base_tools: RelocationToolsProtocol | None = None) -> RelocationToolsProtocol:
    local_tools = base_tools or RelocationDBTools()
    if isinstance(local_tools, CompositeRelocationDBTools):
        return local_tools
    runtime_config = load_mcp_runtime_config()
    if runtime_config is None:
        return local_tools

    providers = [
        MCPRentalListingProvider(config=provider_config)
        for provider_config in runtime_config.providers
        if provider_config.enabled
    ]
    if not providers:
        return local_tools

    return CompositeRelocationDBTools(
        local_db=local_tools,
        external_providers=providers,
        include_local_listings=runtime_config.include_local_listings,
    )


def _extract_tool_payload(result: Any) -> Any:
    structured = getattr(result, "structuredContent", None)
    if structured not in (None, {}, []):
        return structured

    parsed_items: list[Any] = []
    for content in getattr(result, "content", []):
        text = getattr(content, "text", None)
        if text is not None:
            parsed_items.append(_parse_jsonish(text))
            continue

        resource = getattr(content, "resource", None)
        resource_text = getattr(resource, "text", None)
        if resource_text is not None:
            parsed_items.append(_parse_jsonish(resource_text))

    if not parsed_items:
        return None
    if len(parsed_items) == 1:
        return parsed_items[0]
    return parsed_items


def _parse_jsonish(raw: str) -> Any:
    text = raw.strip()
    if not text:
        return ""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _schema_properties(input_schema: dict[str, Any]) -> list[str]:
    properties = input_schema.get("properties", {})
    if isinstance(properties, dict):
        return [key for key in properties if isinstance(key, str)]
    return []


def _resolve_binding_value(payload: Any, binding: str | SearchArgumentBinding) -> Any:
    if isinstance(binding, str):
        binding = SearchArgumentBinding(field=binding)

    value = getattr(payload, binding.field, None)
    if value is None:
        return None
    if binding.transform == "iso_date" and isinstance(value, date):
        return value.isoformat()
    if binding.transform == "positive_to_bool":
        return bool(value and value > 0)
    if binding.transform == "bool":
        return bool(value)
    if binding.transform == "rooms_array":
        rooms = int(value)
        return [str(rooms)] if rooms > 0 else None
    return value


def _coerce_argument_value_for_schema(value: Any, schema: dict[str, Any]) -> Any:
    schema_type = schema.get("type")
    if value is None:
        return None
    if schema_type == "integer":
        coerced = _to_int(value)
        return coerced if coerced is not None else value
    if schema_type == "number":
        coerced = _to_float(value)
        return coerced if coerced is not None else value
    if schema_type == "boolean":
        coerced = _coerce_bool(value)
        return coerced if coerced is not None else value
    return value


def _normalize_tool_name(value: str) -> str:
    normalized = value.strip().lower().replace("/", "-")
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"-{2,}", "-", normalized).strip("-")
    return normalized


def _semantic_argument_already_present(arguments: dict[str, Any], property_name: str) -> bool:
    tokens = set(_property_tokens(property_name))
    room_like = bool(tokens.intersection({"rooms", "room", "bedroom", "bedrooms"}))
    location_like = bool(tokens.intersection({"city", "location", "settlement", "region", "geo"}))
    country_like = "country" in tokens
    price_like = bool(tokens.intersection({"price", "rent", "budget"})) and bool(
        tokens.intersection({"max", "upper", "budget", "limit", "min", "from", "to"})
    )

    for existing_name in arguments:
        existing_tokens = set(_property_tokens(existing_name))
        if room_like and existing_tokens.intersection({"rooms", "room", "bedroom", "bedrooms"}):
            return True
        if location_like and existing_tokens.intersection({"city", "location", "settlement", "region", "geo"}):
            return True
        if country_like and "country" in existing_tokens:
            return True
        if price_like and existing_tokens.intersection({"price", "rent", "budget"}):
            return True
    return False


def _guess_search_argument(property_name: str, payload: SearchListingsInput, default_country: str | None) -> Any:
    tokens = set(_property_tokens(property_name))
    lowered_name = property_name.lower()

    if tokens.intersection({"city", "location", "settlement", "region", "geo"}):
        return payload.city
    if "country" in tokens:
        return default_country
    if tokens.intersection({"price", "rent", "budget"}) and tokens.intersection({"max", "upper", "budget", "limit", "to"}):
        return payload.monthly_budget
    if tokens.intersection({"rooms", "room", "bedroom", "bedrooms"}):
        return payload.rooms_min
    if tokens.intersection({"furnished", "furniture"}):
        return payload.furnished
    if tokens.intersection({"pet", "pets"}):
        return True if payload.pet_count > 0 else None
    if "commute" in tokens:
        return payload.max_commute_minutes
    if "short" in tokens and "term" in tokens:
        return True if payload.include_short_term else None
    if payload.move_in_date is not None and (
        "available" in tokens
        or "availability" in tokens
        or "move" in tokens
        or lowered_name in {"availablefrom", "availableat", "moveindate", "startdate"}
        or lowered_name.endswith("date")
    ):
        return payload.move_in_date.isoformat()
    return None


def _property_tokens(value: str) -> list[str]:
    normalized = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value)
    return [token for token in re.split(r"[^a-z0-9]+", normalized.lower()) if token]


def _resolve_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def _extract_from_record(record: dict[str, Any], aliases: list[str]) -> Any:
    for alias in aliases:
        direct = _resolve_path(record, alias)
        if direct not in (None, ""):
            return direct

    wanted = {alias.lower() for alias in aliases}
    queue: list[Any] = [record]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            for key, value in current.items():
                if str(key).lower() in wanted and value not in (None, ""):
                    return value
                if isinstance(value, (dict, list)):
                    queue.append(value)
        elif isinstance(current, list):
            queue.extend(item for item in current if isinstance(item, (dict, list)))
    return None


def _to_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    return str(value)


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = re.sub(r"[^\d,.\-]", "", value).replace(",", ".")
        if cleaned.count(".") > 1:
            head, _, tail = cleaned.partition(".")
            cleaned = head + "." + tail.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _to_int(value: Any) -> int | None:
    number = _to_float(value)
    return int(number) if number is not None else None


def _coerce_bool(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "да"}:
            return True
        if lowered in {"false", "0", "no", "n", "нет"}:
            return False
    return None


def _to_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        for parser in (date.fromisoformat, datetime.fromisoformat):
            try:
                parsed = parser(stripped)
                return parsed if isinstance(parsed, date) and not isinstance(parsed, datetime) else parsed.date()
            except ValueError:
                continue
    return None


def _infer_rooms_from_text(text: str) -> int | None:
    lowered = text.lower()
    if "студ" in lowered or "studio" in lowered:
        return 1

    match = re.search(r"(\d+)\s*[- ]?\s*(комн|к\.|room)", lowered)
    if match:
        return int(match.group(1))
    return None


def _infer_area_from_text(text: str) -> float | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*м²", text.lower())
    if not match:
        match = re.search(r"(\d+(?:[.,]\d+)?)\s*sqm", text.lower())
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _normalize_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    return [str(value)]
