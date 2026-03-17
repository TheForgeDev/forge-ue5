# UE5 Multiplayer & Replication — Deep Dive Knowledge File
### UE5 Dev Agent — Knowledge v1.0

---

## CORE CONCEPTS

### Network Roles

Every Actor in a multiplayer game has a role:

```
ROLE_Authority      // Server — owns the truth
ROLE_SimulatedProxy // Client — receives updates, simulates between them
ROLE_AutonomousProxy // Owning client — can send input to server
```

Check role in code:
```cpp
if (HasAuthority())           // Are we the server?
if (IsLocallyControlled())    // Is this our pawn?
if (GetLocalRole() == ROLE_AutonomousProxy) // Are we the owning client?
```

**Rule:** Logic that changes game state → server only. Cosmetics → can run on all.

---

### Server Types

**Dedicated Server:**
- No rendering, no player on server machine
- Best for competitive games
- Build with `-server` flag

**Listen Server:**
- One player hosts AND plays
- Easier to set up, worse for competitive
- Good for co-op games

---

## REPLICATION

### Basic Actor Replication

```cpp
// Constructor — enable replication
AMyActor::AMyActor()
{
    bReplicates = true;
    bReplicateMovement = true; // replicate transform automatically
}
```

### Variable Replication

```cpp
// .h
UPROPERTY(Replicated)
float Health;

UPROPERTY(ReplicatedUsing = OnRep_Health) // calls function when value changes on client
float Health;

UFUNCTION()
void OnRep_Health(); // called on CLIENT when Health changes
```

```cpp
// .cpp — REQUIRED
void AMyActor::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);

    DOREPLIFETIME(AMyActor, Health);                          // replicate to everyone
    DOREPLIFETIME_CONDITION(AMyActor, Health, COND_OwnerOnly); // only to owning client
}
```

### Replication Conditions

```
COND_None           // Always replicate
COND_OwnerOnly      // Only to owning client
COND_SkipOwner      // Everyone except owner
COND_SimulatedOnly  // Only simulated proxies
COND_InitialOnly    // Only on first replication
COND_ServerOnly     // Never replicate (server-only variable)
COND_Custom         // Custom condition via SetCustomIsActiveOverride
```

---

## RPCs (Remote Procedure Calls)

### RPC Types

```cpp
// Client calls this → runs on SERVER
UFUNCTION(Server, Reliable)
void ServerDoSomething();

// Server calls this → runs on OWNING CLIENT only
UFUNCTION(Client, Reliable)
void ClientDoSomething();

// Server calls this → runs on ALL clients (and server)
UFUNCTION(NetMulticast, Reliable)
void MulticastDoSomething();
```

### Reliable vs Unreliable

```cpp
UFUNCTION(Server, Reliable)   // Guaranteed delivery — use for important actions
UFUNCTION(Server, Unreliable) // No guarantee — use for frequent updates (movement)
```

### Implementation Pattern

```cpp
// .h
UFUNCTION(Server, Reliable)
void ServerFire();

// .cpp — always add _Implementation
void AMyCharacter::ServerFire_Implementation()
{
    // This runs on server
    SpawnProjectile();
}

// Optional: validation function
bool AMyCharacter::ServerFire_Validate()
{
    // Return false to kick the client (cheat detection)
    return true;
}
```

### When to use which RPC

| Situation | RPC Type |
|---|---|
| Player presses button → server should know | Server |
| Server event → show effect on all clients | NetMulticast |
| Server → specific client notification | Client |
| Movement / frequent updates | Unreliable |
| Firing / ability activation | Reliable |

---

## COMMON REPLICATION MISTAKES

---

### Mistake: Calling Server RPC from server

Server RPCs must be called from the **owning client**.
If called from server → silently does nothing.

```cpp
// WRONG — calling Server RPC on server:
if (HasAuthority())
{
    ServerDoSomething(); // does nothing
}

// RIGHT — just call the function directly on server:
if (HasAuthority())
{
    DoSomething(); // call implementation directly
}
```

---

### Mistake: Forgetting _Implementation suffix

```cpp
// WRONG:
void AMyActor::ServerDoSomething()
{
    // code here — this is actually the declaration wrapper
}

// RIGHT:
void AMyActor::ServerDoSomething_Implementation()
{
    // actual code here
}
```

---

### Mistake: Replicating every frame

```cpp
// WRONG — replicated variable changing every Tick:
void AMyActor::Tick(float DeltaTime)
{
    ReplicatedPosition = GetActorLocation(); // massive bandwidth usage
}

// RIGHT — use built-in movement replication:
bReplicateMovement = true; // handles position/rotation efficiently
```

---

### Mistake: OnRep not called on server

`OnRep_` functions are called **only on clients** when the replicated value changes.
Server sets the value but doesn't trigger OnRep.

```cpp
// If you need logic to run on BOTH server and client:
void AMyActor::SetHealth(float NewHealth)
{
    if (HasAuthority())
    {
        Health = NewHealth;
        OnHealthChanged(); // call manually on server
    }
    // OnRep_Health() handles client side automatically
}

void AMyActor::OnRep_Health()
{
    OnHealthChanged(); // called automatically on clients
}
```

---

### Mistake: Spawning actors on client

