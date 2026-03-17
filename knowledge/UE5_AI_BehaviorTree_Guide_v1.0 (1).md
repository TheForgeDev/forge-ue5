# UE5 AI & Behavior Tree — Error & Setup Guide
### UE5 Dev Agent — Knowledge v1.0

---

## CORE CONCEPTS

**Behavior Tree (BT)** — decision-making logic tree
**Blackboard (BB)** — AI's memory, stores data as key-value pairs
**AIController** — runs the BT, interfaces with Pawn
**Perception** — how AI detects players (sight, hearing, damage)

**Node types:**
```
Composite   — controls execution flow
  Selector  → tries children left to right, stops at first SUCCESS
  Sequence  → runs children left to right, stops at first FAILURE

Task        — leaf node, does actual work (MoveTo, Wait, custom)
Decorator   — condition gate on any node
Service     — ticks periodically while branch is active, updates BB
```

**Build.cs required:**
```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "AIModule",
    "NavigationSystem",
    "GameplayTasks", // for AI tasks
});
```

---

## CHAPTER 1: SETUP ERRORS

---

### AI1 — Behavior Tree Not Starting
**Symptom:** AI stands still, BT never executes

**Checklist:**
```
1. AIController assigned to Pawn?
   Pawn → Details → Pawn → AI Controller Class

2. Auto Possess AI set correctly?
   Pawn → Details → Pawn → Auto Possess AI → PlacedInWorldOrSpawned

3. RunBehaviorTree called in AIController?
4. NavMesh present in level? (NavMeshBoundsVolume)
5. BT asset assigned?
```

```cpp
// AIController — start BT:
void AMyAIController::OnPossess(APawn* InPawn)
{
    Super::OnPossess(InPawn);
    if (BehaviorTree)
    {
        RunBehaviorTree(BehaviorTree);
    }
}

// Or use BeginPlay:
void AMyAIController::BeginPlay()
{
    Super::BeginPlay();
    if (BehaviorTree && GetPawn())
    {
        RunBehaviorTree(BehaviorTree);
    }
}
```

---

### AI2 — Blackboard Component Null
**Symptom:** Crash or null when accessing Blackboard

```cpp
// WRONG — getting blackboard before BT starts:
void AMyAIController::BeginPlay()
{
    Super::BeginPlay();
    GetBlackboardComponent()->SetValueAsVector(...); // null — BT not started yet
}

// RIGHT — access after RunBehaviorTree:
void AMyAIController::OnPossess(APawn* InPawn)
{
    Super::OnPossess(InPawn);
    if (BehaviorTree)
    {
        RunBehaviorTree(BehaviorTree); // initializes Blackboard
        // Now safe to access:
        GetBlackboardComponent()->SetValueAsVector(TEXT("PatrolPoint"), StartLocation);
    }
}
```

---

### AI3 — Custom Task FinishExecute Never Called
**Symptom:** AI freezes on custom task indefinitely
**Most common BT mistake**

Every custom Task MUST call FinishTask/FinishExecute.
If not called → task runs forever, tree stops.

```cpp
UCLASS()
class UMyBTTask : public UBTTaskNode
{
    GENERATED_BODY()

    virtual EBTNodeResult::Type ExecuteTask(UBehaviorTreeComponent& OwnerComp,
        uint8* NodeMemory) override
    {
        // Do work...
        AAIController* Controller = OwnerComp.GetAIOwner();
        if (!Controller) return EBTNodeResult::Failed;

        // For instant tasks — return result directly:
        return EBTNodeResult::Succeeded;

        // For latent tasks (async) — return InProgress and call later:
        // return EBTNodeResult::InProgress;
        // ... later call:
        // FinishLatentTask(OwnerComp, EBTNodeResult::Succeeded);
    }
};
```

**Task result types:**
```
Succeeded  → task done, tree continues
Failed     → task failed, Sequence stops, Selector tries next
InProgress → still running, call FinishLatentTask later
Aborted    → only returned from AbortTask override
```

---

### AI4 — BT Looping / Restarting Constantly
**Symptom:** AI flickers, BT restarts every frame

**Cause:** A decorator or task is instantly succeeding/failing,
causing the tree to restart from root immediately.

```
Common causes:
1. Decorator condition always evaluates to same result
2. Task returns Succeeded/Failed instantly instead of InProgress
3. Blackboard key checked by decorator changes every tick

Fix:
- Add a Wait task after the problematic branch
- Use Event-driven observation on decorators instead of constant check
- For latent actions: return InProgress, complete via FinishLatentTask
```

