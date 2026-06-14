from __future__ import annotations

from pathlib import Path

from src.agent.state import PolicyChunk


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_DOCS_DIR = ROOT_DIR / "data" / "documents"


def _split_long_text(text: str, chunk_size: int) -> list[str]:
    clean = text.strip()
    if len(clean) <= chunk_size:
        return [clean]

    paragraphs = [part.strip() for part in clean.split("\n\n") if part.strip()]
    if not paragraphs:
        return [clean]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0
    for paragraph in paragraphs:
        addition = len(paragraph) + (2 if current else 0)
        if current and current_len + addition > chunk_size:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
            continue
        current.append(paragraph)
        current_len += addition

    if current:
        chunks.append("\n\n".join(current))
    return chunks


def load_policy_chunks(documents_dir: Path = DEFAULT_DOCS_DIR, chunk_size: int = 800) -> list[PolicyChunk]:
    chunks: list[PolicyChunk] = []

    for path in sorted(documents_dir.glob("*.md")):
        current_heading = path.stem
        buffer: list[str] = []
        lines = path.read_text(encoding="utf-8").splitlines()

        def flush() -> None:
            text = "\n".join(buffer).strip()
            if not text:
                return
            for piece in _split_long_text(text, chunk_size=chunk_size):
                chunks.append(
                    PolicyChunk(
                        source=path.name,
                        heading=current_heading,
                        text=piece,
                    )
                )

        for line in lines:
            if line.startswith("#"):
                flush()
                buffer = []
                current_heading = line.lstrip("# ").strip() or path.stem
                continue
            buffer.append(line)

        flush()

    return chunks
