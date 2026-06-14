from __future__ import annotations

from src.tools.calculations import CalculationTools, CompareListingsInput, EstimateUpfrontCostInput, ScoreListingInput
from src.tools.relocation_db import RelocationDBTools


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install `mcp` to run this server.") from exc

    calc = CalculationTools(RelocationDBTools())
    server = FastMCP("mcp-calculations")

    @server.tool()
    def estimate_upfront_cost(listing_id: str):
        return calc.estimate_upfront_cost(EstimateUpfrontCostInput(listing_id=listing_id))

    @server.tool()
    def score_listing(listing_id: str, requirements: dict):
        return calc.score_listing(ScoreListingInput(listing_id=listing_id, requirements=requirements))

    @server.tool()
    def compare_listings(listing_ids: list[str], requirements: dict):
        return calc.compare_listings(CompareListingsInput(listing_ids=listing_ids, requirements=requirements))

    return server


if __name__ == "__main__":  # pragma: no cover - optional runtime
    build_server().run()
