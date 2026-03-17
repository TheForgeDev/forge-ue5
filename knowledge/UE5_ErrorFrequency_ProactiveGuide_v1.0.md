# UE5 Error Frequency & Proactive Suggestion Guide
### UE5 Dev Agent — Knowledge v1.0
### Purpose: Agent uses this to proactively warn users BEFORE problems occur

---

## HOW THE AGENT USES THIS FILE

When a user is working on a topic, the agent cross-references against the
"WATCH FOR" lists below and proactively adds warnings.

Example:
User asks: "How do I store a reference to another Actor?"
Agent answers the question AND adds: "⚠ Common mistake here: missing UPROPERTY()
causes GC crash. This is the #1 most reported UE5 C++ issue."

---

## TIER 1 — EXTREMELY COMMON (Every beginner hits these)

These appear in almost every UE5 C++ discussion. Agent should mention
proactively whenever the relevant topic comes up.

---

### F1: Missing UPROPERTY on UObject Pointer
**Frequency:** #1 most reported UE5 C++ issue
**When it bites:** Seemingly random crashes minutes after starting
**Symptom:** Access violation with non-zero random memory address

```cpp
// DANGER — missing UPROPERTY:
UCameraComponent* Camera;  // GC will collect this

// SAFE:
UPROPERTY()
TObjectPtr<UCameraComponent> Camera;
```

**Agent proactive trigger:** Any time user stores a pointer to a UObject/AActor
as a member variable → automatically mention UPROPERTY requirement.

---

### F2: Hot Reload Blueprint Corruption
**Frequency:** #2 most reported — affects virtually all beginners
**When it bites:** After compiling with editor open
**Symptom:** Blueprints behave wrong, variables missing, hierarchy broken

**Agent proactive trigger:** Any compile-related question → remind about
closing editor first or using Live Coding.

---

### F3: Missing IsValid() Before Pointer Use
**Frequency:** Extremely common, closely tied to F1
**When it bites:** Any time an optional reference might not exist
**Symptom:** Access violation with address near zero (0x00000000 - 0x000000FF)

**Agent proactive trigger:** Any time user calls a method on a pointer
that could be null → suggest IsValid() or ensure().

---

### F4: LNK2019 — Missing Module in Build.cs
**Frequency:** Every time a new system is used (GAS, UMG, AI, etc.)
**When it bites:** First time using any non-default UE class
**Symptom:** Compiler error mentioning unresolved external symbol

**Common missing modules:**
```csharp
"UMG"                // UUserWidget, UButton, etc.
"AIModule"           // AAIController, UBlackboardComponent
"GameplayAbilities"  // GAS system
"GameplayTasks"      // GAS tasks
"NavigationSystem"   // UNavigationSystemV1
"Niagara"            // UNiagaraSystem
"PhysicsCore"        // Physics classes
"Chaos"              // Chaos physics
"EnhancedInput"      // Enhanced Input System
"MovieScene"         // Sequencer
"MediaAssets"        // Media player
```

**Agent proactive trigger:** Any time user uses a class from a non-Core module
→ mention Build.cs dependency requirement.

---

### F5: Super:: Call Missing
**Frequency:** Very common — especially BeginPlay and Tick
**When it bites:** Silently — functionality stops working with no error
**Symptom:** Tick not firing, components not initializing, movement broken

```cpp
// WRONG — missing Super calls:
void AMyActor::BeginPlay() { /* your code */ }
void AMyActor::Tick(float DeltaTime) { /* your code */ }

// RIGHT:
void AMyActor::BeginPlay()
{
    Super::BeginPlay(); // ALWAYS first
    /* your code */
}
void AMyActor::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime); // ALWAYS first
    /* your code */
}
```

**Agent proactive trigger:** Any override of BeginPlay, Tick, EndPlay,
PostInitializeComponents → remind about Super:: call.

---

### F6: Reading Visual Studio Error List Instead of Output Window
**Frequency:** Universal beginner mistake
**When it bites:** Developer chases false errors, real errors missed
**Fix:** Alt+2 → Output window

**Agent proactive trigger:** Any time user shares compiler errors →
ask if they're reading from Output window, not Error List.

---

### F7: Tick Not Working — bCanEverTick Not Set
**Frequency:** Very common
**When it bites:** Silently — Tick function defined but never called
**Symptom:** No crash, no error, Tick just doesn't fire

```cpp
// Required in Constructor:
PrimaryActorTick.bCanEverTick = true;
PrimaryActorTick.bStartWithTickEnabled = true;
```

