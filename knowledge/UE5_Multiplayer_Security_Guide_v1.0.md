# UE5 Multiplayer Security Guide v1.0

---

## 1. WHY IT MATTERS

Security vulnerabilities in UE5 multiplayer projects typically look like:
- Score manipulation (client writing its own score)
- Damage cheating (client controlling damage amount)
- Location teleport (client forcing server to accept its position)
- Inventory exploit (client claiming to use an item it doesn't have)

The vast majority of these vulnerabilities come from a few core patterns.

---

## 2. THE GOLDEN RULE — WHO DECIDES?

```
GOLDEN RULE: Every decision that affects game state is made on the server.
The client only:
  - Sends input (tells the server what it wants to do)
  - Produces visual/audio effects (cosmetic only)
  - Predicts (to hide latency — awaits server confirmation)
```

---

## 3. VULNERABILITY CATEGORIES

---

### CATEGORY 1 — Unauthorized Server RPC

**Risk:** Client sends arbitrary parameters to a Server RPC.

```cpp
// ❌ VULNERABLE — client can set Amount to anything
UFUNCTION(Server, Reliable)
void ServerDealDamage(float Amount);

void AMyChar::ServerDealDamage_Implementation(float Amount)
{
    Target->Health -= Amount;  // 9999% damage is possible
}
```

**Fix — add _Validate function:**
```cpp
// ✅ SECURE
UFUNCTION(Server, Reliable, WithValidation)
void ServerDealDamage(float Amount);

bool AMyChar::ServerDealDamage_Validate(float Amount)
{
    // Check reasonable bounds
    return Amount > 0.f && Amount <= MaxSingleHitDamage;
}

void AMyChar::ServerDealDamage_Implementation(float Amount)
{
    // Validate passed — apply the operation
    Target->Health -= Amount;
}
```

**Extra security — calculate independently on server:**
```cpp
void AMyChar::ServerFireWeapon_Implementation()
{
    // Don't use what the client said the damage is
    // Calculate from the server's own weapon data:
    float Damage = GetEquippedWeapon()->GetBaseDamage();
    ApplyDamage(Target, Damage);
}
```

---

### CATEGORY 2 — Client-side Game Logic

**Risk:** Critical game logic runs without a HasAuthority() check.

```cpp
// ❌ VULNERABLE — runs on both server and client
void AMyChar::OnHit(float Damage)
{
    Health -= Damage;  // Client is reducing its own health
    if (Health <= 0) Die();
}
```

**Fix:**
```cpp
// ✅ SECURE
void AMyChar::OnHit(float Damage)
{
    if (!HasAuthority()) return;  // Server only
    
    Health -= Damage;
    if (Health <= 0) Die();
}
```

**Operations that ALWAYS require HasAuthority():**
- Damage / death
- Score changes
- Inventory add / remove
- Spawn / Destroy
- Match state changes (win / lose)
- Currency / resource changes

---

### CATEGORY 3 — Unreplicated Critical State

**Risk:** Changes on the server never reach the clients.

```cpp
// ❌ VULNERABLE — client always sees 100
float Health;  // No Replicated

// ✅ SECURE
UPROPERTY(ReplicatedUsing=OnRep_Health)
float Health;

void AMyChar::GetLifetimeReplicatedProps(
    TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION_NOTIFY(AMyChar, Health, COND_None, REPNOTIFY_Always);
}

void AMyChar::OnRep_Health()
{
    UpdateHealthUI();
}
```

**Why REPNOTIFY_Always matters:**
If a value is set to the same value it already has (e.g. 100→100), `REPNOTIFY_Changes` won't call OnRep. Use `REPNOTIFY_Always` for reliable UI.

---

### CATEGORY 4 — RPC on Wrong Actor

**Risk:** Client calls a Server RPC on an actor it doesn't own — silently dropped by the server.

```cpp
// ❌ SILENT FAIL — client doesn't own this actor
SomeWorldActor->ServerDoThing();  // Never reaches the server

// ✅ CORRECT — call the RPC on an owned actor
// Through PlayerController or Character:
GetController<AMyController>()->ServerRequestInteract(SomeWorldActor);
```

**RPC Ownership Rules:**
```
For a client to call a Server RPC, it must either:
  - Be the Owner of the actor (PlayerController is the owner)
  - OR the actor must be the client's Pawn/Character

PlayerController → always owned by the client
Character/Pawn  → owned by the client after possession
World actors (enemy, pickup, door) → not owned, RPCs will be silently dropped
```

**Correct pattern for interacting with world actors:**
```cpp
// Client: define Server RPC on PlayerController
UFUNCTION(Server, Reliable, WithValidation)
void ServerInteractWithActor(AActor* Target);

// Server: validation + action
bool AMyController::ServerInteractWithActor_Validate(AActor* Target)
{
    // Distance check — is the player close enough?
    return Target && GetPawn() &&
           FVector::Dist(GetPawn()->GetActorLocation(),
                        Target->GetActorLocation()) < InteractRange;
}

void AMyController::ServerInteractWithActor_Implementation(AActor* Target)
{
    if (IInteractable* I = Cast<IInteractable>(Target))
        I->Interact(GetPawn());
}
```

---

### CATEGORY 5 — Location Manipulation

**Risk:** Client can force the server to accept its position.

```cpp
// ❌ VULNERABLE — client can teleport
UFUNCTION(Server, Reliable)
void ServerSetLocation(FVector NewLocation);

void AMyChar::ServerSetLocation_Implementation(FVector NewLocation)
{
    SetActorLocation(NewLocation);  // No validation!
}
```

**Fix:**
```cpp
// ✅ SECURE — maximum movement distance check
bool AMyChar::ServerSetLocation_Validate(FVector NewLocation)
{
    float MaxMoveDist = GetMovementComponent()->MaxSpeed *
                        GetWorld()->GetDeltaSeconds() * 1.5f;  // 50% tolerance
    return FVector::Dist(GetActorLocation(), NewLocation) <= MaxMoveDist;
}
```

**Alternative:** Use CharacterMovementComponent's built-in anti-cheat:
```cpp
// CharacterMovementComponent already does server-side position correction
// Avoid writing a custom ServerSetLocation
// Trust CharacterMovement's replication instead
```

---

### CATEGORY 6 — GAS Security Issues

**Risk:** LocalPredicted abilities in GAS can be exploited.

```cpp
// ❌ RISKY — client can always activate the ability
NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::LocalPredicted;
// Cost check only runs on the client
```

**GAS Security Patterns:**
```cpp
// For abilities requiring mana/resources — server confirmation required
NetExecutionPolicy = EGameplayAbilityNetExecutionPolicy::ServerInitiated;

// Validate CanActivateAbility on server too
bool UMyAbility::CanActivateAbility(
    const FGameplayAbilitySpecHandle Handle,
    const FGameplayAbilityActorInfo* ActorInfo, ...) const
{
    if (!Super::CanActivateAbility(Handle, ActorInfo, ...)) return false;

    // Mana check
    UMyAttributeSet* Attrs = Cast<UMyAttributeSet>(
        ActorInfo->AbilitySystemComponent->GetAttributeSet(
            UMyAttributeSet::StaticClass()));
    return Attrs && Attrs->GetMana() >= ManaCost;
}
```

---

### CATEGORY 7 — Wrong Replication Mode Selection

**Risk:** Wrong replication mode wastes bandwidth or creates security gaps.

```cpp
// ReplicationMode selection guide:
AbilitySystemComponent->SetReplicationMode(
    EGameplayEffectReplicationMode::Full     // All GE replication
    // Full    → single player or small co-op only (<4 players)
    // Mixed   → player-controlled: GE + cues; AI: cues only — RECOMMENDED
    // Minimal → large multiplayer (20+ players) — cues only
);

// Mixed for ASC on PlayerState:
AbilitySystemComponent->SetReplicationMode(
    EGameplayEffectReplicationMode::Mixed);

// Minimal for ASC on AI characters:
AbilitySystemComponent->SetReplicationMode(
    EGameplayEffectReplicationMode::Minimal);
```

---

## 4. QUICK SCAN — CHECKLIST WHEN CODE ARRIVES

```
□ Do Server RPCs have _Validate functions?
□ Is critical logic protected with HasAuthority()?
□ Are gameplay-critical variables marked with UPROPERTY(Replicated...)?
□ Are RPCs called on the correct actor (owned actor)?
□ Is location/rotation manipulation being validated?
□ Is GAS ability activation also validated on the server?
□ Are input parameters independently calculated on the server?
```

---

## 5. REPLICATION CHEAT SHEET

| What to do | How |
|---|---|
| Variable server→all clients | `UPROPERTY(Replicated)` + GetLifetimeReplicatedProps |
| Variable + callback | `UPROPERTY(ReplicatedUsing=OnRep_X)` + `REPNOTIFY_Always` |
| Client→Server call | `UFUNCTION(Server, Reliable, WithValidation)` |
| Server→owning client call | `UFUNCTION(Client, Reliable)` |
| Server→all clients call | `UFUNCTION(NetMulticast, Unreliable)` |
| Check if running on server | `HasAuthority()` |
| Check if running on owning client | `IsLocallyControlled()` |
| Only run on server | `if (!HasAuthority()) return;` |

---

## 6. DEBUG COMMANDS

```
# Replication debug
net.ShowDebugReplication 1        -- Show replicated variables
LogNet all                        -- All network log

# RPC debug
log LogNetPlayerMovement all      -- Movement replication
log LogRepTraffic all             -- All rep traffic

# GAS network debug
log LogAbilitySystem all          -- GAS network events
```

---

## 7. AGENT RULES

- Server RPC seen → check for _Validate (CATEGORY 1)
- Critical logic without HasAuthority() → CATEGORY 2 warning
- Gameplay variable without Replicated → CATEGORY 3 warning
- Client calling RPC on world actor → CATEGORY 4 warning
- GAS + multiplayer → always check replication mode and ability validation
- Server RPC pattern through PlayerController → correct approach, confirm it
- LocalPredicted + resource cost → suggest ServerInitiated