---

### AI5 — MoveTo Task Failing / AI Not Moving
**Checklist:**
```
1. NavMesh built and covers target area?
   Build → Build Paths  (or press P to visualize)

2. Target location reachable on navmesh?
   DrawDebugSphere at target location, check if on navmesh

3. Agent radius vs navmesh agent size?
   Project Settings → Navigation → Default Agent Radius

4. Character Movement component present?
   MoveTo uses CharacterMovementComponent for pathfinding

5. NavMesh up to date?
   Runtime generation: Project Settings → Navigation → Runtime Generation
```

```cpp
// C++ MoveTo (in Task or AIController):
FAIMoveRequest MoveRequest;
MoveRequest.SetGoalLocation(TargetLocation);
MoveRequest.SetAcceptanceRadius(50.f);
MoveRequest.SetAllowPartialPath(true); // try partial path if full not available

GetPathFollowingComponent()->RequestMove(MoveRequest, ...);
// OR simpler:
MoveToLocation(TargetLocation, 50.f);
```

---

### AI6 — Perception Not Detecting Player
**Setup checklist:**

```cpp
// AIController — setup perception:
void AMyAIController::SetupPerception()
{
    PerceptionComponent = CreateDefaultSubobject<UAIPerceptionComponent>(
        TEXT("PerceptionComp"));

    // Sight config:
    UAISenseConfig_Sight* SightConfig = CreateDefaultSubobject<UAISenseConfig_Sight>(
        TEXT("SightConfig"));
    SightConfig->SightRadius = 1000.f;
    SightConfig->LoseSightRadius = 1500.f;
    SightConfig->PeripheralVisionAngleDegrees = 60.f;
    SightConfig->DetectionByAffiliation.bDetectEnemies = true;
    SightConfig->DetectionByAffiliation.bDetectNeutrals = true;
    SightConfig->DetectionByAffiliation.bDetectFriendlies = true;

    PerceptionComponent->ConfigureSense(*SightConfig);
    PerceptionComponent->SetDominantSense(SightConfig->GetSenseImplementation());

    // Bind callback:
    PerceptionComponent->OnTargetPerceptionUpdated.AddDynamic(
        this, &AMyAIController::OnTargetPerceptionUpdated);
}

// Target must have AIPerceptionStimuliSource component:
// Add to Player Blueprint or:
UAIPerceptionStimuliSourceComponent* StimuliSource = 
    PlayerActor->FindComponentByClass<UAIPerceptionStimuliSourceComponent>();
// If null, add one and register senses
```

**Common mistake:** Target actor has no `UAIPerceptionStimuliSourceComponent`.
Without it, AI senses can't detect it.

---

## CHAPTER 2: BLACKBOARD ERRORS

---

### AI7 — Wrong Blackboard Key Name
**Symptom:** SetValue/GetValue has no effect, key always default

Blackboard key names are case-sensitive.
A typo in `FName("TargetActor")` vs `FName("targetActor")` = different keys.

```cpp
// Declare key names as constants:
const FName AMyAIController::BB_TargetActor = TEXT("TargetActor");
const FName AMyAIController::BB_PatrolPoint = TEXT("PatrolPoint");

// Use constants everywhere:
GetBlackboardComponent()->SetValueAsObject(BB_TargetActor, PlayerActor);
GetBlackboardComponent()->SetValueAsVector(BB_PatrolPoint, PatrolLocation);
```

---

### AI8 — Blackboard Key Type Mismatch
**Symptom:** Value set but not read correctly

```cpp
// Actor reference → use SetValueAsObject / GetValueAsObject:
BB->SetValueAsObject(TEXT("Target"), TargetActor);
AActor* Target = Cast<AActor>(BB->GetValueAsObject(TEXT("Target")));

// Vector → SetValueAsVector / GetValueAsVector:
BB->SetValueAsVector(TEXT("Location"), FVector(100, 200, 0));

// Bool → SetValueAsBool / GetValueAsBool:
BB->SetValueAsBool(TEXT("CanSeePlayer"), true);

// Enum → SetValueAsEnum / GetValueAsEnum:
BB->SetValueAsEnum(TEXT("AIState"), (uint8)EAIState::Patrol);
```

---

## CHAPTER 3: C++ TASK / SERVICE / DECORATOR PATTERNS

---