**Agent proactive trigger:** Any Tick-related question → verify constructor setup.

---

### F8: UPROPERTY Reading in Constructor
**Frequency:** Common intermediate mistake
**Symptom:** Value is always default, changes in editor don't apply

```cpp
// UPROPERTY values are set AFTER constructor returns
// Cannot read them in constructor:
AMyActor::AMyActor()
{
    FVector Pos = MyEditableVector; // WRONG — not set yet
}

// Read them in BeginPlay or PostInitProperties:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    FVector Pos = MyEditableVector; // RIGHT — values are set now
}
```

**Agent proactive trigger:** User reads UPROPERTY in constructor → warn about timing.

---

## TIER 2 — COMMON (Intermediate developers)

These appear regularly in forums. Agent should mention when directly relevant.

---

### F9: CDO Constructor Failed to Find
**Frequency:** Common when using ConstructorHelpers
**Symptom:** "CDO Constructor: Failed to find /Game/..." in log, object not spawning

**Causes:**
- Asset path is wrong (typo, moved file)
- Using Blueprint path without `_C` suffix for class finders
- Asset doesn't exist yet when CDO is created

```cpp
// Class finder requires _C suffix:
static ConstructorHelpers::FClassFinder<APawn> PawnClass(
    TEXT("/Game/Blueprints/BP_MyCharacter.BP_MyCharacter_C")); // _C required

// Object finder for assets:
static ConstructorHelpers::FObjectFinder<UStaticMesh> MeshAsset(
    TEXT("/Game/Meshes/SM_Rock.SM_Rock")); // no _C for assets
```

**Agent proactive trigger:** ConstructorHelpers usage → verify path format.

---

### F10: TObjectPtr Misuse
**Frequency:** Common since UE5.0 introduced TObjectPtr
**Key facts developers get wrong:**

```cpp
// TObjectPtr is NOT a smart pointer:
// - In shipped builds it IS a raw pointer
// - UPROPERTY() is still required separately
// - Use for HEADER member variables only
// - Function parameters and returns still use UObject*

// CORRECT usage:
UPROPERTY()
TObjectPtr<AActor> MyActor; // header member variable

// WRONG usage:
TObjectPtr<AActor> GetMyActor() { return MyActor; } // return type should be AActor*
void DoSomething(TObjectPtr<AActor> Actor) { } // param should be AActor*
```

---

### F11: BeginPlay Ordering Issues
**Frequency:** Common in multi-Actor setups
**Symptom:** Crash or null reference at BeginPlay, works fine after first frame

**Rule:** BeginPlay order across different Actors is NOT guaranteed.
Never assume another Actor's BeginPlay has run.

```cpp
// WRONG — assumes OtherActor::BeginPlay already ran:
void AMyActor::BeginPlay()
{
    GameManager->RegisterMe(this); // GameManager might not be ready
}

// RIGHT — defer to next tick:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    GetWorldTimerManager().SetTimerForNextTick([this]()
    {
        if (IsValid(GameManager))
            GameManager->RegisterMe(this);
    });
}
```

---

### F12: Circular Dependency / Include Order
**Frequency:** Common as projects grow
**Symptom:** Undefined type errors, compile errors on previously working code

**Fix pattern:**
```cpp
// .h — forward declare instead of include:
class AMyOtherActor; // forward declaration

// .cpp — include here:
#include "MyOtherActor.h"
```

---

### F13: Async/Lambda This Capture Crash
**Frequency:** Common when using async operations
**Symptom:** Crash in async callback, object already destroyed

```cpp
// WRONG:
AsyncTask(ENamedThreads::GameThread, [this]()
{
    this->DoSomething(); // 'this' may be gone
});

// RIGHT:
TWeakObjectPtr<ThisClass> WeakThis(this);
AsyncTask(ENamedThreads::GameThread, [WeakThis]()
{
    if (WeakThis.IsValid())
        WeakThis->DoSomething();
});
```

---

### F14: Server RPC Called From Server
**Frequency:** Common multiplayer mistake
**Symptom:** Server RPC silently does nothing

```cpp
// Server RPCs must be called FROM CLIENT
// Calling from server = silent no-op

// WRONG:
if (HasAuthority())
    ServerDoSomething(); // does nothing on server

// RIGHT on server:
if (HasAuthority())
    ServerDoSomething_Implementation(); // call directly
```

---

### F15: GetAllActorsOfClass in Tick
**Frequency:** Very common performance issue
**Symptom:** FPS drops, profiler shows high game thread time

