# UE5 Architecture Decision Guide v1.0

---

## 1. CORE QUESTION: "WHERE DOES THIS GO?"

Read this guide by asking "who should own this?" — not "what does it do?"

---

## 2. MAIN DECISION TABLE

| What you want to store | Where | Why |
|---|---|---|
| Match rules (win condition, round time) | `AGameModeBase` | Server-only, defines match rules |
| Current match state (score, time remaining) | `AGameStateBase` | Replicated, synced to all clients |
| Per-player control (input, camera, HUD) | `APlayerController` | Per-player, server+client |
| Player persistent data (name, XP, K/D) | `APlayerState` | Replicated, survives respawn |
| Character properties (health, movement speed) | `ACharacter` / `APawn` | The character itself, physical actor |
| Reusable behaviors (health system) | `UActorComponent` | Attachable to any Actor |
| Global systems (save, analytics, audio manager) | `UGameInstanceSubsystem` | Persists across level loads |
| Level-scoped systems (spawner, objective tracker) | `UWorldSubsystem` | Created/destroyed with the level |
| Per-object data/behavior | `UObject` subclass | Lightweight, GC-managed |
| Pure data container (item definition, ability config) | `UDataAsset` | Serializable, editable in editor |
| Read-only table data | `UDataTable` | Importable from CSV/JSON |

---

## 3. GAMEMODE vs GAMESTATE vs PLAYERCONTROLLER vs PLAYERSTATE

These four classes are the most commonly confused.

### GameMode
```
- Only exists on the server (not on clients)
- Answers: "What are the rules of this match?"
- Player spawn points, default Pawn class, HUD class go here
- Can change per level (each level can have its own GameMode)

DON'T PUT HERE: Score, current player list, timer state
PUT HERE: Win condition checks, round start/end logic
```

### GameState
```
- Exists on server + all clients (replicated)
- Answers: "What is the current state of the match?"
- Everything shown on HUD should be read from here

DON'T PUT HERE: Player input, camera
PUT HERE: Current score, time remaining, active player list, match phase
```

### PlayerController
```
- One per player (including spectators)
- All exist on server, only own local PC exists on client
- Input, camera, HUD, client-server communication

DON'T PUT HERE: Character HP, inventory
PUT HERE: Input binding, camera rotation, HUD reference, client RPCs
```

### PlayerState
```
- One per player
- Exists on server + all clients (replicated)
- Persists even when the Pawn/Character dies and respawns

DON'T PUT HERE: Match rules
PUT HERE: Player name, score, ping, persistent stats
```

### Quick Test:
```
"Does this data disappear when the player respawns?" → No → PlayerState
"Does this data disappear when the match ends, but all players see it?" → Yes → GameState
"Does only the server care about this?" → Yes → GameMode
"Is this per-player input/camera?" → Yes → PlayerController
```

---

## 4. COMPONENT vs ACTOR

### Choose Actor when:
- An entity that exists independently in the world (weapon, vehicle, NPC)
- Has its own Transform (location, rotation, scale)
- Can be spawned/destroyed independently

### Choose Component when:
- Behavior added to an Actor (health system, inventory, interaction)
- You want the same behavior on multiple Actor types
- It's part of an Actor, not independent

```cpp
// WRONG pattern — using an Actor like a component
AActor* HealthManager; // Actor reference inside Actor — weak design

// CORRECT pattern — Component
UPROPERTY(VisibleAnywhere)
TObjectPtr<UHealthComponent> HealthComp;
```

### Component Composition example:
```
ACharacter
  ├── UHealthComponent      — health, taking damage
  ├── UInventoryComponent   — inventory management
  ├── UInteractionComponent — detect nearby objects
  └── UCombatComponent      — attack, block, combo
```

With this pattern, `ABoss`, `APlayer`, and `AFriendlyNPC` all share the same `UHealthComponent` — no code duplication.

---

## 5. GAMEINSTANCE vs SUBSYSTEM

### GameInstance (old pattern, still valid)
```cpp
UCLASS()
class UMyGameInstance : public UGameInstance {
    GENERATED_BODY()
public:
    TArray<FSaveSlotInfo> SaveSlots;
    void SaveGame();
    void LoadGame();
};
```
- Persists across level loads
- Single instance, accessible everywhere
- Problem: grows into a "god object" as the project scales

### GameInstance Subsystem (UE5 recommended pattern)
```cpp
UCLASS()
class USaveGameSubsystem : public UGameInstanceSubsystem {
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    void SaveGame();
    void LoadGame();
};

// Access from anywhere:
USaveGameSubsystem* SaveSys = GetGameInstance()->GetSubsystem<USaveGameSubsystem>();
```

**Subsystem advantages:**
- Doesn't bloat GameInstance
- Auto-initialized and deinitialized
- Unit testable (can be mocked)
- Each system owns its own responsibility (SRP compliant)

### When to use which?
```
New project or UE5.0+  →  Subsystem (always)
Legacy project, GameInstance already large  →  Add to GameInstance or gradually migrate to Subsystem
```

---

## 6. WORLD SUBSYSTEM vs GAMEINSTANCE SUBSYSTEM

```
UWorldSubsystem
  - Created and destroyed with a World (level)
  - For level-scoped systems: spawner, objective tracker, ambient sound manager
  - Initialize runs on level load, Deinitialize on unload

UGameInstanceSubsystem
  - Created when the game starts, lives until the application closes
  - For systems that persist across level transitions: save/load, analytics, leaderboard
```

---

## 7. UOBJECT vs USTRUCT vs PLAIN C++

