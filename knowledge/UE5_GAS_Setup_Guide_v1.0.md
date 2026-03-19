# UE5 GAS — Complete Setup & Architecture Guide v1.0

---

## 1. WHAT IS GAS

Gameplay Ability System (GAS) is Epic's framework for abilities, attributes, effects, and tags. Used in Fortnite, Paragon, Lyra. It handles:

- **Abilities** — what a character can do (jump, fire, dash)
- **Attributes** — numeric stats (health, mana, damage)
- **Effects** — how attributes change (damage, heal, buff, debuff)
- **Tags** — hierarchical labels for state and communication
- **Cues** — visual/audio feedback decoupled from logic

GAS is complex because it solves complex problems: networked prediction, effect stacking, ability cancellation, and more. Every setup decision has multiplayer consequences.

---

## 2. CORE CLASSES

```
UAbilitySystemComponent (ASC)
  → The hub. Everything flows through this component.
  → Manages active abilities, applied effects, owned tags

UGameplayAbility (GA)
  → Defines what an ability does
  → Runs on server, may predict on client

UAttributeSet (AS)
  → Container for float attributes (Health, Mana, Stamina)
  → Must be registered with ASC

UGameplayEffect (GE)
  → Modifies attributes — Instant, Duration, Infinite
  → The only correct way to change attributes at runtime

FGameplayTag
  → Hierarchical string label: "Character.State.Stunned"
  → Used everywhere — blocking, requiring, canceling abilities

UGameplayCue
  → Visual/audio feedback only — never game logic
  → Replicated separately from effects
```

---

## 3. ARCHITECTURE DECISION — WHERE DOES ASC LIVE?

This is the most important GAS decision. Wrong choice = painful refactor.

### Option A — ASC on Character

```cpp
// Character.h
UPROPERTY(VisibleAnywhere)
TObjectPtr<UAbilitySystemComponent> AbilitySystemComponent;

UPROPERTY()
TObjectPtr<UMyAttributeSet> AttributeSet;
```

