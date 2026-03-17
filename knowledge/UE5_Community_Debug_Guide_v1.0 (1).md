# UE5 Community Crash & Debug Guide
### UE5 Dev Agent — Knowledge v1.0
### Source: Unreal Slackers Discord, Epic Forums, Community Research

---

## CRITICAL: HOT RELOAD WARNING

**Hot Reload corrupts blueprints. Do not use it.**

Hot Reload occurs when you compile while the editor is open.
It can corrupt your entire Blueprint hierarchy silently.
If you save after a Hot Reload corruption — you save the corruption permanently.

**The only fix for a corrupted Blueprint: delete it and recreate from scratch.**

**Rules:**
- Always close the editor before compiling in your IDE
- OR enable Live Coding (disables Hot Reload automatically)
- Never press Compile in editor while making structural C++ changes

```
// Live Coding shortcut:
Ctrl + Alt + F11
```

**Hot Reload vs Live Coding:**
- Hot Reload = dangerous, corrupts BPs, avoid completely
- Live Coding = safe for .cpp changes, still requires editor restart for header changes

---

## VISUAL STUDIO SETUP

### Use Output Window, NOT Error List

The Error List in Visual Studio shows unreliable intellisense noise.
**Always use the Output window for real compiler errors.**

```
View > Output  (or Alt + 2)
```

The Output window shows:
- Actual compiler errors only
- Correct file and line number
- No false positives

**Recommended: Disable Error List window entirely.**
Epic's own documentation recommends this.

### Unity Build — Disable for Better Error Detection

By default UE batches files together (Unity Build), which hides missing include errors.

```csharp
// YourProject.Build.cs — add this:
bUseUnity = false;
```

Without this, missing includes may only show up randomly when Unity Build changes its batching.

---

## ACCESS VIOLATION — COMPLETE DIAGNOSIS GUIDE

### Memory Address Near Zero = Null Pointer
```
Exception thrown: read access violation.
'X' was 0x00000018.  ← address close to 0 = null pointer
```
The pointer itself is null. Someone called a function on a null object.

### Memory Address Random/Far From Zero = GC Crash
```
Exception thrown: read access violation.
'X' was 0x7FF932B37BB7.  ← random address = dangling pointer (GC collected it)
```
The pointer was valid, GC cleaned up the object, pointer now points to garbage.

---

### Null Pointer Fixes

**Always check before use:**
```cpp
// WRONG:
APlayerController* PC = GetWorld()->GetFirstPlayerController();
PC->SetViewTarget(this); // crash if PC is null

// RIGHT — assert approach (crash early, find root cause):
APlayerController* PC = GetWorld()->GetFirstPlayerController();
ensure(PC != nullptr); // breaks in debugger if null, shows exact location
PC->SetViewTarget(this);

// RIGHT — conditional approach (only if null is acceptable):
if (APlayerController* PC = GetWorld()->GetFirstPlayerController())
{
    PC->SetViewTarget(this);
}
```

**Important:** Don't just add null checks to hide the problem.
Fix the root cause — why is it null in the first place?

---

### GC Crash Fixes

**Missing UPROPERTY — most common GC crash:**
```cpp
// WRONG — GC doesn't know you're using this, collects it:
UCameraComponent* CamComponent;

// RIGHT — UPROPERTY tells GC to keep it alive:
UPROPERTY()
UCameraComponent* CamComponent;

// UE5 recommended:
UPROPERTY()
TObjectPtr<UCameraComponent> CamComponent;
```

**Rule:** Every UObject pointer stored as a member variable needs `UPROPERTY()`.

---

## COMPILER ERRORS

### LNK2019 — Unresolved External Symbol

**Cause 1: Missing module dependency**

Find which module the class belongs to:
1. Google: `[ClassName] unreal engine documentation`
2. On the docs page, find "Module:" in the header
3. Add that module to Build.cs

```csharp
// YourProject.Build.cs
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core", "CoreUObject", "Engine", "InputCore",
    "UMG",        // for UUserWidget
    "AIModule",   // for AI classes
    "GameplayAbilities", // for GAS
    // add whatever module is missing
});
```

**Cause 2: Missing function implementation**
```cpp
// .h — declared:
void MyFunction();

// .cpp — body missing → LNK2019
// Fix: add the body
void AMyClass::MyFunction()
{
    // implementation
}
```

**Cause 3: Class not exported**
If the class has no `MODULENAME_API` in its declaration → it's not exported.
Find an alternative class or approach.

---

### C2027 — Use of Undefined Type

```
error C2027: use of undefined type 'UUserWidget'
```

**In .cpp files — add the include:**
```cpp
#include "Blueprint/UserWidget.h"
```

**In .h files — use forward declaration instead:**
```cpp
// .h — forward declare (avoids circular dependencies, faster compile):
class UUserWidget;

// .cpp — include here:
#include "Blueprint/UserWidget.h"
```

Forward declaration works when you only use pointers to the type.
If you need to call methods or know the size → full include required.

---

### GENERATED_BODY Deprecation Warning

Old tutorials use deprecated macros:
```cpp
GENERATED_UCLASS_BODY()  // deprecated
GENERATED_USTRUCT_BODY() // deprecated
```

Always use:
```cpp
GENERATED_BODY()
```

Difference: old macros added `public:` automatically, new one doesn't.
Add `public:` manually after `GENERATED_BODY()`.

