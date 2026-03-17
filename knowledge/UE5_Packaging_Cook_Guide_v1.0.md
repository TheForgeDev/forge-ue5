# UE5 Packaging & Cook Errors — Knowledge Guide v1.0

---

## 1. OVERVIEW

Packaging converts your project into a distributable build. It involves:
1. **Cook** — converts assets to platform-specific formats
2. **Stage** — copies cooked assets + binaries to staging directory
3. **Package** — compresses/wraps for distribution

Most packaging failures happen at the Cook stage. The pattern is always: **works in editor → fails packaged**.

---

## 2. WHERE TO FIND ERRORS

```
After a failed package:
  Output Log → filter by "Error" — shows cook errors
  Saved/Logs/[ProjectName]-[Date].log — full log
  Saved/Cooked/ — partially cooked assets (inspect to find last failure)

For detailed cook log:
  Package project with:
  Project Settings → Packaging → Additional Cook Options:
  -cooklog -logcmds="LogCook Verbose"
```

---

## 3. COMMON COOK ERRORS

### ERROR-PKG01: "Cook Failed — Asset could not be cooked"

**Log pattern:**
```
LogCook: Error: Error cooking [/Game/Path/MyAsset]
```

**Causes and fixes:**

**A) Asset has unresolved references:**
```
Fix:
1. Open the asset in editor
2. Check for red/broken references in Details panel
3. Fix Up Redirectors: Content Browser → right-click folder → Fix Up Redirectors
4. Delete unused assets properly (don't delete files from disk directly)
```

**B) Blueprint compile error:**
```
Fix:
1. Open Blueprint → Compile — fix all errors
2. Run: File → Refresh All Nodes
3. Package again
```

**C) Asset references a missing plugin:**
```
Fix:
Check Edit → Plugins — is every required plugin enabled?
If referencing a marketplace plugin, ensure it's installed for the target engine version.
```

---

### ERROR-PKG02: "Works in editor, crashes in packaged build"

**This is the most common and hardest to debug.**

**Step 1: Check log from packaged build:**
```
[GameDir]/[ProjectName]/Saved/Logs/[ProjectName].log
```

**Step 2: Use Development instead of Shipping:**
```
Project Settings → Packaging → Build Configuration: Development
→ Packaged build includes debug symbols, better crash messages
```

**Step 3: Common causes:**

**A) Hardcoded paths:**
```cpp
// WRONG — absolute paths break in packaged build
UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, TEXT("C:/MyProject/Content/Tex.uasset"));

// CORRECT — content-relative paths
UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, TEXT("/Game/Textures/MyTex"));
// or use soft references / AssetManager
```

**B) Assets not being cooked (not referenced):**
```
Assets only cook if they are:
  - Directly referenced by a map that's in the cook list
  - In a "Always Cook" directory
  - Referenced by a Blueprint or C++ that's in the cook list

Fix:
Project Settings → Packaging → Additional Asset Directories to Cook
→ Add folders with assets you need but aren't directly referenced
```

**C) Null pointer on startup (CDO issue):**
```cpp
// Constructor accessing world or other actors — crashes in packaged
AMyActor::AMyActor()
{
    // WRONG — world not available in constructor
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), ...); // null GetWorld()
}

// CORRECT — use BeginPlay
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    // World is available here
}
```

---

### ERROR-PKG03: "Shader compilation failed" or black materials in package

**Cause:** Shader permutation not precompiled for target platform.

**Fix:**
```
1. Open Project Settings → Packaging
2. Enable "Share Material Shader Code" 
3. Enable "Shared Material Native Libraries"
4. Cook Shaders:
   File → Cook Content for [Platform]
   Wait for full shader compile before packaging

5. For specific shader errors:
   Output Log → search for "ShaderCompile Error"
   Usually means unsupported shader feature for target platform
   (e.g., ray tracing on mobile, tessellation on some platforms)
```

---

### ERROR-PKG04: Missing plugin or module in packaged build

**Log pattern:**
```
LogInit: Error: Unable to load plugin [PluginName]
```

**Fix:**
```cpp
// In .uplugin or .uproject, ensure plugin is marked:
{
    "Name": "MyPlugin",
    "Enabled": true,
    "WhitelistPlatforms": ["Win64", "Mac", "Linux"] // Add target platforms
}

// In Build.cs, ensure plugin module is listed:
PublicDependencyModuleNames.Add("MyPluginModule");
```

---

### ERROR-PKG05: "Package size too large" or slow packaging

**Common causes:**

**A) Development assets included:**
```
Project Settings → Packaging
→ Exclude editor content: check "Exclude editor content when cooking"
→ This removes ~30-50% of package size in most projects
```

**B) Uncompressed textures:**
```
Texture → Compression Settings → Default (DXT1/DXT5)
Not "VTC/ASTC Auto" — this packages multiple formats
```

