from __future__ import annotations

from pathlib import Path


def _candidate_paths(working_dir: Path, item: str) -> list[Path]:
    raw = Path(item)
    candidates = []
    if raw.is_absolute():
        candidates.append(raw)
    else:
        candidates.extend(
            [
                working_dir / item,
                working_dir / f"{item}.md",
                working_dir / "skills" / item,
                working_dir / "skills" / f"{item}.md",
                working_dir / "skills" / item / "SKILL.md",
            ]
        )
    return candidates


def compile_skill_prelude(skills: list[str], working_dir: Path) -> str:
    if not skills:
        return ""
    sections: list[str] = []
    unresolved: list[str] = []
    for item in skills:
        found = next((path for path in _candidate_paths(working_dir, item) if path.exists()), None)
        if found is None:
            unresolved.append(item)
            continue
        sections.append(f"Skill `{item}` from {found}:\n{found.read_text(encoding='utf-8').strip()}")
    if unresolved:
        sections.append("Named skills without local payloads: " + ", ".join(unresolved))
    return "\n\n".join(sections)
