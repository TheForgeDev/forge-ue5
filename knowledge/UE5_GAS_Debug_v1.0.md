# UE5 GAS — Debug & Diagnosis Guide v1.0

---

## 1. SHOWDEBUG COMMANDS

The most powerful GAS debugging tool. Run in PIE console or shipping build with cheats enabled.

```
showdebug abilitysystem
```

This displays on screen:
- Active abilities (and their state)
- Active gameplay effects (name, duration, stacks)
- Owned gameplay tags
- Attribute values
- Blocked/required tags

### Navigate between actors:

```
AbilitySystem.Debug.NextTarget    — cycle to next actor
AbilitySystem.Debug.PrevTarget    — cycle to previous actor
```

Or click an actor in the viewport while showdebug is active.

### What to look for:

```
Active Abilities:
  [ACTIVE]    UMyAbility_Jump         ← currently running
  [INACTIVE]  UMyAbility_Fireball     ← ready to activate

Active Effects:
  GE_Burn (3.2s remaining, stack: 1)
  GE_SpeedBuff (∞, stack: 2)

Owned Tags:
  Status.Burning
  Ability.Jumping

Attributes:
  Health: 75.0 / 100.0
  Mana: 30.0 / 50.0
```

---

## 2. LOG CATEGORIES

Add to DefaultEngine.ini or run in console:

```ini
[Core.Log]
LogAbilitySystem=Verbose
LogGameplayTags=Verbose
LogGameplayEffects=Verbose
LogGameplayAbilities=Verbose
```

Or in console:
```
log LogAbilitySystem Verbose
log LogGameplayTags Verbose
```

### Key log messages and what they mean:

```
"Can't activate LocalOnly or LocalPredicted ability when not local"
→ InitAbilityActorInfo not called on client
→ Fix: OnRep_PlayerState or OnRep_Controller

"Attribute Health is not from AttributeSet registered with ASC"
→ AttributeSet not registered with the ASC
→ Fix: Create AttributeSet as subobject of ASC owner, not separately

"Ability blocked by tags"
→ An owned tag is in the ability's BlockAbilitiesWithTag list
→ Fix: Check showdebug for active tags, remove blocking tag

"ApplyGameplayEffectSpecToSelf called on ASC before InitAbilityActorInfo"
→ Effect applied before GAS is initialized
→ Fix: Call InitAbilityActorInfo before ApplyDefaultEffects

"GameplayEffect has no target"
→ Target ASC is null
→ Fix: Verify target actor implements IAbilitySystemInterface
```

---

## 3. COMMON CRASH PATTERNS

### CRASH-GAS01: Null ASC pointer after respawn

```
Callstack hint:
  UAbilitySystemComponent::TryActivateAbility → nullptr dereference

Cause:
  ASC is on Character. Character destroyed on death.
  New Character spawned. ASC reference not updated.

Fix:
  Move ASC to PlayerState. Or update ASC reference on respawn.

Detection:
  if (!AbilitySystemComponent)
  {
      UE_LOG(LogTemp, Error, TEXT("ASC is null on %s"), *GetName());
      return;
  }
```

### CRASH-GAS02: AttributeSet garbage collected

```
Callstack hint:
  UAttributeSet::GetHealthAttribute → access violation

Cause:
  AttributeSet created without UPROPERTY() — GC collects it.

Fix:
  UPROPERTY()
  TObjectPtr<UMyAttributeSet> AttributeSet;

  // OR register as subobject (auto-prevents GC):
  AttributeSet = CreateDefaultSubobject<UMyAttributeSet>(TEXT("AS"));
```

### CRASH-GAS03: AbilityTask outlives ability

```
Callstack hint:
  UAbilityTask::Activate → ability spec invalid

Cause:
  Ability ends but task callback fires after.

Fix:
  In task's OnDestroy, unbind all delegates.
  In ability's EndAbility, task is automatically cleaned up.
  Never store raw task pointer — use the task handle.
```

### CRASH-GAS04: Effect applied on client without authority