---

## TICK NOT BEING CALLED

Two things required for Tick to work:

**1. Constructor setup:**
```cpp
AMyActor::AMyActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.bStartWithTickEnabled = true; // must be true to start ticking
}
```

**2. Super::BeginPlay() call:**
```cpp
void AMyActor::BeginPlay()
{
    Super::BeginPlay(); // MUST be called — forgetting this breaks Tick
    // your code
}
```

If both are correct and Tick still doesn't fire → check if the Actor is spawned and active in the world.

---

## DEBUGGING — STEP BY STEP

### Setup for Meaningful Debugging

**Step 1: Set build configuration to DebugGame Editor**
Development Editor optimizes code away — breakpoints jump randomly.
DebugGame Editor preserves variable values and line accuracy.

**Step 2: Install Editor Debug Symbols**
Without symbols, callstack shows only `UnrealEditor_UnrealEd Unknown Unknown`.

```
Epic Games Launcher → Engine version → Options →
Check "Editor symbols for debugging" → Apply
```

**Step 3: Place breakpoint**
Click left gutter in VS → red dot appears.
Or: select line → F9

**Step 4: Launch with debugger**
F5 in Visual Studio — launches editor with VS attached.
Orange bar at bottom = VS attached.

**Step 5: Navigate**
- F10 = step over (next line)
- F11 = step into (enter function)
- F5 = continue to next breakpoint
- Hover variable = see value
- Locals/Autos tab = all local variables

### Reading Callstacks

**Good callstack (symbols installed):**
```
AMyActor::BeginPlay() [MyActor.cpp:47]
AActor::DispatchBeginPlay() [Actor.cpp:3821]
UWorld::BeginPlay() [World.cpp:...)
```
→ Your code is at the top. Start there.

**Bad callstack (no symbols):**
```
UnrealEditor_UnrealEd
UnrealEditor_CoreUObject
UnrealEditor
```
→ Install debug symbols first.

**Finding your code in callstack:**
Scroll past engine functions until you see your project name.
That's where to start investigating.

---

## UPROPERTY QUICK REFERENCE

```cpp
UPROPERTY()                    // GC tracking only
UPROPERTY(EditAnywhere)        // editable in any Blueprint/editor
UPROPERTY(EditDefaultsOnly)    // editable only in default Blueprint
UPROPERTY(VisibleAnywhere)     // visible but not editable
UPROPERTY(BlueprintReadWrite)  // read/write from Blueprint
UPROPERTY(BlueprintReadOnly)   // read-only from Blueprint
UPROPERTY(Replicated)          // replicated in multiplayer
UPROPERTY(SaveGame)            // included in save game serialization
```

**Performance note:**
`EditAnywhere` on large containers (TArray, TMap) can slow down the editor significantly.
Use `VisibleAnywhere` or no specifier if designer editing isn't needed.

---

## COMMON BEGINNER MISTAKES — QUICK LIST

| Mistake | Fix |
|---|---|
| UObject pointer without UPROPERTY | Add `UPROPERTY()` |
| No null check before pointer use | `if (IsValid(ptr))` or `ensure()` |
| Compiling with editor open | Close editor first, or use Live Coding |
| Reading Error List instead of Output | Use Output window (Alt+2) |
| GENERATED_UCLASS_BODY() | Replace with GENERATED_BODY() |
| Super::BeginPlay() missing | Add it as first line of BeginPlay |
| Tick not working | Check `bCanEverTick = true` in constructor |
| LNK2019 error | Add module to Build.cs |
| Undefined type error | Add include to .cpp, forward declare in .h |
| Unity Build hiding errors | Set `bUseUnity = false` in Build.cs |
| DebugGame config not set | Switch to DebugGame Editor in VS |
| No debug symbols | Install via Epic Launcher |

---

## ENSURE vs CHECK vs VERIFY

```cpp
ensure(condition)
// False → logs callstack, continues execution
// Use: "This shouldn't happen but game can recover"
// Only triggers once per unique location

ensureMsgf(condition, TEXT("My message %s"), *SomeString)
// Same as ensure but with custom message

check(condition)
// False → immediate crash (like assert)
// Use: "This MUST be true, game cannot continue"
// Always active in all build configs

checkf(condition, TEXT("Message"))
// Same as check with message

verify(condition)
// Like check but expression is always evaluated
// Use when the expression has side effects

ensureAlwaysMsgf(condition, TEXT("Message"))
// Like ensure but triggers every time (not just once)
```

**When to use which:**
- `ensure` — expected to be true, want to know if not, game can survive
- `check` — must be true, game logic is broken if not
- `if (IsValid())` — null is an acceptable runtime state

---

## USTRUCT IN TARRAY — GC TRAP

```cpp
// WRONG — pointer inside struct without UPROPERTY:
USTRUCT()
struct FBall
{
    GENERATED_BODY()
    ABallActor* BallActor; // no UPROPERTY — GC can collect BallActor
};

TArray<FBall> Balls;

// RIGHT:
USTRUCT()
struct FBall
{
    GENERATED_BODY()

    UPROPERTY()
    TObjectPtr<ABallActor> BallActor; // GC tracks this
};
```

Structs stored in TArrays must have UPROPERTY on any UObject pointers inside them.
Nested containers cannot be marked UPROPERTY — only the struct itself can be.