| | UObject | UStruct | Plain C++ struct/class |
|---|---|---|---|
| Managed by GC | Yes | No | No |
| Usable in Blueprint | Yes | Yes (limited) | No |
| Supports UPROPERTY | Yes | Yes | No |
| Serializable | Yes | Yes | No |
| Cost | High | Low | Very low |
| When to use | Complex objects, BP access needed | Data groups, structs to replicate or expose to BP | Pure computation, outside engine |

```cpp
// UObject — needs behavior + data + BP access
UCLASS(BlueprintType)
class UItemBase : public UObject { ... };

// UStruct — data only, to be replicated or used in BP
USTRUCT(BlueprintType)
struct FItemData {
    GENERATED_BODY()
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    FName ItemID;
    UPROPERTY(EditAnywhere, BlueprintReadWrite)
    int32 Quantity;
};

// Plain C++ — pure computation, outside engine
struct FMathHelper {
    static float Lerp(float A, float B, float T) { return A + T * (B - A); }
};
```

---

## 8. DATAASSET vs DATATABLE vs SOFTOBJECTPTR

### UDataAsset
```cpp
UCLASS(BlueprintType)
class UWeaponConfig : public UDataAsset {
    GENERATED_BODY()
public:
    UPROPERTY(EditAnywhere)
    float Damage;
    UPROPERTY(EditAnywhere)
    TObjectPtr<UStaticMesh> Mesh;
};
```
- Asset created in Content Browser
- Easily editable in editor
- One-to-one relationship: one weapon = one asset
- Loadable via AssetManager using Primary Data Asset pattern

### UDataTable
- Imported from CSV or JSON
- Large sets of similar data (item list, enemy stats)
- Can't add/remove rows at runtime
- Easy to read from Blueprint

### Soft Reference vs Hard Reference

```cpp
// Hard reference — asset is ALWAYS in memory
UPROPERTY(EditDefaultsOnly)
TObjectPtr<UStaticMesh> AlwaysLoadedMesh; // Loaded when level loads

// Soft reference — loaded on demand
UPROPERTY(EditDefaultsOnly)
TSoftObjectPtr<UStaticMesh> LazyLoadedMesh;

// Loading
UStaticMesh* Mesh = LazyLoadedMesh.LoadSynchronous(); // Sync (hitching risk)
// or async:
StreamableManager.RequestAsyncLoad(LazyLoadedMesh.ToSoftObjectPath(), FStreamableDelegate::CreateUObject(...));
```

**Rule:** In systems with many references (inventory, ability database), don't use hard references — memory bloats. Use `TSoftObjectPtr` + async load.

---

## 9. MULTIPLAYER ARCHITECTURE — WHO IS RESPONSIBLE?

```
Server (Authority):
  - Changes game state (apply damage, respawn)
  - Replication source (sends changes to clients)
  - Cheat-sensitive logic goes here

Client (Simulated):
  - Visual effects (particles, sound)
  - Local input processing (then sent to server via Server RPC)
  - UI updates (from replicated values)

Both:
  - Physics simulation (but authority is on server)
```

### Architecture Template:
```
Player fires weapon:
  1. Client: Detect input → start local animation (fast feedback)
  2. Client: Send Server_Fire() RPC
  3. Server: Server_Fire_Implementation() runs → calculate damage → update HP
  4. Server: HP changes → Replicated HP is sent to clients
  5. Client: OnRep_Health() runs → HUD updates
  6. Server: Multicast_PlayFireEffect() → effect plays on all clients
```

---

## 10. COMMON ARCHITECTURE MISTAKES

### BUG-A01: Putting data in the wrong class
**Symptom:** Score resets after respawn.
**Cause:** Score is on `ACharacter` — destroyed on respawn.
**Fix:** Move score to `APlayerState` — persists across respawn.

### BUG-A02: Server logic running on client
**Symptom:** Different players see different results in multiplayer.
**Cause:** Damage calculation runs independently on each client.
**Fix:** `HasAuthority()` check — calculate damage on server only, replicate the result.

### BUG-A03: GameInstance god object
**Symptom:** `UMyGameInstance` is 2000+ lines, every system was added here.
**Fix:** Move each responsibility to a `UGameInstanceSubsystem`. Leave GameInstance as a thin coordinator.

### BUG-A04: Chained hard references
**Symptom:** Game takes very long to open, memory usage is very high.
**Cause:** When one asset loads, chained hard references via UPROPERTY load with it.
**Fix:** Use `TSoftObjectPtr` for large assets, async load on demand.

### BUG-A05: Expensive operations in Tick
**Symptom:** FPS drops, profiler shows a specific Actor's Tick taking too long.
**Fix:**
```cpp
// Bad — runs every frame
void AMyActor::Tick(float DeltaTime) {
    TArray<AActor*> NearbyActors;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AActor::StaticClass(), NearbyActors);
    // Running for thousands of actors every frame
}

// Good — runs on a timer
void AMyActor::BeginPlay() {
    GetWorldTimerManager().SetTimer(ScanTimer, this, &AMyActor::ScanNearbyActors, 0.5f, true);
}
```

---

## 11. AGENT RULES

- "Where should this go?" → Check Section 2 table, suggest the matching category
- "GameState or GameInstance?" → Does it need to survive level transitions? Yes → GameInstance/Subsystem. No → GameState
- "Component or Actor?" → Does it exist independently in the world? Yes → Actor. No → Component
- Multiplayer question → Apply Section 9 template, clarify where Authority lives
- "Hard reference / memory issue" → Section 8, suggest TSoftObjectPtr
- Performance issue in Tick → Apply BUG-A05 pattern
