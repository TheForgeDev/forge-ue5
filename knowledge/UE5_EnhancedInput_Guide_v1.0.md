# UE5 Enhanced Input System — Knowledge Guide v1.0

---

## 1. OVERVIEW

Enhanced Input replaces the legacy Input System starting UE5.1. It introduces:
- **InputAction** — what the input does (Jump, Fire, Move)
- **InputMappingContext** — which keys map to which actions
- **Modifiers & Triggers** — how input is processed before reaching the action

Legacy input (`BindAxis`, `BindAction` on UInputComponent) still compiles but is deprecated. Migrate to Enhanced Input for all new projects.

---

## 2. PROJECT SETUP

### 2.1 Enable the Plugin
Edit → Plugins → "Enhanced Input" → Enable → Restart editor.

### 2.2 Set Default Input Component Class
```
Project Settings → Engine → Input
→ Default Player Input Class: EnhancedPlayerInput
→ Default Input Component Class: EnhancedInputComponent
```

If this is not set, `Cast<UEnhancedInputComponent>` will return null even with the plugin enabled.

### 2.3 Build.cs
```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "EnhancedInput"
});
```

---

## 3. CORE ASSETS

### 3.1 InputAction Asset
Create in Content Browser: **Input → Input Action**

Key properties:
```
Value Type: Digital (bool), Axis1D (float), Axis2D (FVector2D), Axis3D (FVector)
Trigger Behavior: Triggered, Started, Ongoing, Canceled, Completed
```

### 3.2 InputMappingContext Asset
Create in Content Browser: **Input → Input Mapping Context**

Maps keys to InputActions:
```
W Key → IA_Move (modifier: Swizzle Y→X, Negate)
S Key → IA_Move (modifier: Swizzle Y→X, Negate, Negate Y)
Gamepad Left Stick → IA_Move (no modifier)
```

---

## 4. C++ SETUP — CHARACTER

### 4.1 Header
```cpp
#include "InputActionValue.h"

UCLASS()
class AMyCharacter : public ACharacter
{
    GENERATED_BODY()

public:
    UPROPERTY(EditDefaultsOnly, Category="Input")
    TObjectPtr<UInputMappingContext> DefaultMappingContext;

    UPROPERTY(EditDefaultsOnly, Category="Input")
    TObjectPtr<UInputAction> MoveAction;

    UPROPERTY(EditDefaultsOnly, Category="Input")
    TObjectPtr<UInputAction> LookAction;

    UPROPERTY(EditDefaultsOnly, Category="Input")
    TObjectPtr<UInputAction> JumpAction;

protected:
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;
    virtual void BeginPlay() override;

private:
    void Move(const FInputActionValue& Value);
    void Look(const FInputActionValue& Value);
};
```

### 4.2 BeginPlay — Add Mapping Context
```cpp
void AMyCharacter::BeginPlay()
{
    Super::BeginPlay();

    if (APlayerController* PC = Cast<APlayerController>(GetController()))
    {
        if (UEnhancedInputLocalPlayerSubsystem* Subsystem =
            ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(
                PC->GetLocalPlayer()))
        {
            Subsystem->AddMappingContext(DefaultMappingContext, 0);
            // Priority 0 = lowest. Higher number = higher priority.
        }
    }
}
```

### 4.3 SetupPlayerInputComponent
```cpp
void AMyCharacter::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);

    UEnhancedInputComponent* EIC = Cast<UEnhancedInputComponent>(PlayerInputComponent);
    if (!EIC) return; // Check Project Settings if this is null

    EIC->BindAction(MoveAction, ETriggerEvent::Triggered, this, &AMyCharacter::Move);
    EIC->BindAction(LookAction, ETriggerEvent::Triggered, this, &AMyCharacter::Look);
    EIC->BindAction(JumpAction, ETriggerEvent::Started,   this, &AMyCharacter::Jump);
    EIC->BindAction(JumpAction, ETriggerEvent::Completed, this, &AMyCharacter::StopJumping);
}
```

### 4.4 Action Callbacks
```cpp
void AMyCharacter::Move(const FInputActionValue& Value)
{
    FVector2D MovementVector = Value.Get<FVector2D>();

    if (Controller)
    {
        const FRotator Rotation = Controller->GetControlRotation();
        const FRotator YawRotation(0, Rotation.Yaw, 0);

        const FVector ForwardDirection = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::X);
        const FVector RightDirection   = FRotationMatrix(YawRotation).GetUnitAxis(EAxis::Y);

        AddMovementInput(ForwardDirection, MovementVector.Y);
        AddMovementInput(RightDirection,   MovementVector.X);
    }
}

void AMyCharacter::Look(const FInputActionValue& Value)
{
    FVector2D LookAxisVector = Value.Get<FVector2D>();

    AddControllerYawInput(LookAxisVector.X);
    AddControllerPitchInput(LookAxisVector.Y);
}
```

---

## 5. TRIGGER EVENTS — WHICH ONE TO USE?

| ETriggerEvent | When fires | Use case |
|---|---|---|
| `Started` | First frame key is pressed | Jump start, ability activate |
| `Triggered` | Every frame while active (after threshold) | Movement, look |
| `Ongoing` | Every frame while held, before threshold | Hold-to-charge |
| `Completed` | Frame the key is released | Jump release, cancel |
| `Canceled` | Trigger condition not met (e.g. tap too short) | Abort hold action |

---

## 6. MODIFIERS — MOST USEFUL

