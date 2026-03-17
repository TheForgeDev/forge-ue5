# UE5 Plugin Development — Error & Setup Guide
### UE5 Dev Agent — Knowledge v1.0

---

## PLUGIN STRUCTURE

```
MyPlugin/
├── MyPlugin.uplugin          ← plugin descriptor
├── Source/
│   └── MyPlugin/
│       ├── MyPlugin.Build.cs ← module build rules
│       ├── Public/
│       │   └── MyPlugin.h   ← public headers
│       └── Private/
│           └── MyPlugin.cpp ← implementation
├── Content/                  ← optional assets
└── Resources/
    └── Icon128.png           ← marketplace icon
```

---

## CHAPTER 1: UPLUGIN FILE

---

### PL1 — .uplugin File Structure

```json
{
    "FileVersion": 3,
    "Version": 1,
    "VersionName": "1.0",
    "FriendlyName": "My Plugin",
    "Description": "Does something useful",
    "Category": "Other",
    "CreatedBy": "Your Name",
    "CreatedByURL": "",
    "DocsURL": "",
    "MarketplaceURL": "",
    "SupportURL": "",
    "CanContainContent": true,
    "IsBetaVersion": false,
    "IsExperimentalVersion": false,
    "Installed": false,
    "Modules": [
        {
            "Name": "MyPlugin",
            "Type": "Runtime",
            "LoadingPhase": "Default"
        }
    ],
    "Plugins": [
        {
            "Name": "Niagara",
            "Enabled": true
        }
    ]
}
```

**Module Type values:**
```
Runtime        → loads in game and editor
RuntimeAndGame → only in game builds
Editor         → only in editor
EditorAndProgram → editor and commandlets
```

**LoadingPhase values:**
```
Default          → standard game module load time
PreDefault       → before Default modules
PostDefault      → after Default modules
PostConfigInit   → very early — required for shaders
PreEarlyLoadingScreen → for splash screens
```

---

### PL2 — Plugin Failed to Load: Missing Dependency
**Symptom:** `Plugin 'X' failed to load because module 'Y' could not be loaded`

```json
// In .uplugin — declare ALL plugin dependencies:
"Plugins": [
    { "Name": "Niagara", "Enabled": true },
    { "Name": "MetasoundEngine", "Enabled": true },
    { "Name": "GameplayAbilities", "Enabled": true }
]
```

**And in Build.cs:**
```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core", "CoreUObject", "Engine",
    "Niagara",           // if using Niagara
    "MetasoundEngine",   // if using MetaSounds
    "GameplayAbilities", // if using GAS
});
```

Missing from .uplugin + missing from Build.cs = module load failure.

---

### PL3 — EngineVersion Locking Breaking Compatibility
**Symptom:** Plugin shows as incompatible with engine version

```json
// WRONG — locks to specific engine version:
"EngineVersion": "5.3.0"

// RIGHT — remove or leave empty for broader compatibility:
"EngineVersion": ""

// OR use version range (preferred for marketplace):
// Don't set EngineVersion — let marketplace manage per-version uploads
```

---

## CHAPTER 2: MODULE SETUP

---

### PL4 — Module Interface — Required Boilerplate

```cpp
// MyPlugin.h — public:
#pragma once
#include "CoreMinimal.h"
#include "Modules/ModuleManager.h"

class FMyPluginModule : public IModuleInterface
{
public:
    virtual void StartupModule() override;
    virtual void ShutdownModule() override;
};

// MyPlugin.cpp — private:
#include "MyPlugin.h"

#define LOCTEXT_NAMESPACE "FMyPluginModule"

void FMyPluginModule::StartupModule()
{
    // Initialize your plugin here
    // Register custom asset types, editor extensions, etc.
}

void FMyPluginModule::ShutdownModule()
{
    // Clean up — unregister everything registered in StartupModule
}

#undef LOCTEXT_NAMESPACE

IMPLEMENT_MODULE(FMyPluginModule, MyPlugin)
// ↑ This line is REQUIRED — links module name to class
```

---

### PL5 — IMPLEMENT_MODULE Missing
**Symptom:** Linker error or module not found at runtime

Every module .cpp MUST have `IMPLEMENT_MODULE(ClassName, ModuleName)`.
Without it → module won't load.

```cpp
// At bottom of primary .cpp:
IMPLEMENT_MODULE(FMyPluginModule, MyPlugin)

// For simple modules with no custom class:
IMPLEMENT_MODULE(FDefaultModuleImpl, MyPlugin)
```

---

### PL6 — Public vs Private Headers

```
Public/   → headers exposed to projects using this plugin
Private/  → internal implementation, not exposed

// Build.cs — tell compiler where headers are:
public MyPlugin(ReadOnlyTargetRules Target) : base(Target)
{
    PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

    PublicIncludePaths.AddRange(new string[]
    {
        Path.Combine(ModuleDirectory, "Public")
    });

    PrivateIncludePaths.AddRange(new string[]
    {
        Path.Combine(ModuleDirectory, "Private")
    });
}
```

---

### PL7 — API Export Macro Missing
**Symptom:** Classes in plugin not accessible from project code

