# UE5 World Partition & Level Streaming — Error & Setup Guide
### UE5 Dev Agent — Knowledge v1.0

---

## OVERVIEW

**World Partition** — UE5's automatic open world streaming system.
Divides the world into cells, streams them based on player location.
Replaces UE4's manual Level Streaming / World Composition.

**Key concepts:**
```
Streaming Cell     → chunk of world data, loaded/unloaded automatically
Data Layer         → group of actors that can be toggled on/off at runtime
HLOD (Hierarchical LOD) → simplified distant representation of streamed-out cells
World Partition Editor → visualizes cells, data layers, HLOD setup
```

---

## CHAPTER 1: SETUP ERRORS

---

### WP1 — World Partition Not Streaming In
**Symptom:** Level loads but geometry doesn't appear, world looks empty

**Checklist:**
```
1. World Partition enabled?
   World Settings → World Partition → Enable Streaming

2. Player has a streaming source?
   World Partition streams around UWorldPartitionReplicationGraphNode
   → Pawn must be possessed
   → In editor PIE: press Play first, then world streams

3. Streaming distance configured?
   World Settings → World Partition → Streaming Distances
   Default may be too small for your world scale

4. "Initial Load" cells set correctly?
   Actors marked as "Always Loaded" stay permanent
   Everything else streams based on distance

5. NavMesh data layer loaded?
   Navigation may be in a separate data layer — ensure it's loaded
```

**Common: Geometry visible in editor but not in PIE:**
```
World Partition only streams in PIE mode when player pawn is possessed.
Press F8 to eject from pawn → world un-streams (expected behavior).
Press F8 again to possess → world re-streams.
```

---

### WP2 — Data Layer Not Loading at Runtime
**Symptom:** Actors in data layer don't appear when layer is activated

```cpp
// Get World Partition Subsystem:
UWorldPartitionSubsystem* WPSubsystem =
    GetWorld()->GetSubsystem<UWorldPartitionSubsystem>();

// Activate data layer (C++):
#include "WorldPartition/DataLayer/WorldDataLayersSubsystem.h"

UWorldDataLayersSubsystem* DataLayerSubsystem =
    GetWorld()->GetSubsystem<UWorldDataLayersSubsystem>();

if (DataLayerSubsystem)
{
    // Get data layer asset reference:
    AWorldDataLayers* WorldDataLayers = DataLayerSubsystem->GetWorldDataLayers();
    // Set layer state:
    DataLayerSubsystem->SetDataLayerRuntimeState(
        MyDataLayerAsset,
        EDataLayerRuntimeState::Activated);
}
```

**States:**
```
Unloaded   → not in memory at all
Loaded     → in memory but not visible (logic runs, no rendering)
Activated  → in memory and visible
```

---

### WP3 — HLOD Not Generating / Appearing Incorrectly
**Symptom:** Distant objects pop in/out instead of showing HLOD

```
Generate HLODs:
1. World Partition Editor → HLOD tab
2. Select all actors → Generate HLODs
3. Build → Build All → includes HLOD data

HLOD issues checklist:
[ ] HLODs generated after all geometry placed?
[ ] HLOD layers configured correctly?
[ ] HLOD transition distance appropriate for world scale?
[ ] Nanite meshes generate Nanite HLODs — requires Nanite enabled
```

---

### WP4 — Always Loaded Actors Causing Performance Issues
**Symptom:** World partition not helping performance, everything loads at once

```
Actors marked "Always Loaded" never unload.
This includes: Sky, PostProcess volumes, GameMode actors.
Keep "Always Loaded" list minimal.

Check in World Partition Editor:
Filter → "Is Always Loaded" → review the list
Move runtime-only actors to streaming cells or data layers
```

---

### WP5 — World Partition Crash: Package Already Exists
**Symptom:** Crash with `Assertion failed: !FindObject (nullptr, *PackageName)`

This happens when streaming cell packages conflict.

