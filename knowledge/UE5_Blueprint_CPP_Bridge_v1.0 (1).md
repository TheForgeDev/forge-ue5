# UE5 Blueprint ↔ C++ Bridge — Knowledge Guide v1.0

---

## 1. CORE CONCEPT — UHT (Unreal Header Tool)

The bridge between Blueprint and C++ is built by the **Unreal Header Tool (UHT)**. Before compiling your code, UHT scans header files, processes macros, and generates the `MyClass.generated.h` file. This means:

- `#include "MyClass.generated.h"` is required as the last include in every header
- After macro changes, Live Coding isn't enough — Full Rebuild is required
- UHT errors usually appear a few lines above the actual error line

---

## 2. UCLASS MACROS — MAKING CLASSES BLUEPRINTABLE

```cpp
// Minimum — Blueprint subclass can be created
UCLASS(Blueprintable)
class UMyClass : public UObject { ... };

// Blueprint subclass + attachable as component
UCLASS(Blueprintable, BlueprintType)
class UMyComponent : public UActorComponent { ... };

// Abstract — can't be instantiated directly, only used as parent class
UCLASS(Abstract, Blueprintable)
class UMyBase : public UObject { ... };

// EditInlineNew — can be created inline inside a UPROPERTY
UCLASS(Blueprintable, EditInlineNew)
class UMyData : public UObject { ... };
```

**Common mistake:** The class isn't `Blueprintable` but you're trying to access it from Blueprint.
→ Cast fails, function is invisible, can't add as component.

---

## 3. UPROPERTY — FULL REFERENCE

### Editor Access

```cpp
UPROPERTY(EditAnywhere)
// Editable in Details panel — both CDO (class defaults) and instance

UPROPERTY(EditDefaultsOnly)
// Only editable in Blueprint class defaults, not per-instance
// Generally used for design-time constants

UPROPERTY(EditInstanceOnly)
// Only editable on instances placed in the level, not in class defaults
// Generally used for scene-specific overrides

UPROPERTY(VisibleAnywhere)
// Visible but not editable — ideal for component references
// Use VisibleAnywhere for components, not EditAnywhere

UPROPERTY(VisibleDefaultsOnly)
// Only visible in class defaults

UPROPERTY(VisibleInstanceOnly)
// Only visible on instances
```

### Blueprint Access

```cpp
UPROPERTY(BlueprintReadWrite)
// Read and write from Blueprint

UPROPERTY(BlueprintReadOnly)
// Read only from Blueprint

// Combinations — very common:
UPROPERTY(EditAnywhere, BlueprintReadWrite, Category="Combat")
float MaxHealth = 100.f;

UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
TObjectPtr<UStaticMeshComponent> Mesh;
```

### Network / Serialization

```cpp
UPROPERTY(Replicated)
// Replicated from server to clients
// Also requires DOREPLIFETIME() in GetLifetimeReplicatedProps

UPROPERTY(ReplicatedUsing=OnRep_Health)
float Health;
// OnRep_Health() is called on all clients when Health changes

UPROPERTY(SaveGame)
// Serialized with USaveGame + FObjectAndNameAsStringProxyArchive

UPROPERTY(Transient)
// Not serialized, not saved, reset on level load
// Ideal for runtime caches

UPROPERTY(meta=(ClampMin="0.0", ClampMax="1.0", UIMin="0.0", UIMax="1.0"))
float Opacity = 1.f;
// Editor slider is constrained to 0-1
```

### Category and Organization

```cpp
UPROPERTY(EditAnywhere, Category="Combat|Stats")
// Grouped under "Combat > Stats" in the Details panel

UPROPERTY(EditAnywhere, meta=(DisplayName="Max HP"))
float MaxHealth;
// Shows as "Max HP" in the editor, MaxHealth in C++

UPROPERTY(EditAnywhere, meta=(EditCondition="bIsAlive"))
float AttackPower;
// Grayed out and uneditable when bIsAlive is false
```

---

## 4. UFUNCTION — FULL REFERENCE

### Blueprint Access