```
Callstack hint:
  UAbilitySystemComponent::ApplyGameplayEffectSpecToSelf → ensure(HasAuthority())

Cause:
  Client-side code applying a gameplay effect directly.

Fix:
  All effect applications must happen on server.
  Use Server RPC if triggering from client input.
  Predicted effects use UAbilitySystemComponent::ApplyGameplayEffectToSelf
  with prediction key.
```

### CRASH-GAS05: Tag container modified during iteration

```
Callstack hint:
  FGameplayTagContainer::HasTag → array out of bounds

Cause:
  Gameplay tag container modified while being iterated.
  Common in effects that grant/remove tags on application.

Fix:
  Copy the container before iterating:
  FGameplayTagContainer TagsCopy = OwnedTags;
  for (const FGameplayTag& Tag : TagsCopy) { ... }
```

---

## 4. ATTRIBUTE DEBUGGING

### Print all attributes:

```cpp
void DebugPrintAttributes(UAbilitySystemComponent* ASC)
{
    if (!ASC) return;

    TArray<UAttributeSet*> AttributeSets = ASC->GetSpawnedAttributes();
    for (UAttributeSet* Set : AttributeSets)
    {
        if (!Set) continue;

        TArray<FGameplayAttribute> Attributes;
        UAttributeSet::GetAttributesFromSetClass(Set->GetClass(), Attributes);

        for (const FGameplayAttribute& Attr : Attributes)
        {
            float Value = ASC->GetNumericAttribute(Attr);
            UE_LOG(LogTemp, Log, TEXT("%s: %.2f"),
                *Attr.GetName(), Value);
        }
    }
}
```

### Watch attribute change:

```cpp
// In BeginPlay or after InitAbilityActorInfo:
AbilitySystemComponent->GetGameplayAttributeValueChangeDelegate(
    UMyAttributeSet::GetHealthAttribute()
).AddUObject(this, &AMyCharacter::OnHealthChanged);

void AMyCharacter::OnHealthChanged(const FOnAttributeChangeData& Data)
{
    UE_LOG(LogTemp, Log,
        TEXT("Health changed: %.2f → %.2f (delta: %.2f)"),
        Data.OldValue, Data.NewValue, Data.NewValue - Data.OldValue);
}
```

---

## 5. EFFECT DEBUGGING

### List all active effects:

```cpp
void DebugActiveEffects(UAbilitySystemComponent* ASC)
{
    if (!ASC) return;

    TArray<FActiveGameplayEffect*> Effects;
    ASC->GetAllActiveGameplayEffects(Effects);  // Note: use query instead

    // Better approach:
    FGameplayEffectQuery Query; // empty = all effects
    TArray<FActiveGameplayEffectHandle> Handles =
        ASC->GetActiveEffects(Query);

    for (const FActiveGameplayEffectHandle& Handle : Handles)
    {
        const FActiveGameplayEffect* Effect =
            ASC->GetActiveGameplayEffect(Handle);
        if (!Effect) continue;

        UE_LOG(LogTemp, Log,
            TEXT("Effect: %s, Duration: %.2f, Stacks: %d"),
            *Effect->Spec.Def->GetName(),
            Effect->GetTimeRemaining(ASC->GetWorld()->GetTimeSeconds()),
            Effect->Spec.StackCount);
    }
}
```

### Check if specific effect is active:

```cpp
bool IsEffectActive(
    UAbilitySystemComponent* ASC,
    TSubclassOf<UGameplayEffect> EffectClass)
{
    FGameplayEffectQuery Query =
        FGameplayEffectQuery::MakeQuery_MatchAnyOwningTags(
            EffectClass.GetDefaultObject()->InheritableOwnedTagsContainer.Added
        );

    return ASC->GetActiveEffects(Query).Num() > 0;
}
```

---

## 6. TAG DEBUGGING

### Print all owned tags:

```cpp
void DebugOwnedTags(UAbilitySystemComponent* ASC)
{
    if (!ASC) return;

    FGameplayTagContainer OwnedTags;
    ASC->GetOwnedGameplayTags(OwnedTags);

    UE_LOG(LogTemp, Log, TEXT("Owned Tags for %s:"),
        *ASC->GetOwnerActor()->GetName());

    for (const FGameplayTag& Tag : OwnedTags)
    {
        UE_LOG(LogTemp, Log, TEXT("  %s"), *Tag.ToString());
    }
}
```