**C) Too many shader permutations:**
```
Project Settings → Rendering
→ Disable unused rendering features (ray tracing if not used, etc.)
→ Each enabled feature multiplies shader permutations
```

---

### ERROR-PKG06: "LNK" errors during packaging

**Cause:** C++ compile errors that only appear for target platform (not editor build).

**Common pattern:**
```
LNK2019 in packaged build but not editor:
→ Module has different dependencies for Shipping vs Editor builds
→ Check Build.cs for PrivateDependencyModuleNames vs PublicDependencyModuleNames
```

**Fix:**
```csharp
// In Build.cs, some modules are editor-only:
if (Target.bBuildEditor)
{
    PrivateDependencyModuleNames.Add("UnrealEd");
}

// For game modules needed in all configurations:
PublicDependencyModuleNames.Add("GameplayAbilities");
```

---

### ERROR-PKG07: iOS / Android specific failures

**iOS:**
```
Common: "Provision profile" or "certificate" errors
Fix: Xcode → Preferences → Accounts → download provisioning profiles
Ensure bundle ID in Project Settings matches provisioning profile

Common: "WWDR certificate expired"
Fix: Download new Apple WWDR certificate from developer.apple.com
```

**Android:**
```
Common: "NDK not found"
Fix: Install Android NDK through Epic setup assistant
Project Settings → Platforms → Android SDK → check paths

Common: "Build tools version mismatch"
Fix: Install the specific Android Build Tools version shown in error
(usually via Android Studio SDK Manager)
```

---

## 4. PACKAGING CHECKLIST — BEFORE YOU PACKAGE

```
□ All Blueprints compile without errors (File → Compile All Blueprints)
□ Fix Up Redirectors run (Content Browser → right-click → Fix Up Redirectors)
□ Map list correct: Project Settings → Packaging → Maps to include
□ Default map set: Project Settings → Maps & Modes → Game Default Map
□ Required plugins listed and enabled
□ No editor-only assets referenced in game code
□ Test with Development build before Shipping
□ Shader compilation complete (no "Compiling Shaders" progress remaining)
```

---

## 5. DEVELOPMENT vs SHIPPING BUILD

| | Development | Shipping |
|---|---|---|
| Debug symbols | Yes | No |
| Log output | Full | Minimal |
| Asserts (`check()`) | Active | Stripped |
| Performance | ~10-20% slower | Optimal |
| Use for | Testing, crash debugging | Final release |

**Always test packaged builds in Development first.** Shipping removes all `check()` calls and most logging — crashes in Shipping are much harder to debug.

---

## 6. "WORKS IN EDITOR, FAILS PACKAGED" — SYSTEMATIC DEBUG

```
Step 1: Package with Development build
Step 2: Run the packaged executable
Step 3: Find the log: [GameDir]/Saved/Logs/*.log
Step 4: Search for "Error" and "Fatal" in log
Step 5: If crash (no helpful error):
  a. Enable crash reporter: Project Settings → Crash Reporter
  b. Run with -log flag: MyGame.exe -log
  c. Check Windows Event Viewer for crash dump
Step 6: Isolate:
  a. Remove plugins one by one
  b. Strip content to minimum and re-add
  c. Test specific level that reproduces the crash
```

---

## 7. USEFUL PACKAGING CONSOLE COMMANDS

```bash
# Package from command line (useful for CI/CD):
RunUAT.bat BuildCookRun 
    -project="[Path]/MyProject.uproject"
    -noP4 
    -platform=Win64 
    -clientconfig=Development 
    -cook -build -stage -package
    -archivedirectory="[OutputPath]"
    -cookflavor=Multi  # For multiple quality settings

# Cook only (faster iteration):
RunUAT.bat BuildCookRun 
    -project="[Path]/MyProject.uproject"
    -noP4 -platform=Win64 -cook -iterate
    # -iterate: only re-cook changed assets

# Verify cooked content:
UnrealEditor.exe [Path]/MyProject.uproject -run=DiffAssets
```

---

## 8. AGENT RULES

- "Works in editor but not packaged" → Step-by-step Section 6 debug flow
- Cook failed asset → check for broken references + BP compile errors (ERROR-PKG01)
- Hardcoded paths → content-relative path format (ERROR-PKG02-A)
- Asset not found in packaged build → "Additional Asset Directories to Cook" (ERROR-PKG02-B)
- Black materials / shader errors → shader precompilation (ERROR-PKG03)
- Missing plugin → .uplugin WhitelistPlatforms + Build.cs (ERROR-PKG04)
- Large package size → exclude editor content + texture compression (ERROR-PKG05)
- LNK in packaged not editor → editor-only module in Build.cs (ERROR-PKG06)
- Before packaging → run full checklist (Section 4)
- Always test Development before Shipping