```cpp
UFUNCTION(BlueprintCallable, Category="Combat")
void TakeDamage(float Amount);
// Callable as a function node in Blueprint (has exec pin)

UFUNCTION(BlueprintPure, Category="Stats")
float GetHealthPercent() const;
// Pure node in Blueprint — no exec pin, just returns a value
// Must be const, should have no side effects

UFUNCTION(BlueprintImplementableEvent, Category="Events")
void OnDeath();
// Only DECLARED in C++ — no body
// Implemented in BP subclass
// To call from C++: OnDeath(); (normal call)

UFUNCTION(BlueprintNativeEvent, Category="Events")
void OnDeath();
// C++ has a DEFAULT IMPLEMENTATION, BP can override
// In .cpp:
void UMyClass::OnDeath_Implementation() {
    // C++ default behavior
}
// If BP doesn't override, C++ runs
// If BP overrides, the BP version runs
```

### BlueprintImplementableEvent vs BlueprintNativeEvent

| | BlueprintImplementableEvent | BlueprintNativeEvent |
|---|---|---|
| C++ body | None (header only) | Yes (with `_Implementation` suffix) |
| BP implementation required? | No (does nothing if not implemented) | No (C++ runs if not overridden) |
| Use case | "BP must implement this" | "C++ has a default, BP can override" |

### Network RPCs

```cpp
UFUNCTION(Server, Reliable, WithValidation)
void ServerFire(FVector Direction);
// Client calls, runs on server
// _Implementation and _Validate required in .cpp:
void UMyComp::ServerFire_Implementation(FVector Direction) { ... }
bool UMyComp::ServerFire_Validate(FVector Direction) { return true; }

UFUNCTION(Client, Reliable)
void ClientShowHitEffect();
// Server calls, runs on owning client

UFUNCTION(NetMulticast, Unreliable)
void MulticastPlaySound(USoundBase* Sound);
// Server calls, runs on all clients
// Unreliable = can be dropped, for non-critical effects
```

### Editor Tools

```cpp
UFUNCTION(CallInEditor, Category="Debug")
void PrintDebugInfo();
// Appears as a button in the Details panel, clickable in editor
// Doesn't run during gameplay

UFUNCTION(BlueprintCallable, meta=(DevelopmentOnly))
void DebugDrawSomething();
// Not compiled in Shipping builds, only in Development
```

---

## 5. C++ ↔ BLUEPRINT COMMUNICATION PATTERNS

### Pattern 1: C++ base class, BP subclass

The most common pattern. Infrastructure in C++, designer parameters in BP.

```cpp
// C++ — base class
UCLASS(Blueprintable)
class AWeapon : public AActor {
    GENERATED_BODY()
public:
    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Weapon")
    float Damage = 50.f;

    UPROPERTY(EditDefaultsOnly, BlueprintReadOnly, Category="Weapon")
    TObjectPtr<UStaticMesh> WeaponMesh;

    UFUNCTION(BlueprintCallable)
    void Fire();

    // BP will override this event
    UFUNCTION(BlueprintImplementableEvent)
    void OnFire();
};
```

```
In BP: Create BP_Rifle derived from AWeapon
→ Set Damage = 75, assign WeaponMesh
→ Implement OnFire event in BP (muzzle flash, sound)
```

### Pattern 2: Calling a C++ function from Blueprint

```cpp
// C++ — function to be called
UFUNCTION(BlueprintCallable)
void SpawnEffect(FVector Location, FRotator Rotation);
```

In Blueprint: The "Spawn Effect" node appears automatically.

**If you can't see it — checklist:**
1. Is the class `UCLASS(Blueprintable)`?
2. Is the function in the `public:` section?
3. Does it have `BlueprintCallable`?
4. Was a Full Rebuild done?
5. Is the Blueprint's parent class correct?

### Pattern 3: Triggering a Blueprint event from C++