### Check why ability is blocked:

```cpp
void DebugAbilityBlocked(
    UAbilitySystemComponent* ASC,
    TSubclassOf<UGameplayAbility> AbilityClass)
{
    FGameplayAbilitySpec* Spec = ASC->FindAbilitySpecFromClass(AbilityClass);
    if (!Spec) { UE_LOG(LogTemp, Warning, TEXT("Ability not granted")); return; }

    FGameplayTagContainer OwnedTags;
    ASC->GetOwnedGameplayTags(OwnedTags);

    const UGameplayAbility* AbilityCDO = AbilityClass.GetDefaultObject();

    // Check activation required tags
    if (!AbilityCDO->ActivationRequiredTags.IsEmpty())
    {
        if (!OwnedTags.HasAll(AbilityCDO->ActivationRequiredTags))
        {
            UE_LOG(LogTemp, Warning,
                TEXT("Missing required tags: %s"),
                *AbilityCDO->ActivationRequiredTags.ToString());
        }
    }

    // Check blocked tags
    if (!AbilityCDO->ActivationBlockedTags.IsEmpty())
    {
        if (OwnedTags.HasAny(AbilityCDO->ActivationBlockedTags))
        {
            UE_LOG(LogTemp, Warning,
                TEXT("Blocked by tags: %s"),
                *AbilityCDO->ActivationBlockedTags.ToString());
        }
    }
}
```

---

## 7. ABILITY STATE DEBUGGING

### List all granted abilities and their state:

```cpp
void DebugGrantedAbilities(UAbilitySystemComponent* ASC)
{
    if (!ASC) return;

    TArray<FGameplayAbilitySpec>& Specs = ASC->GetActivatableAbilities();
    for (const FGameplayAbilitySpec& Spec : Specs)
    {
        UE_LOG(LogTemp, Log,
            TEXT("Ability: %s | Active: %s | Level: %d"),
            *Spec.Ability->GetName(),
            Spec.IsActive() ? TEXT("YES") : TEXT("NO"),
            Spec.Level);
    }
}
```

---

## 8. USEFUL CONSOLE COMMANDS

```
// GAS debug overlay
showdebug abilitysystem

// Verbose logging
log LogAbilitySystem Verbose
log LogGameplayEffects Verbose
log LogGameplayTags Verbose

// Force grant an ability (requires cheat manager)
AbilitySystem.Grant [AbilityClass]

// Force apply a gameplay effect
AbilitySystem.ApplyEffect [EffectClass]

// Show all registered tags
GameplayTags.PrintAll

// Show tag usage in project
GameplayTags.PrintReplicationFrequencyReport
```

---

## 9. NETWORK DEBUGGING

### Check if prediction failed:

```cpp
// Add to AbilitySystemComponent subclass:
virtual void OnPredictiveGameplayEffectAddedTagChange(
    const FGameplayTag Tag, int32 NewCount) override
{
    Super::OnPredictiveGameplayEffectAddedTagChange(Tag, NewCount);
    UE_LOG(LogTemp, Verbose,
        TEXT("[PREDICTION] Tag %s count: %d"),
        *Tag.ToString(), NewCount);
}
```

### Verify authority:

```cpp
// Always check before applying effects:
if (!AbilitySystemComponent->IsOwnerActorAuthoritative())
{
    UE_LOG(LogTemp, Warning,
        TEXT("Attempted to apply effect without authority"));
    return;
}
```

---

## 10. AGENT RULES

- "Can't activate LocalOnly ability" → showdebug, check InitAbilityActorInfo timing
- Attribute not changing → DebugActiveEffects, verify effect spec and modifier
- Tag not blocking → DebugOwnedTags, verify tag name matches exactly
- Ability not granting → check bAbilitiesGranted guard, check HasAuthority
- Effect applying on wrong actor → verify GetAbilitySystemComponent() returns correct ASC
- Crash after respawn → CRASH-GAS01, move ASC to PlayerState
- AttributeSet null crash → CRASH-GAS02, missing UPROPERTY
- Prediction mismatch → check replication mode, verify server runs same logic
- showdebug not showing → ability system not initialized, or wrong actor targeted
