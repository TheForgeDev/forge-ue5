# UE5 GAS — Multiplayer Deep Dive v1.0

---

## 1. THE TWO-AUTHORITY PROBLEM IN GAS

GAS abilities can run on both client and server simultaneously. This is intentional — client predicts, server verifies.

```
Client (Autonomous Proxy):
  TryActivateAbility() → runs immediately
  Applies predicted effects
  Shows VFX/animation instantly
  Holds prediction key
  Waits for server confirmation

Server:
  Receives RPC
  Runs CanActivateAbility() independently
  Applies authoritative effects
  Confirms or rejects client prediction
```

If server rejects: client rolls back. Player sees a "snap" — ability undone.
If server confirms: client prediction validated. No visible correction.

---

## 2. PREDICTION — HOW IT WORKS

### Prediction keys

Every predicted ability activation gets a `FPredictionKey`. This key tracks all predicted state changes so they can be undone if server rejects.

```cpp
// You don't manage prediction keys manually in most cases.
// GAS handles them internally when using:
// - LocalPredicted activation policy
// - AbilityTask with prediction

// But you need to understand them for debugging:
// Log prediction key activity:
AbilitySystemComponent->AbilityActivatedCallbacks.AddUObject(
    this, &AMyCharacter::OnAbilityActivated);

void AMyCharacter::OnAbilityActivated(UGameplayAbility* Ability)
{
    UE_LOG(LogTemp, Verbose,
        TEXT("Ability activated: %s, Predicted: %s"),
        *Ability->GetName(),
        Ability->IsInstantiated() ? TEXT("Yes") : TEXT("No"));
}
```

### Activation policies

```
Server             → Runs only on server. No prediction. Safer.
LocalPredicted     → Runs on client immediately, confirmed by server.
LocalOnly          → Runs only on owning client. No server copy.
ServerInitiated    → Server activates, replicates to client.
ServerOnly         → Same as Server. Explicit naming.
```

**Most abilities should be LocalPredicted.** This gives responsive gameplay while maintaining server authority.

---

## 3. REPLICATED EVENTS AND ABILITY TASKS

Some AbilityTasks must replicate their completion event to stay synchronized.

### WaitTargetData — prediction-safe targeting

```cpp
// This task predicts on client, confirms on server
UAbilityTask_WaitTargetData* Task =
    UAbilityTask_WaitTargetData::WaitTargetData(
        this,
        NAME_None,
        EGameplayTargetingConfirmation::Instant,
        AGameplayAbilityTargetActor_SingleLineTrace::StaticClass()
    );

Task->ValidData.AddDynamic(this, &UMyAbility::OnTargetDataReady);
Task->Cancelled.AddDynamic(this, &UMyAbility::OnTargetCancelled);
Task->ReadyForActivation();

// OnTargetDataReady fires on BOTH client and server
// Client fires first (predicted), server fires after RPC
void UMyAbility::OnTargetDataReady(
    const FGameplayAbilityTargetDataHandle& Data)
{
    // IMPORTANT: CommitAbility here, not in ActivateAbility
    if (!CommitAbility(CurrentSpecHandle, CurrentActorInfo,
        CurrentActivationInfo))
    {
        EndAbility(CurrentSpecHandle, CurrentActorInfo,
            CurrentActivationInfo, true, true);
        return;
    }

    // Apply damage effect using target data
    ApplyGameplayEffectToTarget(CurrentSpecHandle, CurrentActorInfo,
        CurrentActivationInfo, Data, DamageEffectClass, 1.f);

    EndAbility(CurrentSpecHandle, CurrentActorInfo,
        CurrentActivationInfo, true, false);
}
```

---

## 4. EFFECT REPLICATION — WHAT REPLICATES WHERE

### Mixed mode (recommended for players):

```
GameplayEffects:
  → Replicate ONLY to owning client
  → Other clients: no effect data

GameplayCues:
  → Replicate to ALL clients
  → This is how other players see VFX/sound

Gameplay Tags (from effects):
  → Replicate to owning client only
  → Other clients see tags via GameplayTag replication on actor
```

