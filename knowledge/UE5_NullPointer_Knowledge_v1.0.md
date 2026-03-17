# UE5 Null Pointer & Common Crash Patterns
### UE5 Dev Agent — Knowledge v1.0
### Source: Community (most viewed threads)

---

## NULL POINTER — COMPLETE GUIDE

---

### Why Null Pointers Happen in UE5

UE5's Garbage Collector (GC) automatically cleans up UObjects that are no longer referenced.
If you store a pointer to a UObject **without UPROPERTY**, GC can collect it → pointer becomes invalid → crash.

**The golden rule:**
Every UObject pointer stored as a member variable MUST have `UPROPERTY()`.

---

### Pattern 1: Missing UPROPERTY

```cpp
// WRONG — GC can collect MyActor, pointer becomes dangling:
class AMyClass : public AActor
{
    AActor* MyActor; // no UPROPERTY — GC ignores this
};

// RIGHT — GC tracks this pointer, sets to nullptr when actor is destroyed:
class AMyClass : public AActor
{
    UPROPERTY()
    TObjectPtr<AActor> MyActor; // UE5.0+ recommended
    
    // or for older style:
    UPROPERTY()
    AActor* MyActor;
};
```

---

### Pattern 2: Missing IsValid() Check

```cpp
// WRONG — crashes if MyActor was destroyed:
MyActor->DoSomething();

// RIGHT:
if (IsValid(MyActor))
{
    MyActor->DoSomething();
}
```

**IsValid() vs != nullptr:**
```cpp
MyActor != nullptr  // only checks if pointer is non-null
IsValid(MyActor)    // checks non-null AND not pending kill AND not garbage
```

Always use `IsValid()` for UObjects, not just null check.

---

### Pattern 3: Null in BeginPlay — Wrong Initialization Order

```cpp
// WRONG — assumes OtherActor already ran BeginPlay:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    AGameManager* Manager = Cast<AGameManager>(
        UGameplayStatics::GetActorOfClass(GetWorld(), AGameManager::StaticClass()));
    Manager->RegisterActor(this); // crash if Manager hasn't spawned yet
}

// RIGHT — check before use:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    AGameManager* Manager = Cast<AGameManager>(
        UGameplayStatics::GetActorOfClass(GetWorld(), AGameManager::StaticClass()));
    
    if (IsValid(Manager))
    {
        Manager->RegisterActor(this);
    }
}
```

If order dependency is critical, use a timer for next tick:
```cpp
FTimerHandle Handle;
GetWorldTimerManager().SetTimerForNextTick([this]()
{
    // guaranteed to run after all BeginPlay calls
    InitializeAfterAllActors();
});
```

---

### Pattern 4: Null After Cast

```cpp
// Cast returns nullptr if the object is not of that type — ALWAYS check:
AActor* Actor = GetOwner();
AMyCharacter* Character = Cast<AMyCharacter>(Actor);

// WRONG:
Character->DoSomething(); // crash if Actor is not AMyCharacter

// RIGHT:
if (AMyCharacter* Character = Cast<AMyCharacter>(Actor))
{
    Character->DoSomething(); // safe — inside the if block
}
```

---

### Pattern 5: Null in Async / Lambda Capture

```cpp
// WRONG — 'this' could be destroyed before lambda runs:
AsyncTask(ENamedThreads::GameThread, [this]()
{
    this->DoSomething(); // crash if 'this' was garbage collected
});

// RIGHT — use TWeakObjectPtr:
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

### Pattern 6: Null Component

```cpp
// WRONG — CreateDefaultSubobject only works in Constructor:
void AMyActor::BeginPlay()
{
    MyComponent = CreateDefaultSubobject<UMyComponent>(TEXT("MyComp")); // nullptr, doesn't work here
}

// RIGHT — always in Constructor:
AMyActor::AMyActor()
{
    MyComponent = CreateDefaultSubobject<UMyComponent>(TEXT("MyComp"));
}
```

---

### Pattern 7: GetController() Returns Null

```cpp
// GetController() returns null if:
// - Actor is not a Pawn
// - Pawn has no controller assigned yet (before BeginPlay completes)
// - Dedicated server accessing client-owned controller

AController* Controller = GetController(); // can be null

// RIGHT:
if (APlayerController* PC = Cast<APlayerController>(GetController()))
{
    // safe
}
```

---

### Pattern 8: UGameplayStatics Functions Returning Null

```cpp
// All GetActor* functions can return null — actor might not exist:
AGameMode* GM = Cast<AGameMode>(UGameplayStatics::GetGameMode(this));
// GM is null on clients in multiplayer — GameMode is server-only

APlayerController* PC = UGameplayStatics::GetPlayerController(this, 0);
// PC is null if index 0 player hasn't joined yet

// Always check:
if (IsValid(GM)) { ... }
if (IsValid(PC)) { ... }
```

---

### Pattern 9: FindComponentByClass Returns Null

```cpp
UMyComponent* Comp = OtherActor->FindComponentByClass<UMyComponent>();
// Returns null if OtherActor doesn't have that component

// RIGHT:
if (UMyComponent* Comp = OtherActor->FindComponentByClass<UMyComponent>())
{
    Comp->DoSomething();
}
```

---

### Pattern 10: Null After Destroy

```cpp
// After Destroy() is called, pointer is NOT immediately null
// It becomes null after GC runs (up to 60 seconds later)
// IsValid() returns false immediately after Destroy() — use this

MyActor->Destroy();
MyActor != nullptr  // still true — misleading
IsValid(MyActor)    // false immediately — correct check
```

---

## POINTER TYPES — QUICK REFERENCE

| Type | Use For | Notes |
|---|---|---|
| `TObjectPtr<T>` | UObject member variables (UE5.0+) | Recommended default |
| `UPROPERTY() T*` | UObject member variables (legacy) | Still valid |
| `TWeakObjectPtr<T>` | Non-owning reference | Safe across GC, use IsValid() |
| `TStrongObjectPtr<T>` | Prevent GC from collecting | Use carefully |
| Raw `T*` | Local variables, parameters | Never store as member without UPROPERTY |

---

## DEBUGGING NULL POINTER CRASHES

### Step 1: Find the crash location
Look at the callstack in the crash log. Find the first line that's YOUR code (not engine code).

### Step 2: Identify the null pointer
```
Access violation reading location 0x0000000000000000
```
`0x00000000` = null pointer dereference. The pointer was null.

### Step 3: Add logging before the crash
```cpp
UE_LOG(LogTemp, Warning, TEXT("MyActor valid: %s"), IsValid(MyActor) ? TEXT("YES") : TEXT("NO"));
```

### Step 4: Use ensure() to catch before crash
```cpp
if (!ensure(IsValid(MyActor)))
{
    return; // graceful exit instead of crash
}
MyActor->DoSomething();
```

### Step 5: Check UPROPERTY
Is the member variable marked with `UPROPERTY()`?
If not → add it → recompile → test.

---

## COMMON NULL POINTER CHECKLIST

When you get a null pointer crash, go through this list:

- [ ] Is the pointer stored as a member variable? → Does it have `UPROPERTY()`?
- [ ] Is `IsValid()` called before use?
- [ ] Is it used inside an async callback? → Use `TWeakObjectPtr`
- [ ] Is it a Cast result? → Check if Cast succeeded
- [ ] Is it accessed in BeginPlay? → Is the referenced actor guaranteed to exist?
- [ ] Is it a component? → Was it created in Constructor with `CreateDefaultSubobject`?
- [ ] Is it accessed on a client? → Does it only exist on server (GameMode)?
