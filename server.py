"""
Forge UE5 Dev Agent — MCP Server v1.1.1
Diagnosis + lazy knowledge loading + session memory + memory-safe I/O.

No files need to be uploaded to Claude Projects.
Knowledge files are loaded on-demand by the server.

Requirements:
    pip install mcp httpx

Setup:
    1. Clone: git clone https://github.com/your-username/forge-ue5
    2. Install: pip install mcp httpx
    3. Enable Remote Control API in UE5 (Edit -> Plugins -> Remote Control API -> Enable -> Restart)
    4. Add to Claude Desktop config (%APPDATA%/Claude/claude_desktop_config.json on Windows):
       {
         "mcpServers": {
           "forge-ue5": {
             "command": "python",
             "args": ["C:/forge-ue5/server.py"],
             "env": {
               "UE_PROJECT_PATH": "C:/MyUE5Project"
             }
           }
         }
       }
    5. Restart Claude Desktop

Token usage: ~5K base + ~5K per knowledge module loaded on demand.
No Claude Projects file uploads needed.
"""

import asyncio
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from collections import deque  # Memory-safe tail reading for large log files

import httpx
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ─── CONFIG ──────────────────────────────────────────────────────────────────

UE_HOST = os.environ.get("UE_HOST", "localhost")
UE_PORT = int(os.environ.get("UE_PORT", "30010"))
UE_BASE = f"http://{UE_HOST}:{UE_PORT}"
UE_PROJECT_PATH = os.environ.get("UE_PROJECT_PATH", "")

app = Server("forge-ue5")

# ─── KNOWLEDGE MAP ────────────────────────────────────────────────────────────

KNOWLEDGE_MAP = {
    "gas":             "UE5_GAS_ErrorGuide_v1.0.md",
    "ability":         "UE5_GAS_ErrorGuide_v1.0.md",
    "multiplayer":     "UE5_Multiplayer_Knowledge_v1.0.md",
    "network":         "UE5_Multiplayer_Knowledge_v1.0.md",
    "replication":     "UE5_Multiplayer_Knowledge_v1.0.md",
    "security":        "UE5_Multiplayer_Security_Guide_v1.0.md",
    "rpc":             "UE5_Multiplayer_Security_Guide_v1.0.md",
    "vehicle":         "UE5_ChaosVehicles_Guide_v1.0.md",
    "chaos":           "UE5_ChaosVehicles_Guide_v1.0.md",
    "save":            "UE5_SaveLoad_Guide_v1.0.md",
    "savegame":        "UE5_SaveLoad_Guide_v1.0.md",
    "animation":       "UE5_Animation_IK_MotionMatching_Guide_v1.0.md",
    "ik":              "UE5_Animation_IK_MotionMatching_Guide_v1.0.md",
    "motion_matching": "UE5_Animation_IK_MotionMatching_Guide_v1.0.md",
    "blueprint":       "UE5_Blueprint_CPP_Bridge_v1.0.md",
    "architecture":    "UE5_Architecture_Guide_v1.0.md",
    "subsystem":       "UE5_Architecture_Guide_v1.0.md",
    "devenv":          "UE5_DevEnv_Setup_Guide_v1.0.md",
    "intellisense":    "UE5_DevEnv_Setup_Guide_v1.0.md",
    "hot_reload":      "UE5_DevEnv_Setup_Guide_v1.0.md",
    "lumen":           "UE5_Lumen_Knowledge_v1.0.md",
    "nanite":          "UE5_Lumen_Knowledge_v1.0.md",
    "rendering":       "UE5_RenderPipeline_PCG_Guide_v1.0.md",
    "pcg":             "UE5_RenderPipeline_PCG_Guide_v1.0.md",
    "material":        "UE5_Material_Shader_Guide_v1.0.md",
    "shader":          "UE5_Material_Shader_Guide_v1.0.md",
    "world_partition": "UE5_WorldPartition_Guide_v1.0.md",
    "streaming":       "UE5_WorldPartition_Guide_v1.0.md",
    "audio":           "UE5_Audio_MetaSounds_Guide_v1.0.md",
    "metasounds":      "UE5_Audio_MetaSounds_Guide_v1.0.md",
    "plugin":          "UE5_PluginDev_Guide_v1.0.md",
    "threading":       "UE5_Threading_Performance_Knowledge_v1.0.md",
    "performance":     "UE5_Threading_Performance_Knowledge_v1.0.md",
    "null_pointer":    "UE5_NullPointer_Knowledge_v1.0.md",
    "crash":           "UE5_NullPointer_Knowledge_v1.0.md",
    "patterns":        "UE5_Patterns_Knowledge_v1.0.md",
    "versions":        "UE5_Versions_Knowledge_v1.0.md",
    "migration":       "UE5_Versions_Knowledge_v1.0.md",
    "ai":              "UE5_AI_BehaviorTree_Guide_v1.0.md",
    "behavior_tree":   "UE5_AI_BehaviorTree_Guide_v1.0.md",
    "errors":          "UE5_DevAgent_HataVeri_v1.0.md",
    "input":           "UE5_EnhancedInput_Guide_v1.0.md",
    "enhanced_input":  "UE5_EnhancedInput_Guide_v1.0.md",
    "ui":              "UE5_UMG_UI_Guide_v1.0.md",
    "umg":             "UE5_UMG_UI_Guide_v1.0.md",
    "widget":          "UE5_UMG_UI_Guide_v1.0.md",
    "packaging":       "UE5_Packaging_Cook_Guide_v1.0.md",
    "cook":            "UE5_Packaging_Cook_Guide_v1.0.md",
    "online":          "UE5_OnlineSubsystem_Guide_v1.0.md",
    "steam":           "UE5_OnlineSubsystem_Guide_v1.0.md",
    "eos":             "UE5_OnlineSubsystem_Guide_v1.0.md",
    "error_handbook":  "UE5_ErrorHandbook_v2.0.md",
    "community":       "UE5_Community_Debug_Guide_v1.0.md",
    "error_frequency": "UE5_ErrorFrequency_ProactiveGuide_v1.0.md",
    "proactive":       "UE5_ErrorFrequency_ProactiveGuide_v1.0.md",
}

