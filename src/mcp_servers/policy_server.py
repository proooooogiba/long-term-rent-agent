from __future__ import annotations

from src.tools.policy_search import PolicySearchInput, PolicySearchTool


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("Install `mcp` to run this server.") from exc

    tool = PolicySearchTool()
    server = FastMCP("mcp-rental-policy")

    @server.tool()
    def search_policy_docs(query: str, top_k: int = 5):
        return tool.search_policy_docs(PolicySearchInput(query=query, top_k=top_k))

    return server


if __name__ == "__main__":  # pragma: no cover - optional runtime
    build_server().run()
