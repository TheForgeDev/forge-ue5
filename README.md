# Forge — UE5 Dev Agent

**An AI-powered debugging and architecture assistant for Unreal Engine 5 C++ developers.**

Forge diagnoses crashes, reviews code, spots multiplayer security vulnerabilities, and guides architecture decisions — powered by 30 knowledge files covering the full UE5 C++ ecosystem.

> **"Paste nothing. Forge reads it."**
> 
> With MCP active, Forge reads your Output Log, build errors, and C++ files directly from your editor. No copy-paste, no context switching.

---

## What Forge Does

- **OOM-Safe crash & error diagnosis** — Forge reads 5GB+ Output Logs using memory-safe streaming queues (zero RAM bloat), categorizes errors, and gives you the root cause in seconds
- **Code review** — safety, UE5 standards, performance, multiplayer security scan
- **Architecture consulting** — "where does this go?" with decision tables
- **System analysis** — paste multiple files, Forge analyzes them as a unified system
- **Version migration warnings** — tells you what breaks when upgrading UE versions
- **Multiplayer security scan** — unauthorized Server RPCs, unreplicated state, ownership issues
- **Teaching mode** — explains *why* a bug happened, not just the fix
- **Session memory** — remembers previously found issues across conversations
- **Accessibility (VI) mode** — full screen-reader support for visually impaired developers

---

## Setup (5 minutes)

### Step 1 — Clone
```bash
git clone https://github.com/TheForgeDev/forge-ue5
cd forge-ue5
```

### Step 2 — Install
```bash
pip install mcp httpx
```

### Step 3 — Enable Remote Control API in UE5
```
Edit → Plugins → Remote Control API → Enable → Restart Editor
```

### Step 4 — Configure Claude Desktop

Open your Claude Desktop config file:
- **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
- **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

Add Forge:
```json
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
```

Replace paths with your actual locations.

### Step 5 — Restart Claude Desktop

Forge will appear as a connected tool. No files need to be uploaded to Claude Projects.

### Step 6 — Start your first conversation

```
UE5 version: 5.4
Platform: PC
Project type: multiplayer game
Experience: intermediate C++
```

---

## How It Works

### Lazy Knowledge Loading

Forge doesn't load all 30 knowledge files upfront. Instead, it loads only what's needed:

```
You: "My GAS ability isn't activating after respawn"
Forge: reads knowledge/gas.md → analyzes your specific issue

You: "Now my Chaos Vehicle only goes backward"  
Forge: reads knowledge/chaos_vehicles.md → different module, loaded fresh
```

**Token usage:**
- Without MCP (manual): ~150K tokens (all files loaded)
- With MCP lazy loading: ~10-15K tokens per conversation


### The "Brain" vs The "Nervous System"

Claude is the reasoning engine — but out-of-the-box LLMs hallucinate UE5 C++ APIs. Forge acts as the nervous system: it provides the eyes (Remote Control API), the hands (file reading), and the strict rulebook (30 specialized knowledge files) so the LLM never guesses — it references.

### Session Memory

Forge remembers what it finds across conversations:

```
Week 1: Fixed InitAbilityActorInfo missing in MyCharacter.cpp → saved

Week 2: Analyzing MyVehicle.cpp
Forge: "InitAbilityActorInfo was also missed in MyCharacter.cpp 
        (March 14). Checking MyVehicle.cpp for the same pattern..."
```

Session data is stored locally in `.forge_session.json` — never leaves your machine.


---

## Available Tools

| Tool | What it does |
|---|---|
| `read_knowledge(topic)` | Load a knowledge module on demand |
| `get_project_info` | UE5 version, project name, connection status |
| `analyze_output_log` | Read and categorize errors from Output Log |
| `get_build_errors` | LNK, C2xxx, UHT compiler errors |
| `get_blueprint_errors` | Blueprint compile failures |
| `get_active_plugins` | Active plugins from .uproject |
| `get_cpp_file(path)` | Read a C++ file for code review |
| `get_crash_dump` | Most recent crash report |
| `get_shader_errors` | Material/shader compilation failures |
| `read_saved_log(n)` | Read a specific log from Saved/Logs/ |
| `get_session_memory` | Load previously found issues for this project |
| `save_session_finding` | Save a finding to session memory |

---

## Knowledge Base (30 Modules)