def get_knowledge_dir() -> Path:
    return Path(__file__).parent / "knowledge"

# ─── SESSION MEMORY ───────────────────────────────────────────────────────────

SESSION_FILE = Path(__file__).parent / ".forge_session.json"

def load_session() -> dict:
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"findings": [], "patterns": {}, "project": {}, "last_updated": ""}

def save_session(session: dict):
    try:
        session["last_updated"] = datetime.now().isoformat()
        with open(SESSION_FILE, "w", encoding="utf-8") as f:
            json.dump(session, f, indent=2)
    except Exception:
        pass

# ─── HELPERS ─────────────────────────────────────────────────────────────────

async def ue_get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(f"{UE_BASE}{path}", params=params)
        resp.raise_for_status()
        return resp.json()

def find_project_path() -> Optional[Path]:
    if UE_PROJECT_PATH:
        return Path(UE_PROJECT_PATH)
    return None

def get_saved_logs_dir() -> Optional[Path]:
    project = find_project_path()
    if project:
        logs_dir = project / "Saved" / "Logs"
        if logs_dir.exists():
            return logs_dir
    return None

def parse_log_for_errors(log_content: str) -> dict:
    lines = log_content.split("\n")
    fatals, errors, warnings = [], [], []
    for line in lines:
        lower = line.lower()
        if "logcrashhandler" in lower or "fatal error" in lower:
            fatals.append(line.strip())
        elif ": error:" in lower or "compile error" in lower:
            errors.append(line.strip())
        elif ": warning:" in lower and len(warnings) < 20:
            warnings.append(line.strip())
    return {
        "fatal": fatals[:10],
        "errors": errors[:20],
        "warnings": warnings[:20],
        "total_lines": len(lines)
    }

def read_tail(filepath: Path, n: int) -> str:
    """Read last N lines of a file without loading the whole file into memory."""
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        return "".join(deque(f, maxlen=n))

