# UE5 Dev Environment Setup Guide v1.0

---

## 1. IDE CHOICE — VS vs Rider

| | Visual Studio 2022 | JetBrains Rider |
|---|---|---|
| Cost | Free (Community) | Paid (free for students) |
| IntelliSense quality | Medium (breaks often in UE5) | Good (ReSharper-based) |
| Live Coding integration | Full support | Full support |
| UE5 .uproject support | Yes | Yes (UE plugin required) |
| Recommended for | All levels | Intermediate+ |

**Recommendation:** VS 2022 Community is sufficient to start. Switch to Rider when the monthly cost is justifiable.

---

## 2. VISUAL STUDIO SETUP — REQUIRED COMPONENTS

These workloads are **required** in the VS installer:

```
✅ Desktop development with C++
✅ Game development with C++ (includes UE5-specific components)
```

Under "Individual Components":
```
✅ MSVC v143 - VS 2022 C++ x64/x86 build tools
✅ Windows 10/11 SDK (latest)
✅ C++ CMake tools for Windows
```

**Missing component symptoms:** "MSVC version not found" or "SDK not found" errors during build.

---

## 3. REGENERATING PROJECT FILES — WHEN AND HOW

### When it's needed:
- After adding a new C++ class
- After manually editing a .uplugin or .uproject file
- After changing the engine version
- When you get an "Include could not be found" error
- When IntelliSense stops working

### How to do it:
```
1. Close Unreal Editor
2. Right-click the .uproject file
3. Select "Generate Visual Studio project files"
4. When complete, open the .sln file
5. Build → Rebuild Solution
```

**IMPORTANT:** Regenerating project files with the editor open sometimes works but isn't reliable. Close the editor in uncertain situations.

---

## 4. HOT RELOAD vs LIVE CODING vs FULL REBUILD

Confusing these three causes Blueprint corruption and crashes.

### Hot Reload (DEPRECATED / old method)
- Deprecated since UE5.0
- Risk of data loss when used with Blueprints
- **Don't use it.** Switch to Live Coding.

### Live Coding (recommended)
- Triggered with Ctrl+Alt+F11 (or "Live Coding" button in editor)
- **When it's safe:**
  - Changing existing function bodies
  - Adding new functions (if the header doesn't change)
  - Adding local variables
- **When Full Rebuild is REQUIRED:**
  - New `UPROPERTY` added
  - New `UFUNCTION` added
  - Class hierarchy changed (new parent class)
  - New component (UActorComponent subclass) added
  - Any macro changed

### Full Rebuild (Unreal Header Tool runs)
```
With editor closed:
Visual Studio → Build → Rebuild Solution

or

With editor closed, in terminal:
UnrealBuildTool.exe MyProject Win64 Development -Project="..." -Rebuild
```

### Decision tree:
```
Made a change →
  Only modified a .cpp file → Live Coding is safe
  Modified a .h file →
    Only function body changed → Live Coding probably safe
    UPROPERTY/UFUNCTION added/removed → FULL REBUILD required
    New class added → FULL REBUILD required
```

---

## 5. BLUEPRINT CORRUPTION — CAUSE AND FIX

### Why it happens:
Live Coding updates the binary but doesn't update the references inside Blueprint assets (pin types, function signatures). If Live Coding is used after a header change, the Blueprint tries to hold the old signature → corruption.

### Symptoms:
- Red "ERROR" nodes when the Blueprint is opened
- "Function not found" warnings
- Editor crash on Blueprint compile

### Fix — try in order:
```
1. Close editor, Full Rebuild, reopen
2. Open the corrupted Blueprint → Compile → see errors
3. If error is "function not found": signature changed → delete the node in BP, reconnect
4. If error is "pin type mismatch": UPROPERTY type changed → refresh the related node
5. If unrecoverable: restore the previous Blueprint from Git, apply the C++ change more carefully
```

### Prevention rules:
```
RULE 1: When changing UPROPERTY/UFUNCTION → always do Full Rebuild
RULE 2: Before renaming a class → clear all references in Blueprints first
RULE 3: Before a large refactor → take a Git commit
```

---

## 6. INTELLISENSE ISSUES — TROUBLESHOOTING

### "Include not found" but build works:
```
1. Delete the .vs folder (hidden folder, in project root)
2. Close Visual Studio
3. .uproject → Generate VS project files
4. Reopen the .sln
5. Wait 5-10 minutes — IntelliSense is building its index
```

### IntelliSense completely broken:
```
VS: Tools → Options → Text Editor → C/C++ → Advanced
→ "Disable IntelliSense" = False
→ "Disable Squiggles" = False
→ IntelliSense Max Cached Translation Units = 5 (reduce)
```

### Include issues in Rider:
```
1. File → Invalidate Caches / Restart
2. Tools → Resync Solution
3. Delete .idea folder, reopen Rider
```

---

## 7. ADDING C++ FOR THE FIRST TIME — CONVERTING A BP-ONLY PROJECT

Follow these steps in order — don't skip any:

```
1. Open the editor
2. Tools → New C++ Class → select (Actor recommended for first time)
3. Wait for UHT and compilation to complete
4. CLOSE THE EDITOR
5. .uproject → Generate VS project files
6. Open VS → Build → Build Solution (not Rebuild)
7. Open the editor
8. Make changes from .sln, test with Live Coding
```

**Why close the editor:** After adding the first C++ class, project files change significantly. Regenerating project files while the editor is open doesn't fully reflect these changes.

---

## 8. BUILD CONFIGURATIONS — WHEN TO USE WHICH

| Configuration | Usage | Speed | Debug |
|---|---|---|---|
| Debug | Crash analysis, when full debug symbols are needed | Very slow | Full |
| DebugGame | Debugging game code | Slow | Game code full, engine fast |
| Development | Daily development | Medium | Partial |
| Shipping | Release build | Fast | None |

**For daily use:** `Development Editor`
**For crash analysis:** `DebugGame Editor`
**For performance testing:** `Development` (without editor)

---

## 9. COMMON SETUP ERRORS

### ERROR: "Could not compile. Try rebuilding from source manually."
**Cause:** Missing module in Build.cs, or wrong .generated.h path.
**Fix:**
```
1. Open Output Log — the real error is here
2. LNK error → missing module in Build.cs
3. Include error → regenerate project files
4. "UnrealHeaderTool failed" → macro syntax error, scan Output Log
```

### ERROR: "The game module could not be found"
**Cause:** Project name or module name changed.
**Fix:**
```
1. Open .uproject file (with a text editor)
2. Check "Name" value in the "Modules" array
3. Must match the folder name in the Source directory
4. The class name in Build.cs must also match
```

### ERROR: Build succeeds but changes don't show
**Cause:** Wrong configuration was compiled, or old .dll is loaded.
**Fix:**
```
1. Close the editor
2. Delete Binaries/ and Intermediate/ folders
3. Full Rebuild
```

### ERROR: Shader compilation taking very long (first launch)
**Normal behavior.** Shaders need to compile on first launch or after engine update. Can take 5-30 minutes depending on project size. Loaded from cache on subsequent launches.

---

## 10. AGENT RULES

- User says "VS can't find headers" / "IntelliSense broken" → Apply Section 6, start with project file regeneration
- User says "Blueprint corrupted" → Was this after Live Coding? Apply Section 5
- User is adding C++ for the first time → Apply Section 7 step by step
- "Could not compile" error → Check Section 9, ask for Output Log
- Full Rebuild needed but user doesn't know → Reference Section 4
