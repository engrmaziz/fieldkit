"""Jinja2 prompt template loader and renderer with mandatory version headers.

Conventions:
- Prompts live in packages/*/prompts/*.jinja with a version header.
- Never use inline strings for prompts.
- Version header format: {# version: 1.0.0 #}
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2

VERSION_HEADER_PATTERN = re.compile(r"\{#\s*version\s*[:=]\s*([^\s#]+)\s*#\}", re.IGNORECASE)


class PromptVersionError(ValueError):
    """Raised when a prompt template is missing a required version header."""


@dataclass(frozen=True)
class RenderedPrompt:
    """Rendered prompt with extracted version and template metadata."""

    text: str
    version: str
    template_path: Path


def load_and_render_prompt(
    template_path: str | Path,
    **kwargs: Any,
) -> RenderedPrompt:
    """Load a Jinja2 template file, validate its version header, and render it.

    Args:
        template_path: Path to the .jinja prompt template.
        **kwargs: Variables passed to the Jinja template.

    Returns:
        RenderedPrompt containing the rendered text, template version, and path.

    Raises:
        FileNotFoundError: If the template file does not exist.
        PromptVersionError: If the template is missing a valid `{# version: ... #}` header.
    """
    path = Path(template_path)
    if not path.is_file():
        raise FileNotFoundError(f"Prompt template file not found: {path}")

    raw_content = path.read_text(encoding="utf-8")

    match = VERSION_HEADER_PATTERN.search(raw_content)
    if not match:
        raise PromptVersionError(
            f"Prompt template '{path.name}' is missing a required version header. "
            "Add '{# version: <semver> #}' at the top of the file."
        )

    version = match.group(1).strip()

    template = jinja2.Template(raw_content)
    rendered_text = template.render(**kwargs).strip()

    return RenderedPrompt(
        text=rendered_text,
        version=version,
        template_path=path,
    )