# ─── TOOL DEFINITIONS ────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="read_knowledge",
            description=(
                "Load a Forge knowledge module on demand. "
                "Call this when you need deep knowledge about a specific UE5 topic. "
                "Available topics: gas, multiplayer, security, vehicle, save, animation, "
                "blueprint, architecture, devenv, lumen, rendering, material, world_partition, "
                "audio, plugin, threading, null_pointer, patterns, versions, ai, input, "
                "ui, packaging, online, errors, error_handbook, community."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Topic to load, e.g. 'gas', 'multiplayer', 'vehicle'"
                    }
                },
                "required": ["topic"]
            }
        ),
        Tool(
            name="list_knowledge_topics",
            description="List all available Forge knowledge topics that can be loaded with read_knowledge.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_project_info",
            description="Get UE5 project information: engine version, project name, connection status.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="analyze_output_log",
            description=(
                "Read and analyze the UE5 Output Log. "
                "Returns categorized errors (Fatal/Error/Warning). "
                "Use when the user reports a crash or unexpected behavior."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "last_n_lines": {
                        "type": "integer",
                        "description": "Lines to read from end of log. Default: 500.",
                        "default": 500
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_build_errors",
            description="Get the last C++ build errors (LNK, C2xxx, UHT) from the project logs.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_blueprint_errors",
            description="Get Blueprint compile errors from the current UE5 session log.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_active_plugins",
            description="List all active plugins from the .uproject file.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_cpp_file",
            description="Read a C++ source file from the project for code review.",
            inputSchema={
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path relative to Source/ dir, e.g. 'MyGame/MyCharacter.cpp'"
                    }
                },
                "required": ["file_path"]
            }
        ),
        Tool(
            name="get_crash_dump",
            description="Read the most recent UE5 crash report callstack and error message.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="get_shader_errors",
            description="Get shader compilation errors from the UE5 log.",
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="read_saved_log",
            description="Read a specific saved log file from Saved/Logs directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "log_index": {
                        "type": "integer",
                        "description": "0 = most recent. Default: 0.",
                        "default": 0
                    },
                    "last_n_lines": {
                        "type": "integer",
                        "description": "Lines from end. Default: 200.",
                        "default": 200
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_session_memory",
            description=(
                "Load session memory for this project. "
                "Returns previously found issues and recurring patterns. "
                "Call at the start of a new conversation to get project history."
            ),
            inputSchema={"type": "object", "properties": {}, "required": []}
        ),
        Tool(
            name="save_session_finding",
            description=(
                "Save a finding to session memory. "
                "Call after solving a problem so Forge remembers it for future conversations."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file": {
                        "type": "string",
                        "description": "File where the issue was found, e.g. 'MyCharacter.cpp'"
                    },
                    "issue_type": {
                        "type": "string",
                        "description": "Short category, e.g. 'GAS_InitAbilityActorInfo', 'MissingUPROPERTY'"
                    },
                    "summary": {
                        "type": "string",
                        "description": "One sentence summary of the issue and fix"
                    }
                },
                "required": ["file", "issue_type", "summary"]
            }
        ),
    ]

