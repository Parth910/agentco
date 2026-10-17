"""Which tools each role may use. Patterns support wildcards, e.g. "board_*".

These are the defaults; team config files will be able to override them (M9).
"""

import re
from fnmatch import fnmatchcase

READ_BOARD = ["board_list_tickets", "board_get_ticket"]
WORK_ON_TICKETS = [*READ_BOARD, "board_update_ticket", "board_comment"]
READ_DOCS = ["docs_list", "docs_read"]

ROLE_TOOLS: dict[str, list[str]] = {
    "researcher": [*READ_BOARD, "docs_*", "chat_*"],
    "pm": ["board_*", "docs_*", "chat_*"],
    "program_manager": ["board_*", *READ_DOCS, "chat_*"],
    "engineer": [*WORK_ON_TICKETS, *READ_DOCS, "chat_*"],
    "qa": [*WORK_ON_TICKETS, *READ_DOCS, "chat_*"],
}


def role_type(role_id: str) -> str:
    """'engineer_2' -> 'engineer' (numbered copies share a role's permissions)."""
    return re.sub(r"_\d+$", "", role_id)


def tools_for_role(role_id: str) -> list[str]:
    """Default tool patterns for a role. Unknown roles get no tools."""
    return ROLE_TOOLS.get(role_type(role_id), [])


def is_allowed(tool_name: str, patterns: list[str]) -> bool:
    return any(fnmatchcase(tool_name, pattern) for pattern in patterns)
