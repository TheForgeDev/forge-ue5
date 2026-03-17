# UE5 C++ Comprehensive Error Handbook
### UE5 Dev Agent — Knowledge v2.0
### Categories: Memory · Compiler · Runtime · Animation · UI/Input · Multiplayer · Shipping · Build

---

## CHAPTER 1: MEMORY & GARBAGE COLLECTION

---

### M1 — Missing UPROPERTY (Most Common Crash)
**Tier:** 1 — Every developer hits this
**Symptom:** Random crash minutes after startup. Access violation with non-zero address.

```cpp
// DANGER:
UCameraComponent* Camera;      // GC will collect this silently

// SAFE — UE5 recommended:
UPROPERTY()
TObjectPtr<UCameraComponent> Camera;
```

**How GC decides what to keep:**
- Object referenced by UPROPERTY → kept alive
- Object referenced by raw pointer → GC ignores it, may collect
- Object referenced by TWeakObjectPtr → kept alive but returns null when collected

**UObject creation rules:**
```cpp
// ALWAYS use these — never use `new` for UObjects:
NewObject<UMyClass>(Outer)          // for UObjects
SpawnActor<AMyActor>(...)           // for Actors
CreateDefaultSubobject<T>(Name)     // for components in Constructor only
```

---

### M2 — IsValid() vs != nullptr
**Tier:** 1
**Why they differ:**

```cpp
MyActor->Destroy();

MyActor != nullptr   // TRUE  — pointer not null yet
IsValid(MyActor)     // FALSE — actor is pending kill

// GC clears pointer fully after ~60 seconds
// In the meantime, always use IsValid() not nullptr check
```

**TSoftObjectPtr validity checks:**
```cpp
// Three states of soft pointers:
MyObject.IsNull()    // has no reference at all
MyObject.IsPending() // references unloaded asset
MyObject.IsValid()   // references loaded, valid object
```

---

### M3 — NewObject Outer Chain
**Tier:** 2
**Symptom:** Object unexpectedly garbage collected even with UPROPERTY

```cpp
// WRONG — null outer, GC may collect:
UMyObject* Obj = NewObject<UMyObject>();

// RIGHT — set outer to keep object in correct hierarchy:
UMyObject* Obj = NewObject<UMyObject>(this); // 'this' as outer
```

Outer chain determines lifetime. If outer is collected → inner collected too.

---

### M4 — Memory Leak: UObject Not Destroyed
**Tier:** 2
**Symptom:** RAM increases over time during gameplay

**Common causes:**
- Actor never destroyed after use (spawn but forget)
- Delegate reference keeping object alive
- TStrongObjectPtr preventing GC

```cpp
// Actors must be explicitly destroyed:
MyActor->Destroy(); // marks for GC
// OR
MyActor->SetLifeSpan(5.0f); // auto-destroy after 5 seconds

// Check for leaks with:
// stat memory
// memreport -full (in console)
```

---

### M5 — USTRUCT UObject Pointer Without UPROPERTY
**Tier:** 2
**Symptom:** Crash inside struct stored in TArray

```cpp
// WRONG:
USTRUCT()
struct FMyData
{
    GENERATED_BODY()
    AActor* CachedActor; // no UPROPERTY — GC collects CachedActor
};

// RIGHT:
USTRUCT()
struct FMyData
{
    GENERATED_BODY()
    UPROPERTY()
    TObjectPtr<AActor> CachedActor;
};
```

---

### M6 — Hard vs Soft References Asset Loading
**Tier:** 2
**Symptom:** Long load times, high memory usage

```cpp
// HARD reference — loads at startup, always in memory:
UPROPERTY(EditAnywhere)
TObjectPtr<UTexture2D> AlwaysLoaded; // bad for large assets

// SOFT reference — loads on demand:
UPROPERTY(EditAnywhere)
TSoftObjectPtr<UTexture2D> LazyLoaded;

// Load soft reference:
UTexture2D* Tex = LazyLoaded.LoadSynchronous(); // blocking
// OR async:
UAssetManager::GetStreamableManager().RequestAsyncLoad(
    LazyLoaded.ToSoftObjectPath(),
    FStreamableDelegate::CreateUObject(this, &AMyActor::OnLoaded));
```