### Custom Task — Full Pattern
```cpp
// .h
UCLASS()
class UBTTask_MyTask : public UBTTaskNode
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, Category = "Blackboard")
    FBlackboardKeySelector TargetKey; // exposed in BT editor

    virtual EBTNodeResult::Type ExecuteTask(
        UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
    virtual EBTNodeResult::Type AbortTask(
        UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) override;
};

// .cpp
EBTNodeResult::Type UBTTask_MyTask::ExecuteTask(
    UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory)
{
    AAIController* Controller = OwnerComp.GetAIOwner();
    UBlackboardComponent* BB = OwnerComp.GetBlackboardComponent();
    if (!Controller || !BB) return EBTNodeResult::Failed;

    AActor* Target = Cast<AActor>(BB->GetValueAsObject(TargetKey.SelectedKeyName));
    if (!IsValid(Target)) return EBTNodeResult::Failed;

    // Do work...
    return EBTNodeResult::Succeeded;
}
```

---

### Custom Service — Full Pattern
```cpp
UCLASS()
class UBTService_UpdateTarget : public UBTService
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere)
    FBlackboardKeySelector TargetKey;

    virtual void TickNode(UBehaviorTreeComponent& OwnerComp,
        uint8* NodeMemory, float DeltaSeconds) override
    {
        AAIController* Controller = OwnerComp.GetAIOwner();
        if (!Controller) return;

        // Find player and update blackboard:
        APawn* Player = UGameplayStatics::GetPlayerPawn(Controller, 0);
        OwnerComp.GetBlackboardComponent()->SetValueAsObject(
            TargetKey.SelectedKeyName, Player);
    }
};
```

---

### Custom Decorator — Full Pattern
```cpp
UCLASS()
class UBTDecorator_IsPlayerInRange : public UBTDecorator
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere)
    float MaxDistance = 500.f;

    UPROPERTY(EditAnywhere)
    FBlackboardKeySelector TargetKey;

    virtual bool CalculateRawConditionValue(
        UBehaviorTreeComponent& OwnerComp, uint8* NodeMemory) const override
    {
        AAIController* Controller = OwnerComp.GetAIOwner();
        if (!Controller || !Controller->GetPawn()) return false;

        AActor* Target = Cast<AActor>(
            OwnerComp.GetBlackboardComponent()->GetValueAsObject(
                TargetKey.SelectedKeyName));
        if (!IsValid(Target)) return false;

        float Distance = FVector::Dist(
            Controller->GetPawn()->GetActorLocation(),
            Target->GetActorLocation());
        return Distance <= MaxDistance;
    }
};
```

---

## CHAPTER 4: EQS ERRORS

---

### AI9 — EQS Not Finding Results
**Common causes:**
```
1. No NavMesh in query area
2. Tests filtering out all candidates
3. Generator not generating enough candidates
4. Context not returning valid actor

Debug: Enable EQS visual debugging
  ShowFlag.Navigation 1
  ai.debug.eqs 1
```

---

### AI10 — BTService_RunEQS Crash
**Known UE5 bug:**
`Ensure condition failed: MyMemory->RequestID != INDEX_NONE`

**Workaround:** Run EQS from C++ Task instead of BT Service,
or update to UE5.3+ where this is patched.

---

## COMMON AI ARCHITECTURE PATTERNS

### Pattern 1: Patrol + Chase
```
Root
└── Selector
    ├── Sequence (Chase — high priority)
    │   ├── Decorator: Is Target Valid (BB: TargetActor)
    │   ├── Service: Update Target Location
    │   └── Task: MoveTo (BB: TargetLocation)
    └── Sequence (Patrol — fallback)
        ├── Task: Find Next Patrol Point
        └── Task: MoveTo (BB: PatrolPoint)
```

### Pattern 2: Combat
```
Root
└── Selector
    ├── Sequence (Attack)
    │   ├── Decorator: Is In Attack Range
    │   └── Task: Attack
    ├── Sequence (Chase)
    │   ├── Decorator: Is Target Visible
    │   └── Task: MoveTo Target
    └── Task: Wait (idle)
```

---

## QUICK REFERENCE — AI SETUP CHECKLIST

```
[ ] NavMeshBoundsVolume in level, paths built
[ ] AIController class assigned to Pawn
[ ] Auto Possess AI = PlacedInWorldOrSpawned
[ ] RunBehaviorTree called in AIController OnPossess
[ ] Blackboard asset assigned to Behavior Tree
[ ] Player has UAIPerceptionStimuliSourceComponent
[ ] Custom Tasks always call FinishExecute or return result
[ ] Blackboard key names match exactly (case-sensitive)
[ ] AIModule, NavigationSystem in Build.cs
```
