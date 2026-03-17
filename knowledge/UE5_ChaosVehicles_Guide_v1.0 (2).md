# UE5 Chaos Vehicles — Knowledge Guide v1.0

## 1. SETUP — REQUIRED STEPS

### 1.1 Build.cs Dependencies
```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "ChaosVehicles",
    "PhysicsCore",
    "Chaos",
    "ChaosSolverEngine"
});
```

### 1.2 Plugin Activation
Edit → Plugins → Enable "Chaos Vehicles" → Restart the editor.

### 1.3 Basic C++ Class Hierarchy
```
AWheeledVehiclePawn
  └── UChaosWheeledVehicleMovementComponent
        └── UChaosVehicleWheel (one per wheel)
```

### 1.4 Minimum .h Structure
```cpp
#include "ChaosWheeledVehicleMovementComponent.h"

UCLASS()
class AMyVehicle : public AWheeledVehiclePawn
{
    GENERATED_BODY()
public:
    AMyVehicle();

    UPROPERTY(VisibleAnywhere)
    UChaosWheeledVehicleMovementComponent* VehicleMovement;
};
```

### 1.5 Minimum .cpp Structure
```cpp
AMyVehicle::AMyVehicle()
{
    VehicleMovement = CreateDefaultSubobject<UChaosWheeledVehicleMovementComponent>(TEXT("VehicleMovement"));
    VehicleMovement->SetIsReplicated(true);

    // Define wheel slots — will be assigned in Blueprint
    VehicleMovement->WheelSetups.SetNum(4);
}
```

---

## 2. COMMON ERRORS AND FIXES

### ERROR-CV01: Vehicle only goes backward / only turns one direction
**Cause:** Wheel rotation direction or axle setup is inverted.
**Fix:**
- In each `UChaosVehicleWheel` subclass, check `bAffectedByHandbrake`, `AxleType` (Front/Rear), and `MaxSteerAngle`.
- Front wheels: `AxleType = EVehicleAxle::Front`, `MaxSteerAngle = 40.f`
- Rear wheels: `AxleType = EVehicleAxle::Rear`, `MaxSteerAngle = 0.f`
- Call "Wake All Rigid Bodies" on throttle input (Blueprint) or in C++:
```cpp
GetMesh()->WakeAllRigidBodies();
```

### ERROR-CV02: Vehicle bouncing off the ground / flying up
**Cause:** Suspension values are at default zero.
**Fix:** In the wheel class:
```cpp
SuspensionMaxRaise = 8.f;
SuspensionMaxDrop = 12.f;
SuspensionDampingRatio = 0.5f;
SuspensionWheelRate = 250.f;
```

### ERROR-CV03: Vehicle not on ground at spawn, sliding
**Cause:** Collision setup is missing or CenterOfMass is wrong.
**Fix:**
- Set up collision for all bones in the SkeletalMesh Physics Asset.
- CenterOfMass override:
```cpp
// In .h
UPROPERTY(EditAnywhere, Category=VehicleSetup,
    meta=(EditCondition="bEnableCenterOfMassOverride"))
FVector CenterOfMassOverride;

UPROPERTY(EditAnywhere, Category=VehicleSetup)
bool bEnableCenterOfMassOverride = true;
```
- Lowering the CoM slightly (Z: -20 to -40) generally improves stability.

### ERROR-CV04: "No wheels were found" / vehicle doesn't move at all
**Cause:** WheelSetups array is empty, or no wheel class assigned in Blueprint.
**Fix:**
- After `WheelSetups.SetNum(4)` in C++, verify each slot has a wheel class assigned in Blueprint.
- Alternative: assign directly in C++:
```cpp
VehicleMovement->WheelSetups[0].WheelClass = UMyFrontWheel::StaticClass();
VehicleMovement->WheelSetups[0].BoneName = FName("Wheel_Front_Left");
// ... others
```

### ERROR-CV05: Vehicle stuck at spawn on dedicated server (phantom collision)
**Cause:** Physics object on server not syncing with client.
**Fix:**
- `SetIsReplicated(true)` must be set on the Movement Component.
- `bReplicateMovement = true` on the Pawn.
- Ensure `USkeletalMeshComponent::SetSimulatePhysics(true)` is called on server.
- Only start simulation on Authority:
```cpp
if (HasAuthority())
{
    GetMesh()->SetSimulatePhysics(true);
}
```

### ERROR-CV06: Multiplayer desync — vehicle positions don't match
**Cause:** Physics Prediction / Resimulation in Chaos Modular Vehicles not fully stable (known UE bug).
**Workaround:**
- Test with `ProjectSettings → Physics → EnablePhysicsPrediction: false`.
- Set `TickPhysicsAsync: false` — performance drops but sync is more stable.
- Increase network update rate: `NetUpdateFrequency = 60.f;`