Use soft references for: large textures, meshes, sounds not needed at startup.

---

## CHAPTER 2: COMPILER & BUILD ERRORS

---

### C1 — LNK2019 Unresolved External Symbol
**Tier:** 1
**Symptom:** Linker error, project won't compile

**Step 1:** Identify the class from the error message
**Step 2:** Find its module in Epic docs (search class name → "Module:" field)
**Step 3:** Add to Build.cs

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core", "CoreUObject", "Engine", "InputCore", // defaults
    "UMG",                  // UUserWidget, Slate widgets
    "AIModule",             // AAIController, navigation
    "GameplayAbilities",    // GAS
    "GameplayTasks",        // GAS tasks
    "GameplayTags",         // FGameplayTag
    "NavigationSystem",     // UNavigationSystemV1
    "Niagara",              // UNiagaraSystem, UNiagaraComponent
    "PhysicsCore",          // Physics classes
    "ChaosVehicles",        // Chaos vehicle
    "EnhancedInput",        // Enhanced Input
    "InputCore",            // FKey
    "SlateCore", "Slate",   // Slate UI
    "MovieScene",           // Sequencer
    "MediaAssets",          // Media player
    "Json", "JsonUtilities", // JSON parsing
    "HTTP",                 // HTTP requests
    "OnlineSubsystem",      // Online features
});
```

---

### C2 — UHT / GENERATED_BODY Errors
**Tier:** 1

**generated.h must be last include:**
```cpp
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "MyActor.generated.h" // ALWAYS LAST
```

**Use GENERATED_BODY(), not old macros:**
```cpp
GENERATED_UCLASS_BODY()  // deprecated
GENERATED_USTRUCT_BODY() // deprecated
GENERATED_BODY()         // correct — use this always
```

---

### C3 — Circular Dependency
**Tier:** 2
**Symptom:** Compile errors on previously working code, undefined type

```cpp
// .h — forward declare instead of include:
class AMyOtherActor; // one line, no include needed

// .cpp — full include here:
#include "MyOtherActor.h"
```

Forward declaration works when:
- Using pointer to the type: `AMyOtherActor*`
- Using reference: `AMyOtherActor&`

Full include required when:
- Inheriting from the type
- Calling methods on it in header
- Using it by value (not pointer)

---

### C4 — Unity Build Hiding Errors
**Tier:** 3
**Symptom:** Undefined type errors appear randomly, disappear when code is unchanged

```csharp
// YourProject.Build.cs:
bUseUnity = false; // exposes hidden include errors
```

---

### C5 — CDO Constructor Failed to Find
**Tier:** 2
**Symptom:** "CDO Constructor: Failed to find /Game/..." in log

```cpp
// Class finder — requires _C suffix:
static ConstructorHelpers::FClassFinder<APawn> PawnClass(
    TEXT("/Game/BP_MyCharacter.BP_MyCharacter_C")); // _C required

// Object finder — NO _C for assets:
static ConstructorHelpers::FObjectFinder<UStaticMesh> MeshAsset(
    TEXT("/Game/Meshes/SM_Rock.SM_Rock")); // no _C

// Check validity:
if (PawnClass.Succeeded())
    DefaultPawnClass = PawnClass.Class;
```

**ConstructorHelpers only work in Constructor** — never in BeginPlay or other functions.

---

## CHAPTER 3: RUNTIME CRASHES

---

### R1 — Access Violation Diagnosis
**Tier:** 1

**Address near zero (0x00 - 0xFF):** Null pointer
```
Exception: read access violation — 'X' was 0x00000018
→ Null pointer. Someone called method on nullptr.
→ Fix: Add IsValid() check before the call.
```

**Random high address:** GC collected the object
```
Exception: read access violation — 'X' was 0x7FF932B37BB7
→ Dangling pointer. GC collected UObject, pointer still used.
→ Fix: Add UPROPERTY() to the member variable.
```

---

### R2 — BeginPlay Ordering
**Tier:** 2
**Symptom:** Crash at BeginPlay when accessing another actor

BeginPlay order across actors is **not guaranteed**.
Never assume another Actor's BeginPlay ran first.

```cpp
// WRONG — assumes OtherActor ready:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    GameManager->RegisterMe(this); // GameManager may not exist yet
}

