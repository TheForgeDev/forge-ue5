# UE5 GAS — Advanced Systems Guide v1.0

---

## 1. ABILITY LIFECYCLE — COMPLETE FLOW

Every ability follows this exact sequence:

```
CanActivateAbility()          — can it run? (tags, cooldown, cost)
        ↓
TryActivateAbility()          — attempt to activate
        ↓
CallActivateAbility()          — actually calls ActivateAbility()
        ↓
ActivateAbility()             — YOUR CODE RUNS HERE
        ↓
CommitAbility()               — deduct cost, apply cooldown
        ↓
[ability runs — may span multiple frames via AbilityTasks]
        ↓
EndAbility()                  — cleanup, required
```

**Critical rules:**
- Never call `EndAbility()` before `CommitAbility()` if you want cost/cooldown to apply
- Always call `EndAbility()` — memory leak if you don't
- `CommitAbility()` can fail — check return value

```cpp
void UMyAbility::ActivateAbility(
    const FGameplayAbilitySpecHandle Handle,
    const FGameplayAbilityActorInfo* ActorInfo,
    const FGameplayAbilityActivationInfo ActivationInfo,
    const FGameplayEventData* TriggerEventData)
{
    Super::ActivateAbility(Handle, ActorInfo, ActivationInfo, TriggerEventData);

    // CommitAbility checks cost AND cooldown
    if (!CommitAbility(Handle, ActorInfo, ActivationInfo))
    {
        // Cost or cooldown failed — end immediately
        EndAbility(Handle, ActorInfo, ActivationInfo,
            /*bReplicateEndAbility=*/true, /*bWasCancelled=*/true);
        return;
    }

    // Your ability logic here
    // For instant abilities: apply effect, then end
    // For multi-frame: start an AbilityTask, DON'T end here
}
```

---

## 2. ABILITY TASKS — MULTI-FRAME ABILITIES

AbilityTasks are the mechanism for abilities that span multiple frames. Without them, you can't have:
- Waiting for animation to finish
- Waiting for player input confirmation
- Targeting (selecting where to aim)
- Timed sequences

### 2.1 Built-in Tasks

```cpp
// Wait for gameplay event (e.g. animation notify)
UAbilityTask_WaitGameplayEvent* Task =
    UAbilityTask_WaitGameplayEvent::WaitGameplayEvent(
        this,
        FGameplayTag::RequestGameplayTag("Event.Montage.Hit"),
        nullptr,    // optional target actor
        true        // only trigger once
    );
Task->EventReceived.AddDynamic(this, &UMyAbility::OnHitEventReceived);
Task->ReadyForActivation();
// DON'T call EndAbility() here — task keeps ability alive

// Wait for attribute change
UAbilityTask_WaitAttributeChange* Task =
    UAbilityTask_WaitAttributeChange::WaitForAttributeChange(
        this,
        UMyAttributeSet::GetHealthAttribute(),
        FGameplayTag(),
        FGameplayTag(),
        true
    );
Task->Changed.AddDynamic(this, &UMyAbility::OnHealthChanged);
Task->ReadyForActivation();

// Wait for delay
UAbilityTask_WaitDelay* Task =
    UAbilityTask_WaitDelay::WaitDelay(this, 2.0f);
Task->OnFinish.AddDynamic(this, &UMyAbility::OnDelayFinished);
Task->ReadyForActivation();

// Play montage and wait
UAbilityTask_PlayMontageAndWait* Task =
    UAbilityTask_PlayMontageAndWait::CreatePlayMontageAndWaitProxy(
        this,
        NAME_None,
        AttackMontage,
        1.0f,       // rate
        NAME_None,  // start section
        false       // stop when ability ends
    );
Task->OnCompleted.AddDynamic(this, &UMyAbility::OnMontageCompleted);
Task->OnCancelled.AddDynamic(this, &UMyAbility::OnMontageCancelled);
Task->OnInterrupted.AddDynamic(this, &UMyAbility::OnMontageInterrupted);
Task->ReadyForActivation();
```

### 2.2 Custom AbilityTask