**Fix:**
```
1. Close editor
2. Delete: Project/Saved/Cooked (if exists)
3. Delete: Project/Intermediate/Build
4. Delete: Project/DerivedDataCache
5. Reopen project — cells regenerate
```

---

## CHAPTER 2: LEVEL STREAMING (Traditional)

---

### WP6 — Level Streaming Basics C++

For games NOT using World Partition (or sub-levels):

```cpp
// Load level additively:
FLatentActionInfo LatentInfo;
LatentInfo.CallbackTarget = this;
UGameplayStatics::LoadStreamLevel(
    GetWorld(),
    FName("MySubLevel"),    // level name (not path)
    true,                   // make visible when loaded
    false,                  // block on load (false = async)
    LatentInfo
);

// Unload level:
UGameplayStatics::UnloadStreamLevel(
    GetWorld(),
    FName("MySubLevel"),
    LatentInfo,
    false   // fade out
);

// Check if level is loaded:
ULevelStreamingDynamic* StreamingLevel =
    UGameplayStatics::GetStreamingLevel(GetWorld(), FName("MySubLevel"));
if (StreamingLevel && StreamingLevel->IsLevelLoaded())
{
    // Level is loaded and visible
}
```

---

### WP7 — Level Not Visible After Loading
**Symptom:** LoadStreamLevel called but level doesn't appear

```cpp
// Issue: loaded but not set visible
// Solution — use delegate to set visible after load:
ULevelStreamingDynamic* StreamingLevel = UGameplayStatics::GetStreamingLevel(
    GetWorld(), FName("MySubLevel"));
if (StreamingLevel)
{
    StreamingLevel->OnLevelLoaded.AddDynamic(this, &AMyActor::OnSubLevelLoaded);
}

void AMyActor::OnSubLevelLoaded()
{
    ULevelStreamingDynamic* Level = UGameplayStatics::GetStreamingLevel(
        GetWorld(), FName("MySubLevel"));
    if (Level)
        Level->SetShouldBeVisible(true);
}
```

---

### WP8 — Persistent Level vs Sub-Level Actor Communication
**Symptom:** Can't find actors in sub-levels from persistent level

```cpp
// Actors in sub-levels are in a different level package
// UGameplayStatics::GetAllActorsOfClass searches ALL loaded levels:
TArray<AActor*> FoundActors;
UGameplayStatics::GetAllActorsOfClass(
    GetWorld(), AMyActor::StaticClass(), FoundActors);
// This works across levels but is expensive — cache result

// Better: use interface or delegate pattern
// Sub-level actor registers itself with a GameSubsystem on BeginPlay
// Persistent level queries the subsystem
```

---

## CHAPTER 3: C++ WORLD PARTITION API

---

### WP9 — Querying World Partition State

```cpp
#include "WorldPartition/WorldPartition.h"

// Get World Partition:
UWorldPartition* WP = GetWorld()->GetWorldPartition();
if (WP && WP->IsStreamingEnabled())
{
    // World Partition active
}

// Force load a cell area (for gameplay — e.g., teleport destination):
// Use UWorldPartitionRuntimeSpatialHashCell or
// place a WorldPartitionStreamingSourceComponent at target location temporarily
```

---

### WP10 — Debugging World Partition

```
Console commands:
wp.Runtime.ShowRuntimeSpatialHashGridLevel 1   // show cell grid
wp.Runtime.ToggleDrawRuntimeHash2D              // 2D debug view
wp.Runtime.DebugDrawStreamingSources 1          // show streaming sources
wp.Runtime.StreamingSourceDebugMode 1           // verbose streaming info

Log categories:
LogWorldPartition Verbose
LogLevelStreaming Verbose
```

---

## QUICK REFERENCE

| Problem | Entry |
|---|---|
| Nothing streaming in | WP1 |
| Data layer not activating | WP2 |
| HLOD issues | WP3 |
| Too much always loaded | WP4 |
| Package crash | WP5 |
| Sub-level not visible | WP7 |
| Cross-level actor access | WP8 |
