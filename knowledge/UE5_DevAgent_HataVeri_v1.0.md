# UE5 Common Errors & Crash Database
### UE5 Dev Agent — Knowledge File v1.0

---

## SECTION 1: COMPILER ERRORS

---

### LNK2019 — Unresolved External Symbol

**What it means:**
A function is declared but its definition can't be found. The linker can't resolve the reference.

**Most common causes:**

1. Missing module dependency
```
// Missing from Build.cs:
PublicDependencyModuleNames.AddRange(new string[] { "AIModule" });
```
Fix: Add the required module to Build.cs, rebuild the project.

2. Function not defined in .cpp
```cpp
// In .h:
void MyFunction();
// In .cpp: missing — causes LNK2019
```
Fix: Add the definition to the .cpp file.

3. Missing generated.h after UCLASS macro
```cpp
#include "MyClass.generated.h" // MUST be the last include
```

---

### C2027 — Use of Undefined Type

**What it means:**
A class is used but its full definition isn't visible — only a forward declaration exists.

**Cause:**
```cpp
// Forward declaration in .h:
class AMyActor;
// But a method is called through the pointer — missing include in .cpp
```

**Fix:**
Add `#include "MyActor.h"` to the .cpp file.
If only using a pointer/reference in the header, forward declaration is enough.
If the full type is needed in the header, the include is required.

---

### C4263 / C4264 — Virtual Function Override Warning

**What it means:**
The signature of the function you're trying to override doesn't match the parent class.

**Cause:**
```cpp
// Parent:
virtual void BeginPlay();
// Child (wrong):
void BeginPlay(int32 Param); // different signature — this is a new function, not an override
```

**Fix:**
Use the `override` keyword — the compiler will warn immediately if the signature is wrong:
```cpp
virtual void BeginPlay() override; // correct
```

---

### UHT Error — Missing #include

**What it means:**
Unreal Header Tool can't generate the required file.

**Most common error:**
```
error: Expected #include "MyClass.generated.h" at the end of the include list
```

**Rule:**
`#include "FileName.generated.h"` must always be the last include in the header.

---

### Circular Dependency

**Symptom:**
A.h includes B.h. B.h includes A.h. Build gets stuck.

**Fix:**
Use forward declarations in headers, move includes to .cpp files:
```cpp
// A.h — instead of include:
class BClass; // forward declaration

// A.cpp — include here:
#include "B.h"
```

---

## SECTION 2: CRASH TYPES

---

### Access Violation (0xC0000005)

**Most common UE5 causes:**

**1. Invalid pointer — GC collected it**
```cpp
// WRONG — no UPROPERTY, GC can collect it:
AActor* MyActor;

// CORRECT:
UPROPERTY()
TObjectPtr<AActor> MyActor;
```

**2. Missing IsValid() check**
```cpp
// WRONG:
MyActor->DoSomething();

// CORRECT:
if (IsValid(MyActor))
{
    MyActor->DoSomething();
}
```

**3. Accessing uninitialized object in BeginPlay**
Spawn order is not guaranteed. Don't assume another Actor's BeginPlay has already run.

**4. Deleted object in async callback**
If you use `this` inside a lambda, the object may have been deleted by the time the lambda runs:
```cpp
// WRONG:
AsyncTask(ENamedThreads::GameThread, [this]()
{
    this->DoSomething(); // this may be deleted
});

// CORRECT:
TWeakObjectPtr<UMyClass> WeakThis(this);
AsyncTask(ENamedThreads::GameThread, [WeakThis]()
{
    if (WeakThis.IsValid())
    {
        WeakThis->DoSomething();
    }
});
```

---

### Ensure Condition Failed

**What it means:**
The `ensure()` macro returned false. Not a crash, but a serious warning — something is in an unexpected state.

**Log appearance:**
```
Ensure condition failed: IsValid(MyComponent) [File:MyActor.cpp] [Line: 47]
```

**How to debug:**
- Find the indicated line
- Trace why the object is invalid at that point
- Ensure often appears before the real crash — don't ignore it