**When to use:**
- Single player games
- AI enemies (they don't respawn with same PlayerState)
- Simple prototypes

**Problem:** On respawn, Character is destroyed and recreated. ASC is destroyed too. All abilities, effects, and tags are lost.

### Option B — ASC on PlayerState (Recommended for multiplayer)

```cpp
// PlayerState.h
UPROPERTY(VisibleAnywhere)
TObjectPtr<UAbilitySystemComponent> AbilitySystemComponent;

UPROPERTY()
TObjectPtr<UMyAttributeSet> AttributeSet;

// Implement IAbilitySystemInterface
virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override;
```

**When to use:**
- Multiplayer games with respawn
- Persistent progression (abilities survive death)
- Fortnite/Paragon pattern

**Advantage:** PlayerState persists through respawn. ASC survives. Abilities, effects, and attributes are preserved.

**Cost:** More complex initialization — InitAbilityActorInfo must be called in more places.

### Option C — ASC on Dedicated Actor (rare)

For non-character entities like vehicles or structures that need GAS. Attach ASC directly to the actor that needs it.

---

## 4. COMPLETE SETUP — ASC ON PLAYERSTATE

### 4.1 PlayerState

```cpp
// MyPlayerState.h
#pragma once
#include "AbilitySystemInterface.h"
#include "GameplayAbilitySpec.h"

UCLASS()
class AMyPlayerState : public APlayerState, public IAbilitySystemInterface
{
    GENERATED_BODY()

public:
    AMyPlayerState();

    virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override
    {
        return AbilitySystemComponent;
    }

    UMyAttributeSet* GetAttributeSet() const { return AttributeSet; }

protected:
    UPROPERTY(VisibleAnywhere, Category = "GAS")
    TObjectPtr<UAbilitySystemComponent> AbilitySystemComponent;

    UPROPERTY()
    TObjectPtr<UMyAttributeSet> AttributeSet;
};

// MyPlayerState.cpp
AMyPlayerState::AMyPlayerState()
{
    AbilitySystemComponent = CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("ASC"));
    AbilitySystemComponent->SetIsReplicated(true);
    // Mixed: effects replicate to owner, cues to all
    AbilitySystemComponent->SetReplicationMode(EGameplayEffectReplicationMode::Mixed);

    AttributeSet = CreateDefaultSubobject<UMyAttributeSet>(TEXT("AttributeSet"));

    // PlayerState replication frequency — CRITICAL
    // Default 100Hz is too low for responsive GAS
    NetUpdateFrequency = 100.f;
}
```

### 4.2 Character — InitAbilityActorInfo

This is where most bugs originate. Must be called in FOUR places:

```cpp
// MyCharacter.cpp

// SERVER: Called when server possesses this character
void AMyCharacter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);

    AMyPlayerState* PS = GetPlayerState<AMyPlayerState>();
    if (!PS) return;

    AbilitySystemComponent = Cast<UAbilitySystemComponent>(PS->GetAbilitySystemComponent());
    AttributeSet = PS->GetAttributeSet();

    // Owner = PlayerState, Avatar = Character
    AbilitySystemComponent->InitAbilityActorInfo(PS, this);

    // Grant abilities AFTER InitAbilityActorInfo
    if (HasAuthority())
    {
        GiveDefaultAbilities();
        ApplyDefaultEffects();
    }
}

// CLIENT: Called when PlayerState replicates to client
void AMyCharacter::OnRep_PlayerState()
{
    Super::OnRep_PlayerState();

    AMyPlayerState* PS = GetPlayerState<AMyPlayerState>();
    if (!PS) return;

    AbilitySystemComponent = Cast<UAbilitySystemComponent>(PS->GetAbilitySystemComponent());
    AttributeSet = PS->GetAttributeSet();

    AbilitySystemComponent->InitAbilityActorInfo(PS, this);
}

// RESPAWN — Server re-possesses after respawn
// PossessedBy fires again — InitAbilityActorInfo called again
// This is intentional and safe

// If using OnRep_Controller instead of OnRep_PlayerState:
void AMyCharacter::OnRep_Controller()
{
    Super::OnRep_Controller();
    // Only needed if ASC is on Character, not PlayerState
}
```

### 4.3 AttributeSet

```cpp
// MyAttributeSet.h
#pragma once
#include "AttributeSet.h"
#include "AbilitySystemComponent.h"
#include "MyAttributeSet.generated.h"

// Macro generates getters/setters/replication
#define ATTRIBUTE_ACCESSORS(ClassName, PropertyName) \
    GAMEPLAYATTRIBUTE_PROPERTY_GETTER(ClassName, PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_GETTER(PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_SETTER(PropertyName) \
    GAMEPLAYATTRIBUTE_VALUE_INITTER(PropertyName)

UCLASS()
class UMyAttributeSet : public UAttributeSet
{
    GENERATED_BODY()

public:
    UMyAttributeSet();

    virtual void GetLifetimeReplicatedProps(
        TArray<FLifetimeProperty>& OutLifetimeProps) const override;

    // Called before attribute changes — use for clamping
    virtual void PreAttributeChange(
        const FGameplayAttribute& Attribute, float& NewValue) override;

    // Called after a GameplayEffect applies — use for reactions
    virtual void PostGameplayEffectExecute(
        const FGameplayEffectModCallbackData& Data) override;

    // Health
    UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_Health, Category = "Attributes")
    FGameplayAttributeData Health;
    ATTRIBUTE_ACCESSORS(UMyAttributeSet, Health)

    UPROPERTY(BlueprintReadOnly, ReplicatedUsing = OnRep_MaxHealth, Category = "Attributes")
    FGameplayAttributeData MaxHealth;
    ATTRIBUTE_ACCESSORS(UMyAttributeSet, MaxHealth)

    // Meta attribute — not replicated, used for damage calculation
    UPROPERTY(BlueprintReadOnly, Category = "Attributes")
    FGameplayAttributeData Damage;
    ATTRIBUTE_ACCESSORS(UMyAttributeSet, Damage)

protected:
    UFUNCTION()
    virtual void OnRep_Health(const FGameplayAttributeData& OldHealth);

    UFUNCTION()
    virtual void OnRep_MaxHealth(const FGameplayAttributeData& OldMaxHealth);
};

// MyAttributeSet.cpp
#include "MyAttributeSet.h"
#include "Net/UnrealNetwork.h"
#include "GameplayEffectExtension.h"

void UMyAttributeSet::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);

    DOREPLIFETIME_CONDITION_NOTIFY(UMyAttributeSet, Health, COND_None, REPNOTIFY_Always);
    DOREPLIFETIME_CONDITION_NOTIFY(UMyAttributeSet, MaxHealth, COND_None, REPNOTIFY_Always);
    // Damage is meta — not replicated
}

void UMyAttributeSet::PreAttributeChange(
    const FGameplayAttribute& Attribute, float& NewValue)
{
    Super::PreAttributeChange(Attribute, NewValue);

    if (Attribute == GetHealthAttribute())
    {
        NewValue = FMath::Clamp(NewValue, 0.f, GetMaxHealth());
    }
    if (Attribute == GetMaxHealthAttribute())
    {
        NewValue = FMath::Max(NewValue, 1.f);
    }
}

void UMyAttributeSet::PostGameplayEffectExecute(
    const FGameplayEffectModCallbackData& Data)
{
    Super::PostGameplayEffectExecute(Data);

    if (Data.EvaluatedData.Attribute == GetDamageAttribute())
    {
        // Apply damage from meta attribute to Health
        const float DamageDone = GetDamage();
        SetDamage(0.f); // Clear meta attribute

        const float NewHealth = FMath::Max(GetHealth() - DamageDone, 0.f);
        SetHealth(NewHealth);

        if (NewHealth <= 0.f)
        {
            // Notify character of death
            // Don't destroy here — let game logic handle it
        }
    }
}

void UMyAttributeSet::OnRep_Health(const FGameplayAttributeData& OldHealth)
{
    GAMEPLAYATTRIBUTE_REPNOTIFY(UMyAttributeSet, Health, OldHealth);
}

void UMyAttributeSet::OnRep_MaxHealth(const FGameplayAttributeData& OldMaxHealth)
{
    GAMEPLAYATTRIBUTE_REPNOTIFY(UMyAttributeSet, MaxHealth, OldMaxHealth);
}
```

### 4.4 Granting Default Abilities

```cpp
// In Character or PlayerState — called after InitAbilityActorInfo on server

void AMyCharacter::GiveDefaultAbilities()
{
    if (!HasAuthority() || !AbilitySystemComponent) return;

    // Guard against granting twice (respawn)
    if (bAbilitiesGranted) return;
    bAbilitiesGranted = true;

    for (TSubclassOf<UGameplayAbility>& AbilityClass : DefaultAbilities)
    {
        if (!AbilityClass) continue;

        FGameplayAbilitySpec Spec(
            AbilityClass,
            1,         // Level
            INDEX_NONE,
            this       // Source object
        );

        AbilitySystemComponent->GiveAbility(Spec);
    }
}
```

### 4.5 Applying Startup Effects

```cpp
void AMyCharacter::ApplyDefaultEffects()
{
    if (!HasAuthority() || !AbilitySystemComponent) return;

    FGameplayEffectContextHandle Context =
        AbilitySystemComponent->MakeEffectContext();
    Context.AddSourceObject(this);

    for (TSubclassOf<UGameplayEffect>& EffectClass : DefaultEffects)
    {
        if (!EffectClass) continue;

        FGameplayEffectSpecHandle Spec =
            AbilitySystemComponent->MakeOutgoingSpec(EffectClass, 1, Context);

        if (Spec.IsValid())
        {
            AbilitySystemComponent->ApplyGameplayEffectSpecToSelf(*Spec.Data.Get());
        }
    }
}
```

---

## 5. REPLICATION MODES — WHICH ONE TO CHOOSE

| Mode | Who receives effects | Use case |
|---|---|---|
| `Full` | All clients | Single player, small games, AI |
| `Mixed` | Owner gets effects + tags; all get Cues | Player characters (recommended) |
| `Minimal` | Only Cues replicate to all | AI-controlled actors |

**Rule:** Player-controlled characters → Mixed. AI → Minimal. Single player → Full.

```cpp
// In PlayerState constructor:
ASC->SetReplicationMode(EGameplayEffectReplicationMode::Mixed);

// In AI Character constructor (ASC on Character):
ASC->SetReplicationMode(EGameplayEffectReplicationMode::Minimal);
```

---

## 6. BUILD.CS — REQUIRED MODULES

```csharp
// YourProject.Build.cs
PublicDependencyModuleNames.AddRange(new string[]
{
    "GameplayAbilities",
    "GameplayTasks",
    "GameplayTags",
});
```

Missing any of these = LNK2019 errors on first GAS class usage.

---

## 7. PROJECT SETTINGS — GAMEPLAY TAGS

Tags must be defined in Project Settings before use:

```
Project Settings → Project → GameplayTags
→ Add new tag: "Ability.Jump"
→ Add new tag: "Status.Stunned"
→ Add new tag: "Effect.Damage"
```

Or in a DataTable asset. Tags not defined here = `RequestGameplayTag` returns empty.

---

## 8. AGENT RULES

- LNK2019 on GAS classes → Build.cs modules missing (Section 6)
- "Can't activate ability when not local" → InitAbilityActorInfo missing on client (Section 4.2)
- Abilities not granted → bAbilitiesGranted guard, check HasAuthority (Section 4.4)
- AttributeSet not working → check DOREPLIFETIME_CONDITION_NOTIFY with REPNOTIFY_Always
- Wrong replication mode → Mixed for players, Minimal for AI (Section 5)
- Attributes not replicating → missing OnRep_ functions with GAMEPLAYATTRIBUTE_REPNOTIFY
- Respawn breaks GAS → ASC should be on PlayerState, not Character (Section 3)
- Damage not applying → use meta attribute pattern (Section 4.3 PostGameplayEffectExecute)
- PlayerState NetUpdateFrequency → set to 100.f minimum (Section 4.1)
