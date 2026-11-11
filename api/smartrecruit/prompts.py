"""Load versioned prompts from prompts/<agent>/<version>.md.

Each file holds a metadata header, then '## System' and '## User' blocks.
The user block may contain {placeholders} filled at run time.
"""
import re

from . import config


def load(agent: str, version: str | None = None) -> tuple[str, str]:
    version = version or config.PROMPT_VERSIONS[agent]
    text = (config.PROMPTS_DIR / agent / f"{version}.md").read_text(encoding="utf-8")
    system = re.search(r"^## System\s*\n(.*?)(?=^## User)", text, re.S | re.M)
    user = re.search(r"^## User\s*\n(.*)", text, re.S | re.M)
    if not system or not user:
        raise ValueError(f"Prompt {agent}/{version} needs '## System' and '## User' sections")
    return system.group(1).strip(), user.group(1).strip()


def render(template: str, **values) -> str:
    # str.format would choke on the JSON braces in the prompts, so replace only known keys
    for key, value in values.items():
        template = template.replace("{" + key + "}", str(value))
    return template
