"""Hermes Organization Layer plugin.

Keeps a Hermes workspace tidy and findable: a canonical cross-platform folder layout,
a generated INDEX.md + index.json, per-entry metadata, and a stale/scratch hygiene policy.

Usage (slash):  /org init | index | new <kind> <name> [purpose...] | find <q> | status
                | prune [--apply] | config | help
Tools:          org_init, org_index, org_new, org_find, org_status, org_prune
"""

from __future__ import annotations

from .orgcore import actions, config

HELP = (
    "**Organization Layer Commands**\n"
    "  `/org init [workspace]`              - create the workspace scaffold + config\n"
    "  `/org index`                         - regenerate INDEX.md + index.json\n"
    "  `/org new <kind> <name> [purpose...]`- create a managed entry (.org.json stub)\n"
    "  `/org find <query>`                  - search the index by name/purpose/tag\n"
    "  `/org status`                        - overview + stale/expired flags\n"
    "  `/org prune [--apply]`               - dry-run (default) or archive stale/expired\n"
    "  `/org config`                        - show resolved config\n"
    "  `/org help`                          - this message\n"
    "\nKinds: projects, test-scripts, scratch, data, notes, docs, assets.\n"
    "Overrides: HERMES_ORG_WORKSPACE or the config at <workspace>/.org/config.json."
)


def _folders() -> list[str]:
    try:
        return config.load_config(config.default_workspace_root())["folders"]
    except Exception:
        return config.DEFAULT_FOLDERS


def _handle_slash(raw_args: str) -> str:
    args = (raw_args or "").strip().split()
    cmd = args[0].lower() if args else "help"
    rest = " ".join(args[1:]) if len(args) > 1 else ""

    if cmd in ("init", "setup", "bootstrap"):
        return actions._fmt(*actions.cmd_init(rest or None))
    if cmd in ("index", "update", "scan"):
        return actions._fmt(*actions.cmd_index())
    if cmd in ("new", "add", "create"):
        parts = rest.split()
        if len(parts) < 2:
            return "Usage: /org new <kind> <name> [purpose...]\nKinds: " + ", ".join(_folders())
        return actions._fmt(*actions.cmd_new(parts[0], parts[1], " ".join(parts[2:])))
    if cmd in ("find", "search", "where"):
        return actions._fmt(*actions.cmd_find(rest))
    if cmd in ("status", "ls", "list", "stats"):
        return actions._fmt(*actions.cmd_status())
    if cmd in ("prune", "gc"):
        return actions._fmt(*actions.cmd_prune(apply="--apply" in args[1:]))
    if cmd in ("config", "show"):
        return actions._fmt(*actions.cmd_show_config())
    if cmd in ("help", "?"):
        return HELP
    return "Unknown subcommand. " + HELP


# ── Agent tool handlers ────────────────────────────────────────────

def _t_init(args: dict) -> str:
    return actions._fmt(*actions.cmd_init(args.get("workspace")))


def _t_index(args: dict) -> str:
    return actions._fmt(*actions.cmd_index())


def _t_new(args: dict) -> str:
    return actions._fmt(*actions.cmd_new(
        args.get("kind", ""), args.get("name", ""),
        args.get("purpose", ""), args.get("tags")))


def _t_find(args: dict) -> str:
    return actions._fmt(*actions.cmd_find(args.get("query", "")))


def _t_status(args: dict) -> str:
    return actions._fmt(*actions.cmd_status())


def _t_prune(args: dict) -> str:
    return actions._fmt(*actions.cmd_prune(apply=bool(args.get("apply", False))))


_TOOL_SPECS = [
    ("org_init", "Scaffold the org workspace (creates the platform-default or a given directory + config).",
     {"type": "object", "properties": {"workspace": {"type": "string", "description": "Optional absolute workspace path (else the platform default)."}}, "additionalProperties": False}),
    ("org_index", "Regenerate INDEX.md and index.json for the org workspace.", {"type": "object", "properties": {}}),
    ("org_new", "Create a managed entry (folder + .org.json stub) under a given kind (projects/test-scripts/scratch/data/notes/docs/assets).",
     {"type": "object", "properties": {"kind": {"type": "string"}, "name": {"type": "string"},
                                       "purpose": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
      "required": ["kind", "name"], "additionalProperties": False}),
    ("org_find", "Find workspace entries by name, purpose, or tag. Returns a matching hit list.",
     {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}),
    ("org_status", "Show workspace summary plus stale/expired flags.",
     {"type": "object", "properties": {}}),
    ("org_prune", "Hygiene: with apply=false (default) lists archive candidates; with apply=true moves stale/expired entries to _archive/.",
     {"type": "object", "properties": {"apply": {"type": "boolean", "description": "Set true to actually archive candidates."}}, "additionalProperties": False}),
]

_HANDLERS = {"org_init": _t_init, "org_index": _t_index, "org_new": _t_new,
             "org_find": _t_find, "org_status": _t_status, "org_prune": _t_prune}


def register(ctx) -> None:
    """Hermes entry point: register the /org command and the org_* agent tools."""
    ctx.register_command(
        "org",
        handler=_handle_slash,
        description="Hermes organization layer: workspace scaffold, index, find, hygiene.",
        args_hint="<init|index|new|find|status|prune|help>",
    )
    for name, descr, schema in _TOOL_SPECS:
        try:
            ctx.register_tool(
                name=name,
                toolset="org",
                schema=schema,
                handler=_HANDLERS[name],
                description=descr,
                is_async=False,
                emoji="🗂",
            )
        except Exception as e:  # tool registration must not block the plugin
            try:
                if hasattr(ctx, "logger"):
                    ctx.logger.error("org tool %s failed to register: %s", name, e)
            except Exception:
                pass