### What this means in practice:

```cpp
// Other clients cannot read your health via GAS
// They must read it via replicated Actor property

// WRONG: asking target's ASC for health from a non-owner client
float TargetHealth = TargetASC->GetNumericAttribute(
    UMyAttributeSet::GetHealthAttribute()); // Returns 0 on non-owner

// CORRECT: replicate health separately for UI purposes
UPROPERTY(ReplicatedUsing=OnRep_Health)
float ReplicatedHealth;
```

---

## 5. NETWORK OPTIMIZATION

### 5.1 NetUpdateFrequency

PlayerState default frequency is too low for responsive GAS:

```cpp
// PlayerState constructor:
NetUpdateFrequency = 100.f;    // Minimum for GAS responsiveness
MinNetUpdateFrequency = 33.f;  // Fallback when nothing changes
```

Why it matters: attribute changes replicate on the next network tick. At 1Hz (default), 1 second delay. At 100Hz, 10ms delay.

### 5.2 Bandwidth considerations

Each active effect adds replication overhead. Optimize:

```cpp
// Don't stack infinite effects unnecessarily
// Use tags instead of infinite effects for simple state tracking

// BAD: infinite effect just to grant a tag
// GOOD: Add tag directly
AbilitySystemComponent->AddLooseGameplayTag(
    FGameplayTag::RequestGameplayTag("Status.Grounded"));

// Remove when done
AbilitySystemComponent->RemoveLooseGameplayTag(
    FGameplayTag::RequestGameplayTag("Status.Grounded"));
```

### 5.3 Attribute replication — REPNOTIFY_Always is critical

```cpp
// Without REPNOTIFY_Always:
// If health goes 100 → 50 → 100, client only fires OnRep once
// (value didn't change from client's perspective)

// WITH REPNOTIFY_Always:
// Every server-side change fires OnRep on client
// Required for proper GAS attribute synchronization

DOREPLIFETIME_CONDITION_NOTIFY(
    UMyAttributeSet, Health,
    COND_None,           // replicate to all connections
    REPNOTIFY_Always     // fire OnRep even if value unchanged
);
```

---

## 6. ABILITY GRANTING ON RESPAWN

The most common multiplayer GAS bug. After respawn:

```
❌ Common mistake:
   PossessedBy fires
   GiveDefaultAbilities() called
   Abilities granted AGAIN (duplicates)
   Player has 2x jump, 2x fireball

✓ Correct pattern:
   bAbilitiesGranted flag prevents double-granting
   InitAbilityActorInfo called (safe to call multiple times)
   GiveDefaultAbilities() only if !bAbilitiesGranted
```

```cpp
// In Character:
bool bAbilitiesGranted = false;

void AMyCharacter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);

    // Init is safe to call multiple times
    AbilitySystemComponent->InitAbilityActorInfo(PlayerState, this);

    if (HasAuthority() && !bAbilitiesGranted)
    {
        GiveDefaultAbilities();
        bAbilitiesGranted = true;
    }
}

// On death — reset for next respawn
void AMyCharacter::OnDeath()
{
    bAbilitiesGranted = false;
    // Don't clear abilities here — they survive on PlayerState ASC
    // Clear them from PlayerState only if you want fresh start on respawn
}
```

---

## 7. DESYNC DETECTION AND RECOVERY

### When does desync happen?

1. Client predicts ability activation
2. Server-side condition is different (mana lower due to another effect)
3. Server rejects — client predicted incorrectly
4. GAS rolls back client prediction

### How to detect:

```cpp
// Override in ASC subclass:
virtual void OnClientActivateAbilityFailed(
    const UGameplayAbility* Ability,
    int16 PredictionKey) override
{
    Super::OnClientActivateAbilityFailed(Ability, PredictionKey);

    UE_LOG(LogTemp, Warning,
        TEXT("[DESYNC] Ability prediction rejected: %s (key: %d)"),
        *Ability->GetName(), PredictionKey);

    // Trigger UI feedback — "ability failed" flash
}
```

### Common desync causes:

```
1. Mana consumed by another predicted ability simultaneously
   → Both abilities predicted at same time, only one can succeed

2. Effect applied mid-prediction
   → DoT ticked between client prediction and server verification

3. Cooldown race condition
   → Ability activated at almost exactly same time on client and server

4. Network jitter
   → Packet arrived out of order
```

### Reducing desync:

```cpp
// Give prediction window — tolerance for timing differences
AbilitySystemComponent->ClientActivateAbilitySucceedWithEventData(
    Handle, PredictionKey, EventData);

// Increase ASC tick rate for tighter prediction
AbilitySystemComponent->SetNetAddressable(); // Required for prediction
```

---

## 8. MULTIPLAYER SECURITY IN GAS

### Never trust client ability activation data

```cpp
// WRONG: accepting damage value from client
void UMyDamageAbility::ActivateAbility(...)
{
    float ClientDamage = GetClientDamageValue(); // NEVER do this
    ApplyDamage(ClientDamage);
}

// CORRECT: server computes damage from authoritative data
void UMyDamageAbility::ActivateAbility(...)
{
    // Server reads from its own AttributeSet
    float AttackPower = AbilitySystemComponent->GetNumericAttribute(
        UMyAttributeSet::GetAttackPowerAttribute());
    ApplyDamageFromServer(AttackPower);
}
```

### Validate target data on server

```cpp
void UMyAbility::OnTargetDataReady(
    const FGameplayAbilityTargetDataHandle& Data)
{
    // This fires on server — validate the target location
    for (int32 i = 0; i < Data.Num(); ++i)
    {
        if (!Data.IsValid(i)) continue;

        const FGameplayAbilityTargetData* TargetData = Data.Get(i);
        FHitResult HitResult;
        if (!TargetData->GetHitResult(&HitResult)) continue;

        // Validate distance — don't trust client position
        float Distance = FVector::Dist(
            GetAvatarActorFromActorInfo()->GetActorLocation(),
            HitResult.Location);

        if (Distance > MaxAbilityRange * 1.2f) // 20% tolerance
        {
            UE_LOG(LogTemp, Warning,
                TEXT("[Security] Ability range exceeded: %.0f > %.0f"),
                Distance, MaxAbilityRange);
            EndAbility(..., true, true); // cancel
            return;
        }
    }

    // Safe to apply
    ApplyDamage(Data);
}
```

### Server-side ability validation

```cpp
// Override in ability:
virtual bool CanActivateAbility(
    const FGameplayAbilitySpecHandle Handle,
    const FGameplayAbilityActorInfo* ActorInfo,
    const FGameplayTagContainer* SourceTags,
    const FGameplayTagContainer* TargetTags,
    OUT FGameplayTagContainer* OptionalRelevantTags) const override
{
    if (!Super::CanActivateAbility(Handle, ActorInfo,
        SourceTags, TargetTags, OptionalRelevantTags))
    {
        return false;
    }

    // Custom server-side validation
    if (ActorInfo->IsNetAuthority())
    {
        // Verify preconditions from server's authoritative state
        AMyPlayerState* PS = Cast<AMyPlayerState>(ActorInfo->OwnerActor.Get());
        if (!PS || PS->IsSpectator()) return false;
    }

    return true;
}
```

---

## 9. AGENT RULES

- Ability activates on client but not server → check activation policy, ensure LocalPredicted
- Prediction snap/rollback → expected behavior when server rejects, reduce by tightening conditions
- Abilities granted twice on respawn → bAbilitiesGranted guard (Section 6)
- Attribute not updating on remote clients → REPNOTIFY_Always missing (Section 5.3)
- Other clients can't read health → replicate health separately, not via GAS (Section 4)
- Desync after lag spike → OnClientActivateAbilityFailed log (Section 7)
- Target data exploitable → always validate distance server-side (Section 8)
- PlayerState latency → NetUpdateFrequency = 100 (Section 5.1)
- NetMulticast cue not firing → check replication mode, Mixed required for player cues
- Server rejecting valid activation → check mana/cooldown race condition (Section 7)