**ensure vs check:**
```cpp
ensure(condition);  // False → log + callstack in editor, continue
check(condition);   // False → immediate crash
verify(condition);  // Also runs in Release builds
```

---

### Pure Virtual Function Called

**What it means:**
An abstract function was called without an implementation.

**Most common cause:**
Calling a virtual function from a Constructor or Destructor.
At that point, the vtable is not yet / no longer fully constructed.

**Fix:**
Never call virtual functions from Constructor/Destructor.
Move them to BeginPlay or PostInitializeComponents.

---

### Stack Overflow

**Symptom:**
Callstack cuts off suddenly, engine crashes.

**Most common UE5 cause:**
Infinite recursion — a function calling itself endlessly.

```cpp
void AMyActor::DoSomething()
{
    DoSomething(); // infinite loop
}
```

**Second common cause:**
Creating a very large stack object inside Tick.

---

### Out of Memory / Large Object Allocation

**In log:**
```
Ran out of memory allocating [X] bytes
```

**Common causes:**
- Texture streaming load issues
- Creating objects inside an infinite loop
- TArray or TMap growing without bounds
- Loading assets directly instead of async (should use async load)

**Fix:**
```cpp
// WRONG — loading large asset directly:
UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, TEXT("/Game/..."));

// CORRECT — async load:
StreamableManager.RequestAsyncLoad(AssetPath, FStreamableDelegate::CreateUObject(...));
```

---

## SECTION 3: GAMEPLAY FRAMEWORK ERRORS

---

### BeginPlay Order Issues

**Problem:**
Actor A looks for a reference to Actor B in BeginPlay. B hasn't started yet.

**Solutions:**

1. Use `PostInitializeComponents` — runs before BeginPlay
2. Bind to `OnActorSpawned` delegate
3. Defer BeginPlay:
```cpp
FTimerHandle TimerHandle;
GetWorldTimerManager().SetTimerForNextTick(this, &AMyActor::DelayedBeginPlay);
```

---

### GameMode Null

**Symptom:**
`GetWorld()->GetAuthGameMode()` returns null.

**Cause:**
You're running on the client. GameMode only exists on the server.

**Fix:**
```cpp
// Check first:
if (HasAuthority())
{
    AMyGameMode* GM = GetWorld()->GetAuthGameMode<AMyGameMode>();
}
```

---

### PlayerController Null

**Common mistake:**
```cpp
APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
PC->DoSomething(); // PC may be null
```

**Cause:**
- Wrong index in multiplayer
- Player hasn't joined yet
- Client's PC doesn't exist on server

**Fix:**
Always check IsValid. In multiplayer, use GetLocalPlayerController.

---

### Component Null After Construction

**Problem:**
Component created with CreateDefaultSubobject is null in BeginPlay.

**Cause:**
CreateDefaultSubobject only works inside the Constructor.

```cpp
// WRONG — in BeginPlay:
MyComponent = CreateDefaultSubobject<UMyComponent>(TEXT("MyComp")); // DOESN'T WORK

// CORRECT — in Constructor:
AMyActor::AMyActor()
{
    MyComponent = CreateDefaultSubobject<UMyComponent>(TEXT("MyComp"));
}
```

---

## SECTION 4: MULTIPLAYER ERRORS

---

### Replication Not Working

**Checklist:**
```cpp
// 1. Is replication enabled on the Actor?
AMyActor::AMyActor()
{
    bReplicates = true;
}

// 2. Is UPROPERTY correct on the variable?
UPROPERTY(Replicated)
float MyValue;

// 3. Is GetLifetimeReplicatedProps implemented?
void AMyActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyActor, MyValue);
}
```

---

### RPC Not Being Called

**Cause 1:** Wrong RPC type
```cpp
UFUNCTION(Server, Reliable)      // Client → Server
UFUNCTION(Client, Reliable)      // Server → Client
UFUNCTION(NetMulticast, Reliable) // Server → All clients
```

**Cause 2:** Missing authority check
Only the client can call a Server RPC. If the server calls it, it won't execute.