```cpp
// Every public class needs the API macro:
#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MyPluginActor.generated.h"

// MYPLUGIN_API makes this class accessible from outside the module:
UCLASS()
class MYPLUGIN_API AMyPluginActor : public AActor
{
    GENERATED_BODY()
    // ...
};

// Without MYPLUGIN_API:
// - Class inaccessible from project code
// - LNK2019 when trying to use it
```

**How the macro is generated:**
```
Module named "MyPlugin" → macro is "MYPLUGIN_API"
Module named "MyGameSystem" → macro is "MYGAMESYSTEM_API"
All uppercase, _API suffix
```

---

## CHAPTER 3: EDITOR EXTENSIONS

---

### PL8 — Custom Asset Type

```cpp
// Register custom asset in StartupModule:
void FMyPluginModule::StartupModule()
{
    // Register asset category:
    IAssetTools& AssetTools =
        FModuleManager::LoadModuleChecked<FAssetToolsModule>("AssetTools")
        .Get();

    EAssetTypeCategories::Type Category =
        AssetTools.RegisterAdvancedAssetCategory(
            FName("MyPlugin"),
            FText::FromString("My Plugin"));

    // Register asset type actions:
    TSharedRef<IAssetTypeActions> Actions =
        MakeShared<FMyAssetTypeActions>(Category);
    AssetTools.RegisterAssetTypeActions(Actions);
    RegisteredAssetTypeActions.Add(Actions);
}

void FMyPluginModule::ShutdownModule()
{
    // MUST unregister in ShutdownModule:
    if (FModuleManager::Get().IsModuleLoaded("AssetTools"))
    {
        IAssetTools& AssetTools =
            FModuleManager::GetModuleChecked<FAssetToolsModule>("AssetTools")
            .Get();
        for (auto& Action : RegisteredAssetTypeActions)
            AssetTools.UnregisterAssetTypeActions(Action);
    }
}
```

---

### PL9 — Custom Editor Module Separation

```
Best practice: separate Runtime and Editor code into separate modules.

MyPlugin/Source/
├── MyPlugin/        ← Runtime module (game code)
│   └── MyPlugin.Build.cs
└── MyPluginEditor/  ← Editor module (editor tools, custom details panels)
    └── MyPluginEditor.Build.cs

// Editor module Build.cs:
public MyPluginEditor(ReadOnlyTargetRules Target) : base(Target)
{
    // Editor modules only compile for editor builds:
    PrivateDependencyModuleNames.AddRange(new string[]
    {
        "Core", "CoreUObject", "Engine",
        "UnrealEd",        // editor utilities
        "AssetTools",      // asset type registration
        "PropertyEditor",  // custom details panels
        "SlateCore",       // Slate UI
        "Slate",
        "MyPlugin",        // depend on your runtime module
    });
}

// .uplugin — both modules:
"Modules": [
    { "Name": "MyPlugin", "Type": "Runtime", "LoadingPhase": "Default" },
    { "Name": "MyPluginEditor", "Type": "Editor", "LoadingPhase": "Default" }
]
```

---

## CHAPTER 4: MARKETPLACE REQUIREMENTS

---

### PL10 — Marketplace Submission Checklist

```
Code requirements:
[ ] No hardcoded project-specific paths
[ ] No engine modifications (must work with binary engine)
[ ] All public classes use MODULENAME_API macro
[ ] No Editor code in Runtime module
[ ] Plugin builds on clean project (test with blank template)
[ ] Tested on UE5.1, 5.2, 5.3, 5.4, 5.5 (or specify versions)

.uplugin requirements:
[ ] EngineVersion empty or removed
[ ] Description filled
[ ] FriendlyName human-readable
[ ] Category set appropriately
[ ] CanContainContent = true if has assets

Assets:
[ ] Icon128.png present in Resources/
[ ] All textures compressed appropriately
[ ] No placeholder/test assets in final build

Third-party code:
[ ] License compatible with marketplace
[ ] Third-party libs in ThirdParty/ folder
[ ] Proper attribution in license files
```

---

### PL11 — Testing Plugin in Isolation

```
Always test in blank project before submitting:

1. Create blank C++ project
2. Copy plugin to [Project]/Plugins/
3. Right-click .uproject → Generate VS Project Files
4. Compile and open
5. Verify no errors or warnings related to your plugin

Common issues only caught in isolation:
- Missing include paths
- Hardcoded paths that don't exist in other projects
- Missing dependencies only present in your test project
- Editor-only code in Runtime module
```

---

### PL12 — Plugin Not Showing in Editor

**Checklist:**
```
1. Plugin in correct folder?
   [Project]/Plugins/MyPlugin/ → project plugin
   [Engine]/Plugins/Marketplace/MyPlugin/ → engine plugin

2. .uplugin valid JSON? (check with JSON validator)

3. Module compiled?
   Right-click .uproject → Generate VS Project Files → Compile

4. Enabled in editor?
   Edit → Plugins → find your plugin → enable checkbox

5. "Missing modules" dialog?
   → Click "Yes" to rebuild
   → If fails: check Build.cs for errors
```

---

## QUICK REFERENCE

| Problem | Entry |
|---|---|
| Plugin fails to load | PL2 |
| Version incompatibility | PL3 |
| Module not found | PL5 |
| LNK2019 from plugin | PL7 |
| Class not accessible | PL7 |
| Asset type registration | PL8 |
| Marketplace prep | PL10 |
| Not showing in editor | PL12 |