// RIGHT — defer one tick:
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

### R3 — Async Lambda This Capture
**Tier:** 2

```cpp
// WRONG — 'this' may be destroyed before lambda runs:
AsyncTask(ENamedThreads::GameThread, [this]()
{
    this->DoSomething(); // crash if 'this' was GC'd
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

### R4 — Pure Virtual Function Called
**Tier:** 2
**Symptom:** "Pure virtual function called" crash, usually at startup

**Cause:** Calling virtual function in Constructor or Destructor.
At that moment, vtable is incomplete.

```cpp
// WRONG:
AMyActor::AMyActor()
{
    Initialize(); // if Initialize() is virtual — crash risk
}

// RIGHT — defer to BeginPlay or PostInitializeComponents:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    Initialize(); // safe here
}
```

---

### R5 — Component Null After Construction
**Tier:** 1

```cpp
// WRONG — CreateDefaultSubobject only works in Constructor:
void AMyActor::BeginPlay()
{
    MyComp = CreateDefaultSubobject<UMyComponent>(TEXT("Comp")); // nullptr
}

// RIGHT:
AMyActor::AMyActor()
{
    MyComp = CreateDefaultSubobject<UMyComponent>(TEXT("Comp")); // only here
}
```

---

### R6 — UPROPERTY Read in Constructor
**Tier:** 2
**Symptom:** Value always default, editor changes ignored

UPROPERTY values are written **after** constructor returns.

```cpp
// WRONG — values not set yet:
AMyActor::AMyActor()
{
    FVector Pos = MyEditableVector; // always zero
}

// RIGHT:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    FVector Pos = MyEditableVector; // values are set here
}

// PostInitProperties is another safe place — called after UPROPERTY values set:
void AMyActor::PostInitProperties()
{
    Super::PostInitProperties();
    FVector Pos = MyEditableVector; // safe
}
```

---

## CHAPTER 4: ANIMATION ERRORS

---

### A1 — T-Pose in Game (AnimBP Not Updating)
**Tier:** 1 — Very common
**Symptom:** Character stuck in T-pose, AnimBP preview works fine

**Checklist:**
```
1. SkeletalMeshComponent → Animation Mode → Use Animation Blueprint
2. AnimBP class assigned correctly to the component
3. Mesh and AnimBP use the same skeleton
4. Super::BeginPlay() called in Character
```

**C++ setup:**
```cpp
// Assign AnimBP in constructor:
static ConstructorHelpers::FClassFinder<UAnimInstance> AnimBP(
    TEXT("/Game/Animations/ABP_MyCharacter.ABP_MyCharacter_C"));
if (AnimBP.Succeeded())
    GetMesh()->SetAnimInstanceClass(AnimBP.Class);
```

---

### A2 — AnimInstance Null in C++
**Tier:** 2
**Symptom:** Crash when accessing AnimInstance

```cpp
// WRONG:
UMyAnimInstance* Anim = Cast<UMyAnimInstance>(GetMesh()->GetAnimInstance());
Anim->MyVariable = true; // crash if Anim is null

// RIGHT:
if (UMyAnimInstance* Anim = Cast<UMyAnimInstance>(GetMesh()->GetAnimInstance()))
{
    Anim->MyVariable = true;
}
```

AnimInstance is null if:
- Mesh has no AnimBP assigned
- Called before BeginPlay
- Cast fails (wrong AnimBP type)

---

### A3 — AnimBP Not Thread Safe Warning
**Tier:** 2
**Symptom:** Warning: "BlueprintUpdateAnimation is not thread safe"

AnimBP update runs on worker thread by default in UE5.
Accessing game thread objects directly causes issues.

```cpp
// Use NativeThreadSafeUpdateAnimation for thread-safe updates:
virtual void NativeThreadSafeUpdateAnimation(float DeltaSeconds) override;