**Cause 3:** Missing _Implementation
```cpp
// .h:
UFUNCTION(Server, Reliable)
void ServerDoSomething();

// .cpp — _Implementation is REQUIRED:
void AMyActor::ServerDoSomething_Implementation()
{
    // actual code here
}
```

---

## SECTION 5: UE5 NEW SYSTEM ERRORS

---

### Nanite — Mesh Not Supported

**Log:**
```
LogStaticMesh: Warning: [MeshName] has Nanite enabled but is not supported
```

**Unsupported cases:**
- Meshes with vertex animation
- Some meshes using 2-sided materials
- Meshes with morph targets
- Skeletal meshes (Nanite only supports static meshes)

**Fix:**
Disable Nanite in mesh settings, or make the mesh compatible.

---

### Lumen — Lighting Not Updating

**Symptom:**
Light changes but the scene doesn't update — old lighting persists.

**Causes:**
1. You're using Static lights — Lumen requires dynamic lights
2. `r.Lumen.DiffuseIndirect.Allow 0` console variable is set
3. Hardware Lumen is on but GPU doesn't support it → falls back to Software

**Console variables:**
```
r.Lumen.Reflections.Allow 1
r.Lumen.DiffuseIndirect.Allow 1
r.RayTracing.ForceAllRayTracingEffects 0
```

---

### Enhanced Input — Input Not Working

**Most common cause:**
InputMappingContext not added.

```cpp
// In PlayerController or Character BeginPlay:
if (APlayerController* PC = Cast<APlayerController>(GetController()))
{
    if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
        ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
    {
        Subsystem->AddMappingContext(MyMappingContext, 0);
    }
}
```

**Second common cause:**
Input Class in Project Settings still set to the old system.
`Project Settings → Input → Default Input Component Class` must be `EnhancedInputComponent`.

---

### Hot Reload vs Live Coding

**Hot Reload (old, problematic):**
- Risk of crash on header changes
- CDO (Class Default Object) can become corrupted
- Disabled by default in UE5

**Live Coding (new, recommended):**
- Activate with Ctrl+Alt+F11
- Only safe for .cpp changes
- Restart editor after header changes

**"Reinstanced" warning:**
After Live Coding, seeing `BP_MyActor has been reinstanced` is normal —
the Blueprint is reloading the updated C++ class.

---

## SECTION 6: PERFORMANCE ISSUES

---

### Tick Optimization

**Problem:**
Every Actor runs Tick every frame by default.

**Fix — disable if not needed:**
```cpp
AMyActor::AMyActor()
{
    PrimaryActorTick.bCanEverTick = false; // Tick completely disabled
}
```

**Reduce Tick interval:**
```cpp
PrimaryActorTick.TickInterval = 0.1f; // Once every 100ms
```

---

### GetAllActorsOfClass — Expensive Call

```cpp
// WRONG — every frame:
void AMyActor::Tick(float DeltaTime)
{
    TArray<AActor*> Actors;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AEnemy::StaticClass(), Actors);
}
```

**Fix:**
- Call once in BeginPlay, cache the result
- Or maintain a central list in GameState
- Or use overlap/collision to find nearby actors

---

### Blueprint Callable Overhead

C++ functions called from Blueprint carry overhead.
Avoid `BlueprintCallable` in performance-critical code (inside Tick).

---

## SECTION 7: LOG READING GUIDE

---

### Log Severity Levels

```
Fatal    → Engine stops, crash
Error    → Serious problem, may continue but something isn't working
Warning  → Should be addressed, working for now
Display  → Informational message
Log      → Normal log
Verbose  → Detailed debug
```

### Crash Log Structure

```
[Time] LogCrashHandler: Error: === Critical error ===
[Time] LogCrashHandler: Error: Fatal error!
[Time] LogCrashHandler: Error: [Error description]
[Time] 0x... [Module] [Function name] [File:Line]
```

**Reading the callstack:**
The topmost line is where the crash occurred.
Going down shows the calling functions.
Find your own code (skip engine code) — start there.

---

*This database is a UE5 Dev Agent knowledge file. Updated as new errors are encountered.*