Actors spawned on clients are **not replicated** to other clients.
Always spawn on server.

```cpp
// WRONG — spawning on client:
void AMyCharacter::SpawnEffect()
{
    GetWorld()->SpawnActor<AMyEffect>(...); // only exists locally
}

// RIGHT — spawn on server, let replication handle the rest:
void AMyCharacter::ServerSpawnEffect_Implementation()
{
    GetWorld()->SpawnActor<AMyEffect>(...); // replicates to all clients
}
```

---

## ACTOR OWNERSHIP

Ownership determines who can call Server RPCs on an Actor.

```cpp
// Set owner:
MyActor->SetOwner(PlayerController);

// Check owner:
MyActor->GetOwner();
```

**Typical ownership chain:**
`PlayerController → Pawn → Weapons/Components owned by Pawn`

If an Actor has no owner → client cannot call Server RPCs on it.

---

## GAMEMODE, GAMESTATE, PLAYERSTATE

### Where things live

| Class | Exists on | Replicated | Use for |
|---|---|---|---|
| GameMode | Server only | No | Rules, game logic, spawning |
| GameState | Server + All Clients | Yes | Global game state (score, timer) |
| PlayerController | Server + Owning Client | Partial | Input, UI, client-specific |
| PlayerState | Server + All Clients | Yes | Per-player data (name, score, ping) |
| Pawn/Character | Server + All Clients | Yes | Player representation in world |

**Common mistake:** Putting game data in GameMode (server only) when clients need it → use GameState instead.

---

## NETWORK PROFILING

### Enable network stats:
```
stat net         // packets, bandwidth, actor channels
stat netchan     // per-channel stats
```

### Key metrics to watch:
- **Outgoing bandwidth** — total data sent per second
- **Actor channel count** — how many actors are replicating
- **Saturated** — if true, bandwidth limit hit, data is being dropped

### Reduce bandwidth:
```cpp
// Increase update frequency for less important actors:
NetUpdateFrequency = 10.0f;      // default 100, reduce for distant/static actors
MinNetUpdateFrequency = 2.0f;    // minimum even when nothing changes

// Only replicate when relevant:
DOREPLIFETIME_CONDITION(AMyActor, SomeVar, COND_SkipOwner);
```

---

## LISTEN SERVER vs DEDICATED SERVER DIFFERENCES

| Feature | Listen Server | Dedicated Server |
|---|---|---|
| Host plays | Yes | No |
| Performance | Lower (host also renders) | Higher |
| Cheating | Easier (host has authority + sees everything) | Harder |
| Setup complexity | Simple | Requires server build |
| Best for | Co-op, casual | Competitive, MMO |

**Code difference:**
On a Listen Server, the host's PlayerController has both Authority AND is LocallyControlled.
Always check both conditions separately when needed.

---

## REPLICATION GRAPH (Advanced)

Default replication evaluates every actor for every connection every frame.
For large worlds (100+ players), use Replication Graph.

```cpp
// Enable in DefaultEngine.ini:
[/Script/OnlineSubsystemUtils.IpNetDriver]
ReplicationDriverClassName="/Script/MyGame.MyReplicationGraph"
```

Replication Graph lets you:
- Spatially cull actors (only replicate nearby actors)
- Group static actors (replicate once, not every frame)
- Custom rules per actor class

---

## LAG COMPENSATION BASICS

Player fires on their screen → by the time server processes, target has moved.

**Client-side prediction:**
Client simulates movement immediately, server corrects if wrong.
UE5's CharacterMovementComponent does this automatically for movement.

**Server-side rewind (manual):**
Server rewinds actor positions to the time of the client's action.
Must implement manually for abilities/shooting.

Basic pattern:
```cpp
// Store position history on server:
struct FPositionRecord
{
    FVector Position;
    float Timestamp;
};
TArray<FPositionRecord> PositionHistory;

// On hit validation — rewind to client's timestamp and check
```

---

## QUICK REFERENCE — MOST COMMON PATTERNS

### Health system with replication:
```cpp
// .h
UPROPERTY(ReplicatedUsing = OnRep_Health)
float Health = 100.f;

UFUNCTION()
void OnRep_Health(float OldHealth); // old value passed as param

UFUNCTION(Server, Reliable)
void ServerTakeDamage(float Amount);

// .cpp
void AMyCharacter::ServerTakeDamage_Implementation(float Amount)
{
    Health = FMath::Clamp(Health - Amount, 0.f, 100.f);
    // OnRep_Health fires automatically on clients
    OnRep_Health(Health + Amount); // call manually on server too
}

void AMyCharacter::OnRep_Health(float OldHealth)
{
    // Update UI, play effects — runs on clients (and manually on server)
    UpdateHealthBar();
    if (Health <= 0.f && OldHealth > 0.f)
    {
        PlayDeathAnimation();
    }
}
```

### Pickup with authority check:
```cpp
void APickup::OnOverlapBegin(UPrimitiveComponent* OverlappedComp,
    AActor* OtherActor, ...)
{
    if (!HasAuthority()) return; // server only

    AMyCharacter* Character = Cast<AMyCharacter>(OtherActor);
    if (IsValid(Character))
    {
        Character->AddItem(ItemData);
        Destroy(); // replicates to all clients
    }
}
```
