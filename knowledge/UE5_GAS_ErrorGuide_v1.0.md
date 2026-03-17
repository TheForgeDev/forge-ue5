# UE5 Gameplay Ability System (GAS) — Error & Setup Guide
### UE5 Dev Agent — Knowledge v1.0
### Source: tranek/GASDocumentation, vorixo devtricks, community research

---

## GAS OVERVIEW — CORE CONCEPTS

GAS = Gameplay Ability System. UE5's framework for abilities, attributes, effects, tags.

**Key classes:**
```
UAbilitySystemComponent (ASC) — central hub, lives on Actor or PlayerState
UGameplayAbility            — defines what an ability does
UAttributeSet               — defines stats (health, mana, damage...)
UGameplayEffect             — modifies attributes (damage, heal, buff...)
FGameplayTag                — hierarchical label (e.g. "Status.Burning")
UGameplayCue                — visual/audio feedback (VFX, sound)
```

---

## CHAPTER 1: SETUP ERRORS

---

### G1 — Missing Build.cs Modules (Most Common First Step)
**Symptom:** LNK2019 errors as soon as GAS classes are used

```csharp
// YourProject.Build.cs — add ALL of these:
PublicDependencyModuleNames.AddRange(new string[]
{
    "GameplayAbilities",
    "GameplayTasks",
    "GameplayTags",
});
```

---

### G2 — AbilitySystemComponent Not Initialized on Client
**Symptom:** `Warning: Can't activate LocalOnly or LocalPredicted ability when not local!`
**Tier:** 1 — The most common GAS multiplayer mistake

GAS must be initialized on **both server AND client** separately.

**ASC on Character (simple setup):**
```cpp
// Constructor:
AbilitySystemComponent = CreateDefaultSubobject<UAbilitySystemComponent>(TEXT("ASC"));
AbilitySystemComponent->SetIsReplicated(true);

// PossessedBy (server):
void AMyCharacter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);
    AbilitySystemComponent->InitAbilityActorInfo(this, this);
    GiveDefaultAbilities(); // grant abilities here on server
}

// OnRep_Controller (client):
void AMyCharacter::OnRep_Controller()
{
    Super::OnRep_Controller();
    AbilitySystemComponent->InitAbilityActorInfo(this, this);
}
```

**ASC on PlayerState (Fortnite/Paragon pattern — recommended for respawning):**
```cpp
// Server — PossessedBy:
void AMyCharacter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);
    AMyPlayerState* PS = GetPlayerState<AMyPlayerState>();
    if (PS)
    {
        AbilitySystemComponent = Cast<UMyASC>(PS->GetAbilitySystemComponent());
        AbilitySystemComponent->InitAbilityActorInfo(PS, this);
    }
}

// Client — OnRep_PlayerState:
void AMyCharacter::OnRep_PlayerState()
{
    Super::OnRep_PlayerState();
    AMyPlayerState* PS = GetPlayerState<AMyPlayerState>();
    if (PS)
    {
        AbilitySystemComponent = Cast<UMyASC>(PS->GetAbilitySystemComponent());
        AbilitySystemComponent->InitAbilityActorInfo(PS, this);
    }
}
```

**Key rule:** InitAbilityActorInfo must be called on both server (PossessedBy) and client (OnRep_PlayerState). No harm in calling twice.

---

### G3 — IAbilitySystemInterface Not Implemented
**Symptom:** GetAbilitySystemComponent() returns null, abilities don't work

```cpp
// Character must implement the interface:
#include "AbilitySystemInterface.h"

class AMyCharacter : public ACharacter, public IAbilitySystemInterface
{
    GENERATED_BODY()

public:
    virtual UAbilitySystemComponent* GetAbilitySystemComponent() const override
    {
        return AbilitySystemComponent;
    }

    UPROPERTY()
    TObjectPtr<UAbilitySystemComponent> AbilitySystemComponent;
};
```

---

### G4 — Abilities Not Granted
**Symptom:** TryActivateAbility returns false, ability not in ASC

Abilities must be **granted** before they can be activated.
Grant happens on **server only** — it replicates automatically.

```cpp
// Grant ability:
FGameplayAbilitySpec AbilitySpec(AbilityClass, 1, -1, this);
AbilitySystemComponent->GiveAbility(AbilitySpec);

// Grant and keep handle for later:
FGameplayAbilitySpecHandle Handle = AbilitySystemComponent->GiveAbility(AbilitySpec);

// Remove ability:
AbilitySystemComponent->ClearAbility(Handle);

// Check if granted:
FGameplayAbilitySpec* Spec = AbilitySystemComponent->FindAbilitySpecFromClass(AbilityClass);
bool bGranted = Spec != nullptr;
```

---

### G5 — AttributeSet Not Registered
**Symptom:** Attribute values return 0, GameplayEffects don't apply