// Or use Property Access system instead of direct casts
// in Animation Blueprint's BlueprintThreadSafeUpdateAnimation
```

---

### A4 — Montage Not Playing
**Tier:** 2
**Common causes:**

```cpp
// 1. Slot not in AnimBP — add DefaultSlot node in Anim Graph

// 2. PlayMontage returns 0 — check:
float Duration = AnimInstance->Montage_Play(MyMontage);
if (Duration <= 0.f)
{
    UE_LOG(LogTemp, Warning, TEXT("Montage failed to play"));
    // Check: AnimBP assigned? Montage valid? Slot exists?
}

// 3. Interruption — another montage playing:
AnimInstance->Montage_Stop(0.2f); // stop current first
AnimInstance->Montage_Play(MyMontage);

// 4. Wrong mesh — playing on wrong SkeletalMeshComponent
```

---

### A5 — Hot Reload Corrupting AnimBP
**Tier:** 1
**Symptom:** AnimBP randomly broken after compile

Same as Blueprint corruption — Hot Reload is the cause.
AnimBPs are especially vulnerable.
Always use Live Coding or close editor before compiling.

---

## CHAPTER 5: UI & INPUT ERRORS

---

### U1 — Enhanced Input Not Firing
**Tier:** 1 — Very common since UE5.1

**Full setup checklist:**

```cpp
// Step 1: Project Settings
// Input → Default Player Input Class → EnhancedPlayerInput
// Input → Default Input Component Class → EnhancedInputComponent

// Step 2: Add MappingContext in Character or PlayerController BeginPlay:
void AMyCharacter::BeginPlay()
{
    Super::BeginPlay();
    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
            ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(
                PC->GetLocalPlayer()))
        {
            Subsystem->AddMappingContext(MyMappingContext, 0);
        }
    }
}

// Step 3: Bind actions (in SetupPlayerInputComponent):
void AMyCharacter::SetupPlayerInputComponent(UInputComponent* InputComponent)
{
    Super::SetupPlayerInputComponent(InputComponent);
    if (UEnhancedInputComponent* EI = Cast<UEnhancedInputComponent>(InputComponent))
    {
        EI->BindAction(JumpAction, ETriggerEvent::Started, this, &AMyCharacter::Jump);
    }
}
```

**UE5.5 Breaking Change:**
Enhanced Input Action events on UI child classes may not fire.
Workaround: bind directly on parent class.

---

### U2 — Input Blocked by Widget
**Tier:** 2
**Symptom:** Game input stops working when UI is visible

```cpp
// Widget consuming all input — set focus mode:
MyWidget->SetIsFocusable(false); // widget won't consume keyboard input

// OR set input mode:
APlayerController* PC = GetOwningPlayer();
FInputModeGameAndUI InputMode;
InputMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
PC->SetInputMode(InputMode);

// When closing UI, restore game input:
PC->SetInputMode(FInputModeGameOnly());
```

---

### U3 — Widget Null on First Frame
**Tier:** 2
**Symptom:** NullReferenceException accessing widget components

```cpp
// Widgets created by CreateWidget are valid immediately
// But child widgets may not be bound yet

// WRONG — accessing in constructor:
AMyHUD::AMyHUD()
{
    MyWidget = CreateWidget<UMyWidget>(GetWorld(), WidgetClass);
    MyWidget->MyButton->OnClicked.AddDynamic(...); // button may be null
}

