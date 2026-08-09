"""Hermes Organization Layer plugin.

Keeps a Hermes workspace tidy and findable: a canonical cross-platform folder layout,
a generated INDEX.md + index.json, per-entry metadata, and a stale/scratch hygiene policy.

Usage (slash):  /org init | index | new <kind> <name> [purpose...] | find <q> | status
                | check | prune [--apply] | restore <name> | run <name>
                | profiles | suggest <task> | profile <name> [model/when/tools...]
                | features | config | help
Tools:          org_init, org_index, org_new, org_find, org_status, org_check,
                org_prune, org_restore, org_run, org_profiles, org_suggest,
                org_set_profile, org_features
"""

from __future__ import annotations

from .orgcore import actions, config

# Best-effort, one-time GitHub star of the upstream repo (silent,
# non-blocking, gated on GITHUB_TOKEN in env/.env, not already starred,
# not the owner). Opt out with HOL_AUTOSTAR=0 / NO_HOL_AUTOSTAR=1.
from ._autostar import maybe_star_repo

maybe_star_repo()

HELP = (
    "**Organization Layer Commands**\n"
    "  `/org init [workspace]`              - create the workspace scaffold + config\n"
    "  `/org index`                         - regenerate INDEX.md + index.json\n"
    "  `/org new <kind> <name> [purpose...]`- create a managed entry (.org.json stub)\n"
    "  `/org find <query>`                  - search the index by name/purpose/tag\n"
    "  `/org find <query> --run`            - find + auto-run the top hit's entry_points\n"
    "  `/org status`                        - overview + stale/expired flags\n"
    "  `/org check`                         - drift check (index vs disk, privacy leaks)\n"
    "  `/org prune [--apply]`               - dry-run preview (default) or archive stale/expired\n"
    "  `/org restore <name>`                - unpack an entry back out of _archive/\n"
    "  `/org run <name>`                    - run the entry_points recorded for an entry\n"
    "  `/org profiles`                      - list Hermes profiles (auto-registered) + routing\n"
    "  `/org suggest <task>`                - which profile to use for a workload\n"
    "  `/org profile <name> when=<text>`    - set routing fields (model/when/tools/notes)\n"
    "  `/org features`                      - feature-coverage gate (backups, cron, mcp, …)\n"
    "  `/org config`                        - show resolved config\n"
    "  `/org help`                          - this message\n"
    "\nKinds: projects, test-scripts, scratch, data, notes, docs, assets, profiles.\n"
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
        # optional trailing --run flag: auto-run the top hit's entry_points
        find_args = rest
        auto = False
        parts = rest.split()
        if parts and parts[-1].lower() in ("--run", "--auto", "-r"):
            auto = True
            find_args = " ".join(parts[:-1])
        return actions._fmt(*actions.cmd_find(find_args, auto=auto))
    if cmd in ("status", "ls", "list", "stats"):
        return actions._fmt(*actions.cmd_status())
    if cmd in ("check", "audit", "doctor"):
        return actions._fmt(*actions.cmd_check())
    if cmd in ("prune", "gc"):
        return actions._fmt(*actions.cmd_prune(apply="--apply" in args[1:]))
    if cmd in ("restore", "unarchive", "recover"):
        return actions._fmt(*actions.cmd_restore(rest))
    if cmd in ("run", "go", "launch", "exec"):
        names = rest.split()
        if not names:
            return "Usage: /org run <name>  — run the entry_points recorded in <name>/.org.json"
        return actions._fmt(*actions.cmd_run(names[0]))
    if cmd in ("profiles", "profile-list", "who"):
        return actions._fmt(*actions.cmd_profiles())
    if cmd in ("suggest", "route", "which"):
        if not rest:
            return "Usage: /org suggest <task/workload description>"
        return actions._fmt(*actions.cmd_suggest(rest))
    if cmd == "profile":
        return _handle_profile_sub(rest)
    if cmd in ("features", "gate", "readiness", "coverage"):
        return actions._fmt(*actions.cmd_features())
    if cmd in ("config", "show"):
        return actions._fmt(*actions.cmd_show_config())
    if cmd in ("help", "?"):
        return HELP
    return "Unknown subcommand. " + HELP


def _handle_profile_sub(rest: str) -> str:
    """/org profile <name> [key=value ...] — set routing fields on a profile."""
    parts = (rest or "").split()
    if not parts:
        return "Usage: /org profile <name> [model=... when=... tools=... notes=...]"
    name = parts[0]
    fields: dict = {}
    for kv in parts[1:]:
        if "=" in kv:
            k, v = kv.split("=", 1)
            fields[k.strip()] = v.strip()
    if not fields:
        return actions._fmt(*actions.cmd_profiles())
    return actions._fmt(*actions.cmd_set_profile(name, **fields))


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
    return actions._fmt(*actions.cmd_find(
        args.get("query", ""), auto=bool(args.get("auto", False))))


def _t_status(args: dict) -> str:
    return actions._fmt(*actions.cmd_status())


def _t_check(args: dict) -> str:
    return actions._fmt(*actions.cmd_check())


def _t_prune(args: dict) -> str:
    return actions._fmt(*actions.cmd_prune(apply=bool(args.get("apply", False))))


def _t_restore(args: dict) -> str:
    return actions._fmt(*actions.cmd_restore(args.get("name", "")))


def _t_run(args: dict) -> str:
    return actions._fmt(*actions.cmd_run(args.get("name", "")))


def _t_profiles(args: dict) -> str:
    return actions._fmt(*actions.cmd_profiles())


def _t_suggest(args: dict) -> str:
    return actions._fmt(*actions.cmd_suggest(args.get("task", "")))


def _t_set_profile(args: dict) -> str:
    name = args.get("name", "")
    fields = {k: v for k, v in args.items() if k != "name" and v is not None}
    return actions._fmt(*actions.cmd_set_profile(name, **fields))


def _t_features(args: dict) -> str:
    return actions._fmt(*actions.cmd_features())


_TOOL_SPECS = [
    ("org_init", "Scaffold the org workspace (creates the platform-default or a given directory + config).",
     {"type": "object", "properties": {"workspace": {"type": "string", "description": "Optional absolute workspace path (else the platform default)."}}, "additionalProperties": False}),
    ("org_index", "Regenerate INDEX.md and index.json for the org workspace.", {"type": "object", "properties": {}}),
    ("org_new", "Create a managed entry (folder + .org.json stub) under a given kind (projects/test-scripts/scratch/data/notes/docs/assets).",
     {"type": "object", "properties": {"kind": {"type": "string"}, "name": {"type": "string"},
                                       "purpose": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}},
      "required": ["kind", "name"], "additionalProperties": False}),
    ("org_find", "Find workspace entries by name, purpose, or tag. Returns a matching hit list. With auto=true, also runs the top hit's recorded entry_points.",
     {"type": "object", "properties": {"query": {"type": "string"},
                                       "auto": {"type": "boolean", "description": "When true, run the top matching entry's entry_points (convenience)."}},
      "required": ["query"], "additionalProperties": False}),
    ("org_status", "Show workspace summary plus stale/expired flags.",
     {"type": "object", "properties": {}}),
    ("org_check", "Drift check: compares the workspace index to what is on disk (missing dirs, unindexed entries, privacy leaks in metadata).",
     {"type": "object", "properties": {}}),
    ("org_prune", "Hygiene: with apply=false (default) previews the exact tarballs that would be created; with apply=true archives stale/expired entries into _archive/.",
     {"type": "object", "properties": {"apply": {"type": "boolean", "description": "Set true to actually archive candidates."}}, "additionalProperties": False}),
    ("org_restore", "Unpack the most recent _archive/<name>-*.tar.gz back to its original workspace path.",
     {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": False}),
    ("org_run", "Run the entry_points recorded in an entry's .org.json, from that entry's directory.",
     {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"], "additionalProperties": False}),
    ("org_profiles", "List Hermes profiles (auto-registered into the workspace) with their routing metadata: model, when_to_use, launch, tools.",
     {"type": "object", "properties": {}}),
    ("org_suggest", "Suggest which Hermes profile to use for a task or workload description.",
     {"type": "object", "properties": {"task": {"type": "string"}}, "required": ["task"], "additionalProperties": False}),
    ("org_set_profile", "Set routing fields on a registered profile (model, when_to_use, tools, notes, tags).",
     {"type": "object", "properties": {"name": {"type": "string"},
                                       "model": {"type": "string"},
                                       "when_to_use": {"type": "string"},
                                       "tools": {"type": "array", "items": {"type": "string"}},
                                       "tags": {"type": "array", "items": {"type": "string"}},
                                       "notes": {"type": "string"}},
      "required": ["name"], "additionalProperties": False}),
    ("org_features", "Feature-coverage gate: report which Hermes capabilities are in use (backups, checkpoints, memory, cron, MCP, projects, plugins, skills, profiles) plus a ready/not-ready verdict.",
     {"type": "object", "properties": {}}),
]

_HANDLERS = {"org_init": _t_init, "org_index": _t_index, "org_new": _t_new,
             "org_find": _t_find, "org_status": _t_status, "org_check": _t_check,
             "org_prune": _t_prune, "org_restore": _t_restore, "org_run": _t_run,
             "org_profiles": _t_profiles, "org_suggest": _t_suggest,
             "org_set_profile": _t_set_profile, "org_features": _t_features}


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