AttributeSets must be created as a subobject and registered with the ASC.

```cpp
// Constructor (or PlayerState constructor if ASC lives there):
AttributeSet = CreateDefaultSubobject<UMyAttributeSet>(TEXT("AttributeSet"));
// No need to manually register — CreateDefaultSubobject on the owning actor of ASC handles it

// If AttributeSet is on a different actor:
AbilitySystemComponent->AddAttributeSetSubobject(AttributeSet);

// Initialize attributes with an instant GameplayEffect (Epic's recommended approach):
// Create GE_InitAttributes as an Instant GameplayEffect with modifiers for each attribute
FGameplayEffectContextHandle EffectContext = ASC->MakeEffectContext();
FGameplayEffectSpecHandle SpecHandle = ASC->MakeOutgoingSpec(InitAttributesEffect, 1, EffectContext);
ASC->ApplyGameplayEffectSpecToSelf(*SpecHandle.Data.Get());
```

---

### G6 — PlayerState NetUpdateFrequency Too Low
**Symptom:** Attribute changes delayed on clients, tags update slowly

PlayerState defaults to very low net update frequency.
With ASC on PlayerState → attribute changes replicate slowly.

```cpp
// In PlayerState constructor:
AMyPlayerState::AMyPlayerState()
{
    NetUpdateFrequency = 100.f; // default is ~1 — way too low for GAS
}
```

---

## CHAPTER 2: ABILITY ACTIVATION ERRORS

---

### G7 — Ability Activation Fails Silently
**Checklist when TryActivateAbility returns false:**

```
1. Is ability granted?        → ASC->FindAbilitySpecFromClass(Class) != nullptr
2. Is ASC initialized?        → InitAbilityActorInfo called
3. Is IAbilitySystemInterface implemented?
4. Are tags blocking it?      → Check ActivationBlockedTags
5. Is cooldown active?        → Check CooldownGameplayEffect
6. Is cost met?               → Check CostGameplayEffect attribute
7. Is CanActivateAbility() overridden and returning false?
```

**Enable GAS logging:**
```
LogAbilitySystem Verbose
LogAbilitySystemComponent Verbose
```

---

### G8 — Ability Ends Immediately
**Symptom:** Ability activates then instantly ends

ActivateAbility must call EndAbility at some point.
If not called → ability hangs indefinitely.
If called too early → ability ends immediately.

```cpp
void UMyAbility::ActivateAbility(const FGameplayAbilitySpecHandle Handle,
    const FGameplayAbilityActorInfo* ActorInfo,
    const FGameplayAbilityActivationInfo ActivationInfo,
    const FGameplayEventData* TriggerEventData)
{
    Super::ActivateAbility(Handle, ActorInfo, ActivationInfo, TriggerEventData);

    // DON'T call EndAbility here unless ability is instant
    // For latent abilities: use AbilityTasks, call EndAbility in task callback

    CommitAbility(Handle, ActorInfo, ActivationInfo); // consumes cost + cooldown
    // ... do ability work ...
    // EndAbility called in callback or after delay
}

void UMyAbility::OnTaskCompleted()
{
    EndAbility(CurrentSpecHandle, CurrentActorInfo, CurrentActivationInfo, true, false);
}
```

---

### G9 — CommitAbility Not Called
**Symptom:** Cooldown and cost never applied even though ability runs

```cpp
// CommitAbility MUST be called for cost/cooldown to apply:
if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
{
    // Cost or cooldown check failed
    EndAbility(Handle, ActorInfo, ActivationInfo, true, true);
    return;
}
```

---

## CHAPTER 3: ATTRIBUTE & EFFECT ERRORS

---

### G10 — AttributeSet Clamping Not Working
**Symptom:** Health goes below 0 or above max

```cpp
// Override PostGameplayEffectExecute in AttributeSet:
void UMyAttributeSet::PostGameplayEffectExecute(const FGameplayEffectModCallbackData& Data)
{
    Super::PostGameplayEffectExecute(Data);

    if (Data.EvaluatedData.Attribute == GetHealthAttribute())
    {
        // Clamp health:
        SetHealth(FMath::Clamp(GetHealth(), 0.f, GetMaxHealth()));
    }
}
```

---

### G11 — GameplayEffect Not Applying
**Checklist:**

```
1. Effect type correct?
   - Instant → applies once, no duration
   - Duration/Infinite → requires active effect removal

2. Target has AttributeSet with the attribute?
   → Effect silently fails if AttributeSet missing

3. Application tag requirements met?
   → Check ApplicationRequiredTags and ApplicationBlockedTags

4. Applied to correct target?
   → ApplyGameplayEffectToSelf vs ApplyGameplayEffectToTarget

5. Replication mode?
   → Mixed/Minimal: GameplayEffects not replicated to simulated proxies
```