| Topic keyword | Coverage |
|---|---|
| `gas` | GAS setup, InitAbilityActorInfo, AttributeSet, replication |
| `multiplayer` | Replication, RPC, authority, Online Subsystem |
| `security` | Server RPC validation, exploit patterns, ownership |
| `vehicle` | Chaos Vehicles setup, 7 error patterns |
| `save` | Save/Load system, serialization, inventory |
| `animation` | IK Retargeter, Motion Matching, Mixamo |
| `blueprint` | All UPROPERTY/UFUNCTION specifiers |
| `architecture` | GameMode/State/Controller decisions, Subsystems |
| `devenv` | VS setup, Live Coding, IntelliSense |
| `lumen` | Lumen/Nanite console variables, artifacts |
| `material` | Materials, shaders, HLSL custom nodes |
| `world_partition` | Streaming, data layers, HLOD |
| `input` | Enhanced Input System, migration from legacy |
| `ui` | UMG, BindWidget, CommonUI, 3D widgets |
| `packaging` | Cook errors, "works in editor fails packaged" |
| `threading` | Async patterns, TWeakObjectPtr in lambdas |
| `versions` | UE5.0→5.5 breaking changes |
| `ai` | Behavior Trees, EQS, custom tasks |
| `audio` | MetaSounds, attenuation, audio debugging |
| `plugin` | Plugin development, module boilerplate |

---

## Example Conversations

**Crash diagnosis:**
```
"My game crashed. Can you analyze the log?"
→ Forge reads Output Log directly, categorizes errors, gives root cause
```

**Code review:**
```
"Review MyCharacter.cpp for multiplayer security issues"
→ Forge reads the file, runs security scan, flags RPC validation gaps
```

**System analysis:**
```
"Here are my GAS setup files — what will break as the project grows?"
→ Forge loads gas knowledge, analyzes files as a system, flags weak points
```

**Version migration:**
```
"I'm upgrading from UE5.3 to 5.4. What should I check?"
→ Forge loads versions knowledge, lists breaking changes relevant to your code
```

---

## Accessibility Mode

For developers using screen readers (NVDA, JAWS, VoiceOver):

```
enable VI mode
```

Output becomes screen-reader friendly: code blocks described before displaying, errors explained in 3 structured layers, symbols replaced with words.

Disable with: `disable VI mode`

---

## Works with Other AI Tools

`server.py` is a standard MCP server — works with any MCP-compatible client:

| Tool | Config location |
|---|---|
| Claude Desktop | `%APPDATA%/Claude/claude_desktop_config.json` |
| Cursor | `.cursor/mcp.json` in project root |
| Windsurf | `~/.config/windsurf/mcp.json` |
| VS Code | `.vscode/mcp.json` |

Note: Knowledge files and session memory work best with Claude, which understands the Forge system prompt context.

---

## Forge vs Other UE5 AI Tools

| | Forge | UnrealClaude / unreal-mcp |
|---|---|---|
| Editor control (spawn actors, edit BP) | Planned (Phase 2) | Yes |
| Crash log analysis | Yes | Partial |
| UE version migration warnings | Yes | No |
| Multiplayer security scan | Yes | No |
| Architecture consulting | Yes | No |
| Session memory | Yes | No |
| Teaching mode | Yes | No |
| Deep domain knowledge (30 modules) | Yes | No |
| Token efficient (lazy loading) | Yes | N/A |
| Installation | pip install | Plugin + npm |

Forge and editor control tools are **complementary**. Use both for best results.

---

## Contributing

Pull requests welcome. To add a knowledge module:

1. Create `knowledge/UE5_[Domain]_Guide_v1.0.md`
2. Add the topic → filename mapping to `KNOWLEDGE_MAP` in `server.py`
3. Follow the existing format: overview, C++ setup, common errors, debug commands, agent rules
4. All content in English
5. Submit PR with a brief description

---

## Roadmap

- [x] Core knowledge base (30 files)
- [x] MCP server with diagnosis tools
- [x] Lazy knowledge loading
- [x] Session memory
- [ ] Editor control tools (Phase 2 — fork of UnrealClaude)
- [ ] Git diff analysis ("what will this commit break?")
- [ ] Pre-commit security scan
- [ ] Test suite — 25-question benchmark
- [ ] **Phase 3: Active Control Architect (v2.0)** — Evolving beyond passive debugging. Integrating Model Predictive Control (MPC) solvers (OSQP) to let Forge actively optimize robotic locomotion, advanced vehicle dynamics, and GAS-driven physics directly in the engine.

---

## License

MIT — free to use, modify, and distribute. Token costs are always the user's own.

---

*Forge grew from a simple question: why does the same GAS crash take every developer hours to find, when the answer is always the same? The goal: put 30 files of accumulated UE5 C++ knowledge into every developer's context window.*