```cpp
// WRONG — O(n) search every frame:
void Tick(float DeltaTime)
{
    TArray<AActor*> Enemies;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AEnemy::StaticClass(), Enemies);
}

// RIGHT — cache once:
// In BeginPlay or on spawn/destroy events
```

---

## TIER 3 — LESS COMMON (Advanced / Edge cases)

Agent mentions these only when specifically relevant.

---

### F16: Unity Build Hiding Include Errors
**Frequency:** Occasional, confusing when it happens
**Symptom:** Random "undefined type" errors that appear/disappear seemingly randomly

```csharp
// YourProject.Build.cs:
bUseUnity = false; // reveals hidden include errors
```

---

### F17: PostEditChangeProperty BP Component Corruption
**Frequency:** Rare, advanced editor tooling
**Symptom:** Property changes in editor don't persist on BP-spawned components

UE internally duplicates CDO for BP components.
Changes made in PostEditChangeProperty are overwritten by cached data.
Use OnConstruction or PostInitProperties instead for initialization.

---

### F18: IsValid vs != nullptr Subtlety
**Frequency:** Occasional — causes hard to find bugs
**When they differ:**

```cpp
MyActor->Destroy(); // Actor marked as garbage, NOT null yet

MyActor != nullptr  // TRUE  — pointer is not null
IsValid(MyActor)    // FALSE — actor is pending kill / garbage

// Always use IsValid() for UObjects, never just != nullptr
```

---

### F19: TSoftObjectPtr vs TObjectPtr Loading
**Frequency:** Occasional — memory management
**Key difference:**

```cpp
// TObjectPtr — hard reference, asset loaded immediately at startup
UPROPERTY(EditAnywhere)
TObjectPtr<UTexture2D> AlwaysLoadedTexture;

// TSoftObjectPtr — soft reference, loaded on demand
UPROPERTY(EditAnywhere)
TSoftObjectPtr<UTexture2D> LazyLoadedTexture;
// Use for large assets not needed immediately
// Prevents them from inflating startup load time
```

---

### F20: TObjectPtr in USTRUCT GC Trap
**Frequency:** Rare but catastrophic when it happens
**Symptom:** Crash inside struct stored in TArray

```cpp
// USTRUCT with UObject pointer — UPROPERTY required:
USTRUCT()
struct FMyData
{
    GENERATED_BODY()

    UPROPERTY()  // required or GC collects the referenced object
    TObjectPtr<AActor> ReferencedActor;
};

// Note: Nested containers inside USTRUCT cannot be UPROPERTY
// Only the struct itself and simple UObject pointers inside it
```

---

## PROACTIVE SUGGESTION RULES FOR AGENT

When user asks about X → also mention Y:

| User Topic | Proactive Warning |
|---|---|
| Storing Actor/Component reference | UPROPERTY() required (F1) |
| Compiling / build errors | Close editor first, use Live Coding (F2) |
| Calling method on pointer | IsValid() check (F3) |
| Using new UE class | Check Build.cs dependency (F4) |
| Overriding BeginPlay/Tick | Super:: call (F5) |
| Compiler errors (sharing) | Check Output window not Error List (F6) |
| Writing Tick function | bCanEverTick in constructor (F7) |
| Reading UPROPERTY in constructor | Values not set yet, use BeginPlay (F8) |
| ConstructorHelpers | Path format and _C suffix (F9) |
| Async / lambda | TWeakObjectPtr capture (F13) |
| Multiplayer Server RPC | Must call from client (F14) |
| Finding actors each frame | Cache it, don't call in Tick (F15) |
| Large assets / textures | TSoftObjectPtr for lazy loading (F19) |

---

## QUICK FREQUENCY SUMMARY

```
TIER 1 (Everyone hits):
F1  Missing UPROPERTY          ████████████████████ #1
F2  Hot Reload corruption      ███████████████████  #2
F3  Missing IsValid()          ██████████████████   #3
F4  Missing Build.cs module    █████████████████    #4
F5  Missing Super:: call       ████████████████     #5
F6  Error List vs Output       ███████████████      #6
F7  Tick not working           ██████████████       #7

TIER 2 (Common):
F8  UPROPERTY in constructor   █████████            
F9  CDO Constructor failed     ████████             
F10 TObjectPtr misuse          ███████              
F11 BeginPlay ordering         ███████              
F12 Circular dependency        ██████               
F13 Async this capture         ██████               
F14 Server RPC from server     █████                
F15 GetAllActors in Tick       █████                

TIER 3 (Less common):
F16-F20                        ██                   
```