```cpp
// Apply effect correctly:
FGameplayEffectContextHandle Context = ASC->MakeEffectContext();
Context.AddSourceObject(this);
FGameplayEffectSpecHandle Spec = ASC->MakeOutgoingSpec(
    DamageEffectClass, AbilityLevel, Context);
if (Spec.IsValid())
{
    // Set magnitude dynamically:
    Spec.Data->SetSetByCallerMagnitude(
        FGameplayTag::RequestGameplayTag("Data.Damage"), DamageAmount);
    ASC->ApplyGameplayEffectSpecToTarget(*Spec.Data.Get(), TargetASC);
}
```

---

### G12 — Meta Attributes (Damage) Not Working
**Symptom:** Damage value not transferred to Health

Meta Attributes are temporary — they're zeroed after PostGameplayEffectExecute.
Use them as intermediary, don't replicate them.

```cpp
// In AttributeSet:
UPROPERTY()  // No replication for Meta Attributes
float Damage; // Meta attribute

void UMyAttributeSet::PostGameplayEffectExecute(...)
{
    if (Data.EvaluatedData.Attribute == GetDamageAttribute())
    {
        float DamageValue = GetDamage();
        SetDamage(0.f); // reset meta attribute

        float NewHealth = GetHealth() - DamageValue;
        SetHealth(FMath::Clamp(NewHealth, 0.f, GetMaxHealth()));
    }
}
```

---

## CHAPTER 4: GAMEPLAY TAGS

---

### G13 — Tag Not Found / RequestGameplayTag Returns Empty
**Symptom:** Tag comparisons fail, tag returned is empty

Tags must be **registered** before use — in GameplayTags.ini or data table.

```ini
; Config/DefaultGameplayTags.ini
[/Script/GameplayTags.GameplayTagsSettings]
+GameplayTagList=(Tag="Ability.Attack",DevComment="")
+GameplayTagList=(Tag="Status.Burning",DevComment="")
+GameplayTagList=(Tag="Data.Damage",DevComment="")
```

```cpp
// Access tags:
FGameplayTag BurningTag = FGameplayTag::RequestGameplayTag(FName("Status.Burning"));

// Check if valid:
if (!BurningTag.IsValid())
{
    UE_LOG(LogTemp, Error, TEXT("Tag not found — check DefaultGameplayTags.ini"));
}

// Better — declare as native tag (UE5.1+):
UE_DECLARE_GAMEPLAY_TAG_EXTERN(TAG_Status_Burning)
UE_DEFINE_GAMEPLAY_TAG(TAG_Status_Burning, "Status.Burning")
```

---

### G14 — Tag Blocking Ability Unexpectedly
**Symptom:** Ability won't activate, no obvious reason

```cpp
// Check what's on the ASC right now:
FGameplayTagContainer OwnedTags;
AbilitySystemComponent->GetOwnedGameplayTags(OwnedTags);
UE_LOG(LogTemp, Log, TEXT("Owned tags: %s"), *OwnedTags.ToStringSimple());

// Check ability's blocking tags:
// In ability class defaults:
// ActivationBlockedTags — if ASC has ANY of these, ability won't activate
// ActivationRequiredTags — ASC must have ALL of these to activate
```

---

## CHAPTER 5: GAS REPLICATION MODES

---

### G15 — Wrong Replication Mode
**Symptom:** Effects/tags not visible on clients

```cpp
// Set in ASC constructor or BeginPlay:
AbilitySystemComponent->SetReplicationMode(EGameplayEffectReplicationMode::Mixed);
```

| Mode | Use For | Effects Replicated | Tags Replicated |
|---|---|---|---|
| Full | Singleplayer / Co-op | All clients | All clients |
| Mixed | Multiplayer, player-controlled | Owner only | All clients |
| Minimal | Multiplayer, AI | Owner only | All clients |

**Recommendation:**
- Player characters → Mixed
- AI/NPCs → Minimal
- Singleplayer → Full

---

## QUICK REFERENCE — GAS SETUP CHECKLIST

```
New GAS project setup:
[ ] Add GameplayAbilities, GameplayTasks, GameplayTags to Build.cs
[ ] Implement IAbilitySystemInterface on Character/PlayerState
[ ] Create AbilitySystemComponent (SetIsReplicated = true)
[ ] Create AttributeSet
[ ] Call InitAbilityActorInfo on server (PossessedBy) AND client (OnRep_PlayerState)
[ ] Set PlayerState NetUpdateFrequency = 100 if ASC lives there
[ ] Initialize attributes with instant GameplayEffect
[ ] Grant default abilities on server in PossessedBy
[ ] Register GameplayTags in DefaultGameplayTags.ini
[ ] Set replication mode (Mixed for players, Minimal for AI)
```