```cpp
// MyAbilityTask_WaitInputConfirm.h
UCLASS()
class UMyAbilityTask_WaitInputConfirm : public UAbilityTask
{
    GENERATED_BODY()

public:
    UPROPERTY(BlueprintAssignable)
    FGenericGameplayTaskDelegate OnConfirm;

    UPROPERTY(BlueprintAssignable)
    FGenericGameplayTaskDelegate OnCancel;

    UFUNCTION(BlueprintCallable, Category="Ability|Tasks",
        meta=(HidePin="OwningAbility", DefaultToSelf="OwningAbility"))
    static UMyAbilityTask_WaitInputConfirm* WaitForInputConfirm(
        UGameplayAbility* OwningAbility);

    virtual void Activate() override;
    virtual void OnDestroy(bool bInOwnerFinished) override;

private:
    void OnInputConfirmed();
    void OnInputCancelled();

    FDelegateHandle ConfirmHandle;
    FDelegateHandle CancelHandle;
};

// MyAbilityTask_WaitInputConfirm.cpp
void UMyAbilityTask_WaitInputConfirm::Activate()
{
    UAbilitySystemComponent* ASC = AbilitySystemComponent.Get();
    if (!ASC) { EndTask(); return; }

    ConfirmHandle = ASC->GenericLocalConfirmCallbacks.AddUObject(
        this, &UMyAbilityTask_WaitInputConfirm::OnInputConfirmed);
    CancelHandle = ASC->GenericLocalCancelCallbacks.AddUObject(
        this, &UMyAbilityTask_WaitInputConfirm::OnInputCancelled);
}

void UMyAbilityTask_WaitInputConfirm::OnInputConfirmed()
{
    OnConfirm.Broadcast();
    EndTask();
}
```

### 2.3 Task Rules

```
DO:
  → Always call ReadyForActivation() after binding delegates
  → Call EndAbility() inside task callbacks when done
  → Handle OnCancelled and OnInterrupted — always

DON'T:
  → Call EndAbility() in ActivateAbility() if a task is running
  → Store task as UPROPERTY without checking validity
  → Forget OnDestroy cleanup (unbind delegates)
```

---

## 3. GAMEPLAY EFFECTS — COMPLETE REFERENCE

### 3.1 Effect Duration Types

```
Instant    → Applies once, immediately. Permanent change.
             Example: deal 50 damage
             
Duration   → Applies for X seconds, then removes itself.
             Example: burning for 5 seconds
             
Infinite   → Never expires. Must be manually removed.
             Example: passive buff while equipped
```

### 3.2 Modifier Operations

```
Add          → Attribute += Value
Multiply     → Attribute *= Value  (stacks multiplicatively)
Divide       → Attribute /= Value
Override     → Attribute = Value   (ignores current value)

Stacking order: Add → Multiply → Divide → Override
```

### 3.3 Applying Effects in C++

```cpp
// Apply effect to self
void ApplyEffectToSelf(
    UAbilitySystemComponent* ASC,
    TSubclassOf<UGameplayEffect> EffectClass,
    float Level = 1.f)
{
    if (!ASC || !EffectClass) return;

    FGameplayEffectContextHandle Context = ASC->MakeEffectContext();
    Context.AddSourceObject(ASC->GetOwnerActor());

    FGameplayEffectSpecHandle Spec =
        ASC->MakeOutgoingSpec(EffectClass, Level, Context);

    if (Spec.IsValid())
    {
        ASC->ApplyGameplayEffectSpecToSelf(*Spec.Data.Get());
    }
}

// Apply effect to target
void ApplyEffectToTarget(
    UAbilitySystemComponent* SourceASC,
    UAbilitySystemComponent* TargetASC,
    TSubclassOf<UGameplayEffect> EffectClass,
    float Level = 1.f)
{
    if (!SourceASC || !TargetASC || !EffectClass) return;

    FGameplayEffectContextHandle Context = SourceASC->MakeEffectContext();
    Context.AddSourceObject(SourceASC->GetOwnerActor());

    FGameplayEffectSpecHandle Spec =
        SourceASC->MakeOutgoingSpec(EffectClass, Level, Context);

    if (Spec.IsValid())
    {
        SourceASC->ApplyGameplayEffectSpecToTarget(
            *Spec.Data.Get(), TargetASC);
    }
}

// Remove effect by class
void RemoveEffect(
    UAbilitySystemComponent* ASC,
    TSubclassOf<UGameplayEffect> EffectClass)
{
    ASC->RemoveActiveGameplayEffectBySourceEffect(EffectClass, nullptr);
}

// Remove effect by handle (stored when applied)
FActiveGameplayEffectHandle Handle = ASC->ApplyGameplayEffectSpecToSelf(...);
ASC->RemoveActiveGameplayEffect(Handle);
```