// RIGHT — access in BeginPlay after widget is added to viewport:
void AMyHUD::BeginPlay()
{
    Super::BeginPlay();
    MyWidget = CreateWidget<UMyWidget>(GetOwningPlayerController(), WidgetClass);
    MyWidget->AddToViewport();
    // Now child widgets are bound and accessible
    MyWidget->MyButton->OnClicked.AddDynamic(...);
}
```

---

### U4 — UMG Binding Performance Warning
**Tier:** 2
**Symptom:** "Widget binding is causing performance issues" warning

UMG Bindings (function bindings in Blueprint) run every tick.
For frequently updated values — use events instead.

```cpp
// C++ — broadcast delegate when value changes:
UPROPERTY(BlueprintAssignable)
FOnHealthChanged OnHealthChanged;

// Call when health changes:
OnHealthChanged.Broadcast(NewHealth);

// Widget binds to event — updates only when needed
```

---

## CHAPTER 6: MULTIPLAYER ERRORS

---

### MP1 — Server RPC Silent Fail
**Tier:** 2
**Symptom:** Server RPC does nothing, no crash, no error

Server RPCs must be called **from the owning client**.
Called from server → silent no-op.

```cpp
// WRONG — calling Server RPC on server:
if (HasAuthority())
    ServerDoSomething(); // does nothing

// RIGHT — call implementation directly on server:
if (HasAuthority())
    ServerDoSomething_Implementation();
```

---

### MP2 — Missing _Implementation
**Tier:** 1 — Multiplayer beginners always hit this

```cpp
// Declaration in .h:
UFUNCTION(Server, Reliable)
void ServerDoSomething();

// .cpp — _Implementation suffix is MANDATORY:
void AMyActor::ServerDoSomething_Implementation()
{
    // actual code
}

// Optional validation:
bool AMyActor::ServerDoSomething_Validate()
{
    return true; // return false to kick client
}
```

---

### MP3 — Variable Not Replicating
**Tier:** 2

```cpp
// Three things required:
// 1. Actor must replicate:
AMyActor::AMyActor() { bReplicates = true; }

// 2. Variable must be marked:
UPROPERTY(Replicated)
float Health;

// 3. GetLifetimeReplicatedProps must be implemented:
void AMyActor::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(AMyActor, Health);
}
```

---

### MP4 — OnRep Not Called on Server
**Tier:** 2
**Symptom:** Logic runs on clients but not on server

OnRep functions only fire **on clients** when value changes via replication.
Server sets the value, doesn't receive OnRep.

```cpp
void AMyActor::SetHealth(float NewHealth)
{
    if (HasAuthority())
    {
        Health = NewHealth;
        OnRep_Health(); // manually call on server
    }
}
void AMyActor::OnRep_Health() { /* runs automatically on clients */ }
```

---

## CHAPTER 7: SHIPPING BUILD ISSUES

---

### S1 — Works in Editor, Crashes in Shipping
**Tier:** 2 — The hardest to debug

**Most common causes:**

```
1. Check / Ensure macros disabled in shipping
   → check() becomes no-op, null pointer not caught early
   → Code after check() assumes precondition was met

2. WITH_EDITOR code running in shipping
   → #if WITH_EDITOR blocks compile out
   → Variables/objects only initialized inside those blocks

3. Optimization differences
   → Shipping uses aggressive optimization
   → Uninitialized variables may have different values
   → Race conditions hidden in debug appear in shipping

4. Log macros disabled
   → UE_LOG compiles out → log-only null checks hidden
```

**Debug shipping crashes:**
```
Crash .dmp file location:
C:/Users/<Username>/AppData/Local/<GameName>/Saved/Crashes/

Tools needed:
- .exe from shipping build
- .pdb file from same build (keep it!)  
- .dmp file from crash
- Rider or Visual Studio → Native Core Dump debug
```

---

### S2 — Editor-Only Code in Shipping
**Tier:** 2

```cpp
// This code compiles out in shipping:
#if WITH_EDITOR
void AMyActor::EditorOnlyFunction() { }
#endif

// WRONG — calling editor-only function unconditionally:
void AMyActor::BeginPlay()
{
    EditorOnlyFunction(); // shipping crash — function doesn't exist
}