| Modifier | What it does | Common use |
|---|---|---|
| `Negate` | Flips sign (-1x) | S key moves backward |
| `Swizzle Input Axis Values` | Reorders XYZ | Map W/S to Y axis |
| `Scale` | Multiplies by value | Sensitivity scaling |
| `Dead Zone` | Ignores small values | Gamepad stick drift |
| `Smooth` | Lerps input over time | Mouse smoothing |

**WASD Move example (Axis2D action):**
```
W → IA_Move: no modifier needed if Y = forward
S → IA_Move: Negate modifier (Y becomes -1)
A → IA_Move: Swizzle (X→Y) + Negate
D → IA_Move: Swizzle (X→Y)
```

---

## 7. SWITCHING MAPPING CONTEXTS AT RUNTIME

```cpp
// Remove default context, add vehicle context
void AMyCharacter::EnterVehicle()
{
    APlayerController* PC = Cast<APlayerController>(GetController());
    if (!PC) return;

    UEnhancedInputLocalPlayerSubsystem* Subsystem =
        ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(
            PC->GetLocalPlayer());
    if (!Subsystem) return;

    Subsystem->RemoveMappingContext(DefaultMappingContext);
    Subsystem->AddMappingContext(VehicleMappingContext, 1);
}

void AMyCharacter::ExitVehicle()
{
    // ... reverse
    Subsystem->RemoveMappingContext(VehicleMappingContext);
    Subsystem->AddMappingContext(DefaultMappingContext, 0);
}
```

**Priority matters:** Higher priority context can block lower priority actions. Two contexts at priority 0 both fire. At priority 1 vs 0, priority 1 wins on conflicts.

---

## 8. COMMON ERRORS AND FIXES

### ERROR-EI01: `Cast<UEnhancedInputComponent>` returns null
**Cause:** Default Input Component Class not set in Project Settings.
**Fix:** `Project Settings → Input → Default Input Component Class → EnhancedInputComponent`

### ERROR-EI02: Input works in editor but not in packaged build
**Cause:** InputAction or InputMappingContext asset not in a folder that's cooked.
**Fix:** Make sure assets are in `/Content/` and not excluded by cook settings. Check `Project Settings → Packaging → Directories to always cook`.

### ERROR-EI03: `AddMappingContext` has no effect
**Cause:** Called before PlayerController is valid (too early in BeginPlay), or called on wrong controller.
**Fix:** Call in `BeginPlay` with `APlayerController*` cast, not from Pawn constructor.
```cpp
// Safe timing check:
if (APlayerController* PC = Cast<APlayerController>(GetController()))
{
    // GetController() is valid here on server and owning client
}
```

### ERROR-EI04: Action fires every frame but should fire once
**Cause:** Using `ETriggerEvent::Triggered` for a one-shot action.
**Fix:** Use `ETriggerEvent::Started` for one-shot actions (jump, interact, fire single shot).

### ERROR-EI05: Gamepad and keyboard both mapped but one doesn't work
**Cause:** Priority conflict — one mapping context is blocking the other.
**Fix:** Use the same `IMC` for both gamepad and keyboard mappings. Multiple `IMC`s for the same action at the same priority both fire.

### ERROR-EI06: Legacy `BindAxis` / `BindAction` calls no longer work
**Cause:** Project was upgraded to UE5.1+ but old binding code remains.
**Fix:** Replace with Enhanced Input. The `UInputComponent` base class still compiles but legacy bindings are ignored when `EnhancedInputComponent` is the default class.

---

## 9. MIGRATION FROM LEGACY INPUT

### Legacy → Enhanced Quick Map

| Legacy | Enhanced Input equivalent |
|---|---|
| `BindAxis("MoveForward", ...)` | `BindAction(MoveAction, ETriggerEvent::Triggered, ...)` + IA_Move Axis2D |
| `BindAction("Jump", IE_Pressed, ...)` | `BindAction(JumpAction, ETriggerEvent::Started, ...)` |
| `BindAction("Jump", IE_Released, ...)` | `BindAction(JumpAction, ETriggerEvent::Completed, ...)` |
| `GetInputAxisValue("MoveForward")` | Read from `FInputActionValue::Get<float>()` in callback |

### Migration steps:
1. Enable Enhanced Input plugin
2. Set default classes in Project Settings
3. Create InputAction assets for each action
4. Create InputMappingContext, assign keys
5. Replace `SetupPlayerInputComponent` with Enhanced Input binding
6. Replace `BindAxis/BindAction` with `EIC->BindAction`
7. Assign IMC assets in BP subclass defaults

---

## 10. MULTIPLAYER NOTES

Enhanced Input runs **only on the owning client** — no replication. Server never receives input directly.

Pattern:
```
Client input → Enhanced Input fires → Character/Controller function →
Server RPC → Server applies movement/action
```

`AddMappingContext` should only be called where `IsLocallyControlled()` is true or in a `PlayerController` on the client. Don't call it on simulated proxies.

---

## 11. AGENT RULES

- `Cast<UEnhancedInputComponent>` null → Project Settings not configured (ERROR-EI01)
- Input works in editor, fails packaged → asset cook path issue (ERROR-EI02)
- `AddMappingContext` no effect → timing or wrong controller (ERROR-EI03)
- Action fires every frame → use `Started` not `Triggered` (ERROR-EI04)
- Legacy `BindAxis` migration needed → Section 9 migration steps
- Multiple contexts conflicting → check priority values
- Multiplayer input issues → Enhanced Input is client-only, needs Server RPC