### 3.4 Set By Caller — Dynamic Values

Use SetByCaller to pass runtime values (damage amount, duration) into effects:

```cpp
// In effect asset: set modifier source to "SetByCaller", tag = "Data.Damage"

// When applying:
FGameplayEffectSpecHandle Spec = ASC->MakeOutgoingSpec(DamageEffect, 1, Context);
Spec.Data->SetSetByCallerMagnitude(
    FGameplayTag::RequestGameplayTag("Data.Damage"),
    DamageAmount
);
ASC->ApplyGameplayEffectSpecToTarget(*Spec.Data.Get(), TargetASC);
```

---

## 4. EXECUTION CALCULATIONS

ExecCalcs are for complex damage formulas that need to read multiple attributes from source and target.

```cpp
// MyDamageExecCalc.h
UCLASS()
class UMyDamageExecCalc : public UGameplayEffectExecutionCalculation
{
    GENERATED_BODY()

public:
    UMyDamageExecCalc();

    virtual void Execute_Implementation(
        const FGameplayEffectCustomExecutionParameters& ExecutionParams,
        FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const override;
};

// MyDamageExecCalc.cpp
// Define attribute capture structs
struct FDamageStatics
{
    // Captures from SOURCE
    DECLARE_ATTRIBUTE_CAPTUREDEF(AttackPower);
    // Captures from TARGET
    DECLARE_ATTRIBUTE_CAPTUREDEF(Defense);
    DECLARE_ATTRIBUTE_CAPTUREDEF(Health);

    FDamageStatics()
    {
        // true = snapshot (capture at effect creation time)
        // false = live (capture at execution time)
        DEFINE_ATTRIBUTE_CAPTUREDEF(UMyAttributeSet, AttackPower, Source, true);
        DEFINE_ATTRIBUTE_CAPTUREDEF(UMyAttributeSet, Defense, Target, false);
        DEFINE_ATTRIBUTE_CAPTUREDEF(UMyAttributeSet, Health, Target, false);
    }
};

static const FDamageStatics& DamageStatics()
{
    static FDamageStatics Statics;
    return Statics;
}

UMyDamageExecCalc::UMyDamageExecCalc()
{
    RelevantAttributesToCapture.Add(DamageStatics().AttackPowerDef);
    RelevantAttributesToCapture.Add(DamageStatics().DefenseDef);
    RelevantAttributesToCapture.Add(DamageStatics().HealthDef);
}

void UMyDamageExecCalc::Execute_Implementation(
    const FGameplayEffectCustomExecutionParameters& ExecutionParams,
    FGameplayEffectCustomExecutionOutput& OutExecutionOutput) const
{
    const FGameplayEffectSpec& Spec = ExecutionParams.GetOwningSpec();

    FAggregatorEvaluateParameters EvalParams;
    EvalParams.SourceTags = Spec.CapturedSourceTags.GetAggregatedTags();
    EvalParams.TargetTags = Spec.CapturedTargetTags.GetAggregatedTags();

    float AttackPower = 0.f;
    float Defense = 0.f;

    ExecutionParams.AttemptCalculateCapturedAttributeMagnitude(
        DamageStatics().AttackPowerDef, EvalParams, AttackPower);
    ExecutionParams.AttemptCalculateCapturedAttributeMagnitude(
        DamageStatics().DefenseDef, EvalParams, Defense);

    // Damage formula
    float Damage = FMath::Max(AttackPower - Defense * 0.5f, 1.f);

    // Output: modify the Damage meta attribute on target
    OutExecutionOutput.AddOutputModifier(
        FGameplayModifierEvaluatedData(
            UMyAttributeSet::GetDamageAttribute(),
            EGameplayModOp::Additive,
            Damage
        )
    );
}
```

---

## 5. GAMEPLAY CUES — DECOUPLED VISUAL FEEDBACK

Cues handle VFX, sound, and cosmetic feedback. They are:
- **Never** responsible for game logic
- Replicated separately from effects (via NetMulticast)
- Safe to skip on low-end clients

### 5.1 Cue Tags