```cpp
// C++ — event declaration (NO body)
UFUNCTION(BlueprintImplementableEvent)
void OnHealthChanged(float NewHealth, float OldHealth);

// Triggering from C++
void AMyCharacter::ApplyDamage(float Amount) {
    float OldHealth = Health;
    Health -= Amount;
    OnHealthChanged(Health, OldHealth); // BP catches this event
}
```

### Pattern 4: C++ Interface

When multiple classes need to implement the same function.

```cpp
// Interface definition
UINTERFACE(Blueprintable)
class UInteractable : public UInterface { GENERATED_BODY() };

class IInteractable {
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintNativeEvent, BlueprintCallable)
    void Interact(AActor* Interactor);
};

// C++ implementation
void AChest::Interact_Implementation(AActor* Interactor) {
    OpenChest();
}

// BP implementation → just override the "Interact" event node

// Calling
if (IInteractable* Interactable = Cast<IInteractable>(HitActor)) {
    Interactable->Execute_Interact(HitActor, this);
    // Note: Execute_ prefix — may also be overridden in BP
}
```

---

## 6. ADDING COMPONENTS — C++ PATTERN

```cpp
// .h
UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
TObjectPtr<UStaticMeshComponent> MeshComp;

UPROPERTY(VisibleAnywhere, BlueprintReadOnly)
TObjectPtr<UBoxComponent> CollisionComp;

// .cpp — in Constructor
AMyActor::AMyActor() {
    // Root component
    CollisionComp = CreateDefaultSubobject<UBoxComponent>(TEXT("CollisionComp"));
    SetRootComponent(CollisionComp);

    // Child component
    MeshComp = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("MeshComp"));
    MeshComp->SetupAttachment(CollisionComp);
}
```

**Common mistakes:**
- Making a component `EditAnywhere` — use `VisibleAnywhere` (changing the component reference is usually undesired)
- Using `NewObject` instead of `CreateDefaultSubobject` — doesn't work in CDO
- Forgetting `SetupAttachment` — component floats in the scene

---

## 7. CAST — TYPE CONVERSION

```cpp
// Safe Cast — returns nullptr on failure
UMyComponent* MyComp = Cast<UMyComponent>(GetComponentByClass(UMyComponent::StaticClass()));
if (MyComp) {
    MyComp->DoSomething();
}

// Force Cast — crashes on failure — DON'T USE
UMyComponent* MyComp = (UMyComponent*)SomePointer; // Dangerous

// CastChecked — Assert + crash on failure — only when "this is definitely this type"
UMyComponent* MyComp = CastChecked<UMyComponent>(SomePointer);
```

**Why does Cast fail?**
- The object is genuinely not that type (class hierarchy misunderstood)
- Object was collected by GC (missing UPROPERTY)
- Object hasn't been initialized yet (called too early — Constructor vs BeginPlay)

---

## 8. DELEGATE (EVENT) SYSTEM

```cpp
// Parameterless dynamic delegate (exposable to BP)
DECLARE_DYNAMIC_MULTICAST_DELEGATE(FOnDeath);

UPROPERTY(BlueprintAssignable)
FOnDeath OnDeath;

// With parameter
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnHealthChanged, float, NewHealth);

UPROPERTY(BlueprintAssignable)
FOnHealthChanged OnHealthChanged;

// Trigger from C++
OnDeath.Broadcast();
OnHealthChanged.Broadcast(NewHealthValue);

// In BP: bind with "Bind Event to OnDeath" node
```

**When to use `BlueprintAssignable`:**
When you want to bind a function to this event from Blueprint. Without it, the event won't appear in BP's "Event Dispatchers" section.

---

## 9. AGENT RULES

- "Can't see it in Blueprint" → Apply the checklist from Section 5
- "BlueprintImplementableEvent not working" → Is there a body in C++? There shouldn't be
- "BlueprintNativeEvent not working" → Check `_Implementation` suffix (Section 4)
- Cast returning null → Check causes in Section 7
- Component not visible in BP → `VisibleAnywhere` + Full Rebuild
- RPC not working → `_Implementation` + `_Validate` present? Authority correct?
- Delegate can't be bound from BP → `BlueprintAssignable` present? Declared with `UPROPERTY`?