// RIGHT:
void AMyActor::BeginPlay()
{
#if WITH_EDITOR
    EditorOnlyFunction();
#endif
}
```

---

### S3 — Check/Ensure Differences Across Configs
**Tier:** 2

```
Config behavior:
DEBUG          → check() crashes, ensure() breaks debugger
DEBUGGAME      → check() crashes, ensure() breaks debugger  
DEVELOPMENT    → check() crashes, ensure() logs only
SHIPPING       → check() disabled (NO-OP), ensure() disabled

This means:
- In debug: null caught immediately at check()
- In shipping: null passes check(), crashes later with cryptic address
```

**Solution:** Never rely on check() as your only guard in hot paths.
Add IsValid() or explicit null handling that survives shipping.

---

## CHAPTER 8: DEBUGGING TOOLS & WORKFLOW

---

### D1 — Build Configuration Guide

| Config | Speed | check() | ensure() | Use When |
|---|---|---|---|---|
| Debug Editor | Slowest | crash | debugger | Engine source debugging |
| DebugGame Editor | Slow | crash | debugger | **Your C++ debugging** |
| Development Editor | Fast | crash | log | Normal development |
| Shipping | Fastest | disabled | disabled | Release / performance test |

**Always use DebugGame Editor when debugging crashes.**
Development Editor optimizes code, breakpoints jump around.

---

### D2 — Installing Debug Symbols
Without symbols, callstack shows only `UnrealEditor_UnrealEd Unknown`.

```
Epic Games Launcher
→ Your UE version
→ Options (gear icon)
→ Check "Editor symbols for debugging"
→ Apply
```

---

### D3 — Useful Console Commands

```
// Memory:
stat memory              // memory usage overview
memreport -full          // detailed memory report → Saved/Profiling/

// Performance:
stat fps                 // framerate
stat unit                // frame, game, render, GPU times
stat game                // game thread breakdown
stat gpu                 // GPU breakdown

// Networking:
stat net                 // packets, bandwidth
netdebug                 // network debug info

// Rendering:
r.VisualizeBuffer        // visualize render passes
ShowFlag.Lumen 0/1       // toggle Lumen
r.Nanite.Visualize       // Nanite debug

// GC:
obj gc                   // force garbage collection
obj refs classname=MyClass  // show what references MyClass
```

---

### D4 — Custom Log Categories

```cpp
// .h — declare category:
DECLARE_LOG_CATEGORY_EXTERN(LogMyGame, Log, All);

// .cpp — define:
DEFINE_LOG_CATEGORY(LogMyGame);

// Usage:
UE_LOG(LogMyGame, Warning, TEXT("Health: %f"), Health);
UE_LOG(LogMyGame, Error, TEXT("Actor %s is null"), *GetName());

// Compile out in shipping:
UE_LOG(LogMyGame, VeryVerbose, TEXT("Tick")); // compiles out in shipping

// Screen display (debug only):
GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::Red,
    FString::Printf(TEXT("Health: %f"), Health));
```

---

## QUICK LOOKUP INDEX

| Error Message | Chapter | Entry |
|---|---|---|
| Access violation 0x000000xx | Ch.3 | R1 |
| Access violation 0x7FF...xxx | Ch.1 | M1 |
| LNK2019 unresolved external | Ch.2 | C1 |
| CDO Constructor failed | Ch.2 | C5 |
| Pure virtual function called | Ch.3 | R4 |
| T-pose in game | Ch.4 | A1 |
| Enhanced input not firing | Ch.5 | U1 |
| Server RPC not working | Ch.6 | MP1 |
| Variable not replicating | Ch.6 | MP3 |
| Works in editor, crashes shipping | Ch.7 | S1 |
| Tick not called | Quick ref | bCanEverTick |
| Hot Reload corruption | Ch.2/Ch.4 | C2, A5 |
| Widget null crash | Ch.5 | U3 |
| AnimBP T-pose | Ch.4 | A1 |
| Async callback crash | Ch.3 | R3 |