```
GameplayCue.Character.Hit
GameplayCue.Ability.FireBall.Impact
GameplayCue.Status.Burning
```

Must start with `GameplayCue.` — this is enforced.

### 5.2 Triggering Cues

```cpp
// From within a GameplayEffect asset:
// Add GameplayCue tag to the effect — auto-triggers on apply/remove

// From C++ manually:
FGameplayCueParameters CueParams;
CueParams.NormalizedMagnitude = DamageAmount / MaxDamage;
CueParams.RawMagnitude = DamageAmount;
CueParams.Location = HitLocation;
CueParams.Normal = HitNormal;

ASC->ExecuteGameplayCue(
    FGameplayTag::RequestGameplayTag("GameplayCue.Character.Hit"),
    CueParams
);
```

### 5.3 Custom Cue Actor

```cpp
UCLASS()
class AMyGameplayCue_BurnEffect : public AGameplayCueNotify_Actor
{
    GENERATED_BODY()

public:
    // Called when effect starts
    virtual bool OnActive_Implementation(
        AActor* MyTarget,
        const FGameplayCueParameters& Parameters) override;

    // Called every tick while effect is active
    virtual bool WhileActive_Implementation(
        AActor* MyTarget,
        const FGameplayCueParameters& Parameters) override;

    // Called when effect ends
    virtual bool OnRemove_Implementation(
        AActor* MyTarget,
        const FGameplayCueParameters& Parameters) override;
};
```

### 5.4 Cue Rules

```
DO:
  → Use cues for all VFX/sound
  → Pass magnitude for scaling effects
  → Use Notify_Static for one-shot effects (hit sparks)
  → Use Notify_Actor for looping effects (fire, aura)

DON'T:
  → Put game logic in cues — they can be skipped
  → Use cues to modify attributes
  → Rely on cue execution order
```

---

## 6. COOLDOWNS AND COSTS

### 6.1 Cost Effect

Create a Gameplay Effect (Instant duration):
- Modifier: Mana, Add, -10 (costs 10 mana)
- Assign in ability's `CostGameplayEffectClass`

### 6.2 Cooldown Effect

Create a Gameplay Effect (Duration):
- Duration: 5 seconds
- Grant tag: `Cooldown.Ability.Fireball` (blocks re-activation)
- Assign in ability's `CooldownGameplayEffectClass`

```cpp
// Check remaining cooldown
float GetCooldownRemaining() const
{
    if (!AbilitySystemComponent) return 0.f;

    FGameplayTagContainer CooldownTags;
    GetCooldownGameplayEffect()->InheritableOwnedTagsContainer.GetAllGameplayTags(CooldownTags);

    FGameplayEffectQuery Query =
        FGameplayEffectQuery::MakeQuery_MatchAnyOwningTags(CooldownTags);

    TArray<float> Durations = AbilitySystemComponent->GetActiveEffectsTimeRemaining(Query);
    return Durations.Num() > 0 ? Durations[0] : 0.f;
}
```

---

## 7. ABILITY INPUT BINDING

```cpp
// In Character SetupPlayerInputComponent:
void AMyCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent);
    if (!EIC || !AbilitySystemComponent) return;

    // Bind input to ability by tag
    EIC->BindAction(JumpAction, ETriggerEvent::Started, this,
        &AMyCharacter::OnJumpInputPressed);
}

void AMyCharacter::OnJumpInputPressed()
{
    if (!AbilitySystemComponent) return;

    // Activate by tag
    FGameplayTagContainer TagContainer;
    TagContainer.AddTag(FGameplayTag::RequestGameplayTag("Ability.Jump"));
    AbilitySystemComponent->TryActivateAbilitiesByTag(TagContainer);
}
```

---

## 8. AGENT RULES

- Ability ends immediately → AbilityTask not started or EndAbility called too early (Section 2)
- CommitAbility fails → cost or cooldown preventing activation, check attribute values
- ExecCalc not applying → check attribute capture definitions match AttributeSet (Section 4)
- Cue not firing → tag must start with "GameplayCue.", check tag registration
- SetByCaller fails → tag must match exactly between spec and effect asset
- Cooldown not working → cooldown effect must grant the blocking tag
- Cost not deducting → verify CostGameplayEffectClass is set in ability defaults
- AbilityTask delegate not firing → ReadyForActivation() not called (Section 2.3)