# ─── TOOL HANDLERS ───────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    # Guard: MCP may pass None instead of empty dict
    arguments = arguments or {}

    # ── read_knowledge ────────────────────────────────────────────────────
    if name == "read_knowledge":
        topic = arguments.get("topic", "").lower().replace(" ", "_").replace("-", "_")

        filename = KNOWLEDGE_MAP.get(topic)
        if not filename:
            for key, val in KNOWLEDGE_MAP.items():
                if topic in key or key in topic:
                    filename = val
                    break

        if not filename:
            return [TextContent(type="text", text=json.dumps({
                "error": f"Unknown topic: '{topic}'",
                "available_topics": sorted(set(KNOWLEDGE_MAP.keys()))
            }, indent=2))]

        file_path = get_knowledge_dir() / filename
        if not file_path.exists():
            return [TextContent(type="text", text=json.dumps({
                "error": f"Knowledge file not found: {filename}",
                "hint": "Make sure the knowledge/ directory exists next to server.py."
            }, indent=2))]

        try:
            return [TextContent(type="text", text=file_path.read_text(encoding="utf-8"))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    # ── list_knowledge_topics ─────────────────────────────────────────────
    elif name == "list_knowledge_topics":
        topics_by_file: dict = {}
        for topic, filename in KNOWLEDGE_MAP.items():
            topics_by_file.setdefault(filename, []).append(topic)
        return [TextContent(type="text", text=json.dumps({
            "usage": "Call read_knowledge(topic) with any topic below",
            "modules": topics_by_file
        }, indent=2))]

    # ── get_session_memory ────────────────────────────────────────────────
    elif name == "get_session_memory":
        session = load_session()
        if not session["findings"] and not session["patterns"]:
            result = {"status": "No session memory yet for this project."}
        else:
            result = {
                "status": "Session memory loaded",
                "last_updated": session.get("last_updated", "unknown"),
                "findings_count": len(session["findings"]),
                "recent_findings": session["findings"][-10:],
                "recurring_patterns": session["patterns"],
                "project": session.get("project", {})
            }
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── save_session_finding ──────────────────────────────────────────────
    elif name == "save_session_finding":
        session = load_session()
        finding = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "file": arguments.get("file", ""),
            "issue_type": arguments.get("issue_type", ""),
            "summary": arguments.get("summary", "")
        }
        session["findings"].append(finding)

        issue_type = finding["issue_type"]
        pattern = session["patterns"].setdefault(issue_type, {"count": 0, "files": []})
        pattern["count"] += 1
        if finding["file"] not in pattern["files"]:
            pattern["files"].append(finding["file"])

        session["findings"] = session["findings"][-50:]  # Keep last 50
        save_session(session)

        result = {"saved": True, "finding": finding}
        if pattern["count"] > 1:
            result["recurring_pattern_detected"] = (
                f"'{issue_type}' has appeared {pattern['count']} times "
                f"in: {', '.join(pattern['files'])}"
            )
        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── get_project_info ──────────────────────────────────────────────────
    elif name == "get_project_info":
        result: dict = {"editor_connected": False}
        try:
            data = await ue_get("/remote/info")
            result.update({
                "editor_connected": True,
                "engine_version": data.get("engineVersion", "Unknown"),
                "project_name": data.get("projectName", "Unknown"),
            })
        except Exception as e:
            result["connection_error"] = str(e)
            result["hint"] = "Check: UE5 open, Remote Control API plugin enabled, editor not paused."

        project = find_project_path()
        result["project_path"] = str(project) if project else "Not set (configure UE_PROJECT_PATH)"

        logs_dir = get_saved_logs_dir()
        if logs_dir:
            log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            result["recent_logs"] = [f.name for f in log_files[:3]]

        if result.get("project_name"):
            session = load_session()
            session["project"]["name"] = result["project_name"]
            session["project"]["engine_version"] = result.get("engine_version", "")
            save_session(session)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── analyze_output_log ────────────────────────────────────────────────
    elif name == "analyze_output_log":
        last_n = arguments.get("last_n_lines", 500)
        log_content = None

        logs_dir = get_saved_logs_dir()
        if logs_dir:
            log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                try:
                    # Memory-safe: reads only last N lines, no full file load
                    log_content = read_tail(log_files[0], last_n)
                except Exception as e:
                    log_content = f"Could not read log: {e}"

        if not log_content:
            log_content = "Log not found. Set UE_PROJECT_PATH environment variable."

        parsed = parse_log_for_errors(log_content)
        return [TextContent(type="text", text=json.dumps({
            "lines_analyzed": parsed["total_lines"],
            "summary": {
                "fatal": len(parsed["fatal"]),
                "errors": len(parsed["errors"]),
                "warnings": len(parsed["warnings"])
            },
            "fatals": parsed["fatal"],
            "errors": parsed["errors"],
            "warnings": parsed["warnings"][:10]
        }, indent=2))]

    # ── get_build_errors ──────────────────────────────────────────────────
    elif name == "get_build_errors":
        build_errors = []
        logs_dir = get_saved_logs_dir()

        if logs_dir:
            log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            for log_file in log_files[:2]:
                try:
                    # Memory-safe: only last 2000 lines to avoid stale old build errors
                    for line in read_tail(log_file, 2000).splitlines():
                        if any(e in line for e in [
                            "LNK2019", "LNK2001", "LNK1120",
                            "error C", "error: ",
                            "UnrealHeaderTool failed",
                            "Cannot open include file",
                            "No such file or directory"
                        ]):
                            build_errors.append(line.strip())
                        if len(build_errors) >= 30:
                            break
                except Exception:
                    continue  # Skip unreadable log files
                if build_errors:
                    break

        return [TextContent(type="text", text=json.dumps({
            "count": len(build_errors),
            "errors": build_errors[:30]
        }, indent=2))]

    # ── get_blueprint_errors ──────────────────────────────────────────────
    elif name == "get_blueprint_errors":
        bp_errors = []
        logs_dir = get_saved_logs_dir()

        if logs_dir:
            log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                try:
                    for line in read_tail(log_files[0], 1000).splitlines():
                        if any(x in line for x in [
                            "LogBlueprint: Error",
                            "LogK2Compiler: Error",
                            "Blueprint compile error"
                        ]):
                            bp_errors.append(line.strip())
                except Exception:
                    pass  # Non-critical, return empty list

        return [TextContent(type="text", text=json.dumps({
            "count": len(bp_errors),
            "errors": bp_errors[:20]
        }, indent=2))]

    # ── get_active_plugins ────────────────────────────────────────────────
    elif name == "get_active_plugins":
        plugins = []
        project = find_project_path()

        if project:
            uproject_files = list(project.glob("*.uproject"))
            if uproject_files:
                try:
                    data = json.loads(uproject_files[0].read_text(encoding="utf-8"))
                    plugins = [
                        p["Name"] for p in data.get("Plugins", [])
                        if p.get("Enabled", False)
                    ]
                except Exception as e:
                    return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

        return [TextContent(type="text", text=json.dumps({
            "count": len(plugins),
            "plugins": plugins
        }, indent=2))]

    # ── get_cpp_file ──────────────────────────────────────────────────────
    elif name == "get_cpp_file":
        file_path = arguments.get("file_path", "")
        resolved = Path(file_path)

        if not resolved.is_absolute():
            project = find_project_path()
            if project:
                candidate = project / "Source" / file_path
                if candidate.exists():
                    resolved = candidate
                else:
                    matches = list(project.glob(f"**/{file_path}"))
                    if matches:
                        resolved = matches[0]

        if resolved.exists():
            try:
                content = resolved.read_text(encoding="utf-8", errors="replace")
                return [TextContent(type="text", text=json.dumps({
                    "file": str(resolved),
                    "line_count": len(content.splitlines()),
                    "content": content
                }, indent=2))]
            except Exception as e:
                return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

        return [TextContent(type="text", text=json.dumps({
            "error": f"File not found: {file_path}",
            "hint": "Use path relative to Source/, e.g. 'MyGame/MyCharacter.cpp'"
        }, indent=2))]

    # ── get_crash_dump ────────────────────────────────────────────────────
    elif name == "get_crash_dump":
        crash_dirs = [
            Path.home() / "AppData" / "Local" / "UnrealEngine" / "Common" / "Crashes",
            Path.home() / "AppData" / "Local" / "Temp" / "UnrealEngine" / "Crashes",
        ]
        project = find_project_path()
        if project:
            crash_dirs.append(project / "Saved" / "Crashes")

        most_recent, most_recent_time = None, 0.0
        for crash_dir in crash_dirs:
            if crash_dir.exists():
                for folder in crash_dir.iterdir():
                    if folder.is_dir():
                        mtime = os.path.getmtime(folder)
                        if mtime > most_recent_time:
                            most_recent_time = mtime
                            most_recent = folder

        if most_recent:
            result: dict = {
                "crash_folder": str(most_recent),
                "timestamp": datetime.fromtimestamp(most_recent_time).isoformat()
            }
            for fname in ["CrashContext.runtime-xml", "UE4Minidump.log"]:
                fpath = most_recent / fname
                if fpath.exists():
                    try:
                        result[fname] = fpath.read_text(encoding="utf-8", errors="replace")[:3000]
                    except Exception:
                        pass  # Non-critical
        else:
            result = {"message": "No crash dumps found."}

        return [TextContent(type="text", text=json.dumps(result, indent=2))]

    # ── get_shader_errors ─────────────────────────────────────────────────
    elif name == "get_shader_errors":
        shader_errors = []
        logs_dir = get_saved_logs_dir()

        if logs_dir:
            log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
            if log_files:
                try:
                    for line in read_tail(log_files[0], 2000).splitlines():
                        if any(x in line for x in [
                            "LogShaderCompilers: Error",
                            "LogMaterial: Error",
                            "Shader compile error"
                        ]):
                            shader_errors.append(line.strip())
                        if len(shader_errors) >= 20:
                            break
                except Exception:
                    pass  # Non-critical

        return [TextContent(type="text", text=json.dumps({
            "count": len(shader_errors),
            "errors": shader_errors
        }, indent=2))]

    # ── read_saved_log ────────────────────────────────────────────────────
    elif name == "read_saved_log":
        log_index = arguments.get("log_index", 0)
        last_n = arguments.get("last_n_lines", 200)

        logs_dir = get_saved_logs_dir()
        if not logs_dir:
            return [TextContent(type="text", text=json.dumps({
                "error": "Log directory not found. Set UE_PROJECT_PATH."
            }, indent=2))]

        log_files = sorted(logs_dir.glob("*.log"), key=os.path.getmtime, reverse=True)
        if log_index >= len(log_files):
            return [TextContent(type="text", text=json.dumps({
                "error": f"Index {log_index} out of range.",
                "available": [f.name for f in log_files]
            }, indent=2))]

        log_file = log_files[log_index]
        try:
            content = read_tail(log_file, last_n)
            parsed = parse_log_for_errors(content)
            return [TextContent(type="text", text=json.dumps({
                "file": log_file.name,
                "lines_returned": parsed["total_lines"],
                "errors_found": len(parsed["errors"]),
                "content": content
            }, indent=2))]
        except Exception as e:
            return [TextContent(type="text", text=json.dumps({"error": str(e)}, indent=2))]

    return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}, indent=2))]

# ─── MAIN ─────────────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read, write):
        await app.run(read, write, app.create_initialization_options())

if __name__ == "__main__":
    asyncio.run(main())