### ERROR-CV07: FArchive / Serialize crash in Chaos context
**Cause:** Chaos physics thread conflicting with game thread.
**Fix:** Always read physics state on the game thread:
```cpp
// WRONG — reading directly from physics thread
float Speed = VehicleMovement->GetForwardSpeed();

// CORRECT — inside Tick or AsyncPhysicsTask
void AMyVehicle::Tick(float DeltaTime)
{
    Super::Tick(DeltaTime);
    // Safe here
    float Speed = VehicleMovement->GetForwardSpeed();
}
```

---

## 3. WHEEL SETTINGS — REFERENCE

```cpp
// UChaosVehicleWheel subclass example
UMyFrontWheel::UMyFrontWheel()
{
    AxleType = EVehicleAxle::Front;
    WheelRadius = 36.f;
    WheelWidth = 20.f;
    MaxSteerAngle = 40.f;
    MaxHandBrakeTorque = 0.f;      // Front wheel doesn't hold handbrake
    bAffectedByHandbrake = false;
    bAffectedByEngine = false;     // Set to true for FWD

    FrictionForceMultiplier = 2.0f;
    SideSlipModifier = 1.0f;

    SuspensionMaxRaise = 8.f;
    SuspensionMaxDrop = 12.f;
    SuspensionDampingRatio = 0.5f;
    SuspensionWheelRate = 250.f;
    SuspensionPreloadLength = 0.f;
}

UMyRearWheel::UMyRearWheel()
{
    AxleType = EVehicleAxle::Rear;
    WheelRadius = 36.f;
    WheelWidth = 20.f;
    MaxSteerAngle = 0.f;
    MaxHandBrakeTorque = 4000.f;
    bAffectedByHandbrake = true;
    bAffectedByEngine = true;

    FrictionForceMultiplier = 2.0f;
}
```

---

## 4. INPUT BINDING — C++

```cpp
void AMyVehicle::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    PlayerInputComponent->BindAxis("Throttle", this, &AMyVehicle::ApplyThrottle);
    PlayerInputComponent->BindAxis("Steering", this, &AMyVehicle::ApplySteering);
    PlayerInputComponent->BindAction("Handbrake", IE_Pressed, this, &AMyVehicle::OnHandbrakePressed);
    PlayerInputComponent->BindAction("Handbrake", IE_Released, this, &AMyVehicle::OnHandbrakeReleased);
}

void AMyVehicle::ApplyThrottle(float Val)
{
    VehicleMovement->SetThrottleInput(Val);
}

void AMyVehicle::ApplySteering(float Val)
{
    VehicleMovement->SetSteeringInput(Val);
}

void AMyVehicle::OnHandbrakePressed()
{
    VehicleMovement->SetHandbrakeInput(true);
}

void AMyVehicle::OnHandbrakeReleased()
{
    VehicleMovement->SetHandbrakeInput(false);
}
```

---

## 5. DEBUG TOOLS

```
p.Vehicle.ShowDebug 1          -- General vehicle debug overlay
p.Vehicle.ShowDebugWheels 1    -- Wheel raycasts and suspension
p.Vehicle.ShowDebugSteering 1  -- Steering angles
p.Chaos.DebugMode 1            -- Chaos solver general debug
```

Debug from C++:
```cpp
// Speed and slip info per wheel
for (int32 i = 0; i < VehicleMovement->Wheels.Num(); i++)
{
    UChaosVehicleWheel* Wheel = VehicleMovement->Wheels[i];
    UE_LOG(LogTemp, Warning, TEXT("Wheel[%d] SuspensionOffset: %f"), i, Wheel->GetSuspensionOffset());
}
```

---

## 6. MODULAR VEHICLES (UE 5.3+)

Since UE 5.3, the **Chaos Modular Vehicles** plugin is available alongside `UChaosVehicleMovementComponent`. More flexible but less stable (especially for multiplayer).

- To enable: Plugins → "Chaos Modular Vehicles" + "Chaos Modular Vehicle Examples"
- Extend the `AModularVehicleBase` class
- Each module (engine, brakes, wheels) is added as a separate component
- **Warning:** Network replication is a known issue in 5.3/5.4 — desync is common

---

## 7. MODIFYING COMPONENT AT RUNTIME

```cpp
// Change engine torque at runtime
UChaosWheeledVehicleMovementComponent* MoveComp =
    Cast<UChaosWheeledVehicleMovementComponent>(GetMovementComponent());

if (MoveComp)
{
    // Direct access to EngineSetup (write a subclass if EditAnywhere isn't exposed)
    MoveComp->EngineSetup.MaxTorque = 500.f;
    MoveComp->RecreatePhysicsState(); // Apply the change
}
```

---

## 8. AGENT RULES

- Vehicle only goes backward → check `AxleType` + `MaxSteerAngle` first (ERROR-CV01)
- Bouncing at spawn → ask about suspension values (ERROR-CV02)
- Multiplayer issue → ask about Physics Prediction flag (ERROR-CV06)
- "No wheels found" → check WheelSetups and BoneName match (ERROR-CV04)
- Dedicated server phantom collision → HasAuthority() + SetIsReplicated check (ERROR-CV05)
