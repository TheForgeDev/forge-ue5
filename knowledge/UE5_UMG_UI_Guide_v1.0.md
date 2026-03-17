# UE5 UMG / UI C++ Integration — Knowledge Guide v1.0

---

## 1. OVERVIEW

UMG (Unreal Motion Graphics) is UE5's UI framework. The typical workflow:
- Design widget layout in Blueprint (WBP_*)
- Bind data and logic in C++ via `UUserWidget` subclass
- Create and manage widgets from C++ or PlayerController

---

## 2. BASIC SETUP

### 2.1 Build.cs
```csharp
PublicDependencyModuleNames.AddRange(new string[] {
    "UMG",
    "Slate",
    "SlateCore"
});
```

### 2.2 C++ Widget Base Class
```cpp
// MyHUDWidget.h
#include "Blueprint/UserWidget.h"

UCLASS()
class UMyHUDWidget : public UUserWidget
{
    GENERATED_BODY()

public:
    // Called after the widget is constructed
    virtual void NativeConstruct() override;
    virtual void NativeTick(const FGeometry& MyGeometry, float InDeltaTime) override;

    // Data update function — called from C++ or BP
    UFUNCTION(BlueprintCallable)
    void UpdateHealth(float NewHealth, float MaxHealth);

protected:
    // BindWidget — links to the named widget in the Blueprint
    UPROPERTY(meta=(BindWidget))
    TObjectPtr<UProgressBar> HealthBar;

    UPROPERTY(meta=(BindWidget))
    TObjectPtr<UTextBlock> HealthText;

    // Optional BindWidget — won't error if not found in BP
    UPROPERTY(meta=(BindWidgetOptional))
    TObjectPtr<UTextBlock> DebugText;

    // BindWidgetAnim — links to an animation defined in the BP
    UPROPERTY(meta=(BindWidgetAnim), Transient)
    TObjectPtr<UWidgetAnimation> HitFlashAnim;
};
```

### 2.3 Implementation
```cpp
void UMyHUDWidget::NativeConstruct()
{
    Super::NativeConstruct();
    // Widget is ready — safe to access BindWidget members here
}

void UMyHUDWidget::UpdateHealth(float NewHealth, float MaxHealth)
{
    if (HealthBar)
    {
        HealthBar->SetPercent(MaxHealth > 0.f ? NewHealth / MaxHealth : 0.f);
    }

    if (HealthText)
    {
        HealthText->SetText(FText::FromString(
            FString::Printf(TEXT("%.0f / %.0f"), NewHealth, MaxHealth)));
    }
}
```

---

## 3. CREATING AND DISPLAYING WIDGETS

### 3.1 From PlayerController (recommended)
```cpp
// PlayerController.h
UPROPERTY(EditDefaultsOnly, Category="UI")
TSubclassOf<UMyHUDWidget> HUDWidgetClass;

UPROPERTY()
TObjectPtr<UMyHUDWidget> HUDWidget;

// PlayerController.cpp
void AMyPlayerController::BeginPlay()
{
    Super::BeginPlay();

    // Only create UI on local client
    if (IsLocalPlayerController())
    {
        HUDWidget = CreateWidget<UMyHUDWidget>(this, HUDWidgetClass);
        if (HUDWidget)
        {
            HUDWidget->AddToViewport();
            // ZOrder: higher = renders on top. Default = 0.
            // HUDWidget->AddToViewport(1);
        }
    }
}
```

### 3.2 Remove and Clean Up
```cpp
void AMyPlayerController::OnGameOver()
{
    if (HUDWidget)
    {
        HUDWidget->RemoveFromParent(); // Removes from viewport
        HUDWidget = nullptr;
    }
}
```

### 3.3 Widget Z-Order and Layering
```cpp
// AddToViewport(int32 ZOrder)
HUDWidget->AddToViewport(0);        // Background
PopupWidget->AddToViewport(10);     // On top of HUD
PauseMenuWidget->AddToViewport(20); // On top of everything
```

---

## 4. BINDWIDGET — RULES AND COMMON MISTAKES

`BindWidget` links a C++ variable to a widget by **exact name match** in the Blueprint.

```cpp
// C++ declares:
UPROPERTY(meta=(BindWidget))
TObjectPtr<UProgressBar> HealthBar;

// Blueprint must have a widget named exactly "HealthBar"
// Name is case-sensitive
```

**Rules:**
- The C++ variable name MUST match the Blueprint widget name exactly
- `BindWidget` without `Optional` — missing widget = compile error in editor
- `BindWidgetOptional` — won't error, but check for null before use
- Works only with `UUserWidget` subclasses, not other UObject types
- `BindWidgetAnim` requires `Transient` specifier

**Common mistake:**
```cpp
// C++ name:        HealthBar
// Blueprint name:  Health_Bar   ← WRONG — won't bind, will error
// Blueprint name:  Healthbar    ← WRONG — case sensitive
// Blueprint name:  HealthBar    ← CORRECT
```

---

## 5. COMMON WIDGET TYPES — C++ API

### UTextBlock
```cpp
#include "Components/TextBlock.h"

TextBlock->SetText(FText::FromString("Hello"));
TextBlock->SetText(FText::AsNumber(42));
TextBlock->SetColorAndOpacity(FSlateColor(FLinearColor::Red));
TextBlock->SetVisibility(ESlateVisibility::Hidden);
```

### UProgressBar
```cpp
#include "Components/ProgressBar.h"

ProgressBar->SetPercent(0.75f); // 0.0 to 1.0
ProgressBar->SetFillColorAndOpacity(FLinearColor(1.f, 0.2f, 0.2f, 1.f));
```

### UImage
```cpp
#include "Components/Image.h"

Image->SetBrushFromTexture(MyTexture);
Image->SetColorAndOpacity(FLinearColor(1.f, 1.f, 1.f, 0.5f));
```

### UButton
```cpp
#include "Components/Button.h"

// Bind click event
Button->OnClicked.AddDynamic(this, &UMyWidget::OnButtonClicked);

// Remove binding on cleanup
Button->OnClicked.RemoveDynamic(this, &UMyWidget::OnButtonClicked);

// Enable/disable
Button->SetIsEnabled(false);
```

### USizeBox / UOverlay / UVerticalBox
```cpp
#include "Components/SizeBox.h"

SizeBox->SetWidthOverride(200.f);
SizeBox->SetHeightOverride(50.f);
SizeBox->ClearWidthOverride();
```

---

## 6. WIDGET ANIMATIONS

```cpp
// In header:
UPROPERTY(meta=(BindWidgetAnim), Transient)
TObjectPtr<UWidgetAnimation> FadeInAnim;

// Play animation
void UMyWidget::PlayFadeIn()
{
    if (FadeInAnim)
    {
        PlayAnimation(FadeInAnim);
        // PlayAnimation(FadeInAnim, 0.f, 1, EUMGSequencePlayMode::Forward, 1.f);
        //   StartAtTime, NumLoops, PlayMode, PlaybackSpeed
    }
}

// Stop
StopAnimation(FadeInAnim);

// Check if playing
bool bPlaying = IsAnimationPlaying(FadeInAnim);

// Bind to animation end
FWidgetAnimationDynamicEvent EndEvent;
EndEvent.BindDynamic(this, &UMyWidget::OnFadeInComplete);
BindToAnimationFinished(FadeInAnim, EndEvent);
```

---

## 7. 3D WIDGET (WIDGET COMPONENT)

For world-space UI attached to actors (health bars over enemies, interaction prompts).

```cpp
// In Actor .h:
UPROPERTY(VisibleAnywhere)
TObjectPtr<UWidgetComponent> HealthBarComponent;

// In Constructor:
HealthBarComponent = CreateDefaultSubobject<UWidgetComponent>(TEXT("HealthBar"));
HealthBarComponent->SetupAttachment(RootComponent);
HealthBarComponent->SetWidgetClass(UMyHealthBarWidget::StaticClass());
HealthBarComponent->SetWidgetSpace(EWidgetSpace::World); // or Screen
HealthBarComponent->SetDrawSize(FVector2D(200.f, 20.f));

// Access the widget instance at runtime:
UMyHealthBarWidget* Widget = Cast<UMyHealthBarWidget>(
    HealthBarComponent->GetUserWidgetObject());
if (Widget)
{
    Widget->UpdateHealth(CurrentHealth, MaxHealth);
}
```

---

## 8. INPUT MODE — GAME vs UI

```cpp
// Game only (no cursor, no widget interaction)
FInputModeGameOnly GameMode;
PlayerController->SetInputMode(GameMode);
PlayerController->SetShowMouseCursor(false);

// UI only (cursor visible, game input blocked)
FInputModeUIOnly UIMode;
UIMode.SetWidgetToFocus(MyWidget->TakeWidget());
PlayerController->SetInputMode(UIMode);
PlayerController->SetShowMouseCursor(true);

// Game and UI (cursor visible, both work — for inventory etc.)
FInputModeGameAndUI GameAndUIMode;
GameAndUIMode.SetWidgetToFocus(MyWidget->TakeWidget());
GameAndUIMode.SetLockMouseToViewportBehavior(EMouseLockMode::DoNotLock);
PlayerController->SetInputMode(GameAndUIMode);
PlayerController->SetShowMouseCursor(true);
```

**Common mistake:** Forgetting to restore `FInputModeGameOnly` when closing a menu — player can't move after.

---

## 9. COMMONUI (UE5.1+)

CommonUI is the recommended framework for production UIs (menus, pause screens). It handles input routing, focus, and platform differences automatically.

### Key classes:
- `UCommonUserWidget` — base class instead of `UUserWidget`
- `UCommonActivatableWidget` — widget that can be "activated" (shown) and "deactivated" (hidden), manages focus automatically
- `UCommonUISubsystem` — global UI state manager

### Basic activatable widget:
```cpp
UCLASS()
class UMyPauseMenu : public UCommonActivatableWidget
{
    GENERATED_BODY()

protected:
    virtual void NativeOnActivated() override;   // Widget shown
    virtual void NativeOnDeactivated() override; // Widget hidden

    // CommonUI automatically handles back button / B button
    virtual FReply NativeOnKeyDown(const FGeometry& InGeometry,
                                   const FKeyEvent& InKeyEvent) override;
};
```

---

## 10. COMMON ERRORS AND FIXES

### ERROR-UI01: BindWidget compile error — "widget not found in blueprint"
**Cause:** C++ variable name doesn't exactly match the Blueprint widget name.
**Fix:** Open the Blueprint, check exact widget name in the hierarchy panel. Rename to match C++ variable name exactly (case-sensitive).

### ERROR-UI02: Widget is null in NativeConstruct
**Cause:** Trying to access BindWidget members before `NativeConstruct`. Don't use them in the constructor.
**Fix:** Always access BindWidget members in `NativeConstruct` or later, never in `UUserWidget::UUserWidget()`.

### ERROR-UI03: Widget created but not visible
**Cause:** `AddToViewport()` not called, or widget has zero size, or visibility is set to Hidden.
**Fix:** Call `AddToViewport()`. Check widget's visibility in BP. Check size constraints.

### ERROR-UI04: Widget visible but player can't move
**Cause:** Input mode set to `UIOnly` and never restored.
**Fix:** Always restore input mode to `GameOnly` when closing the widget.

### ERROR-UI05: Crash when widget is garbage collected
**Cause:** Widget stored as raw pointer without `UPROPERTY()` — GC collects it.
**Fix:**
```cpp
// WRONG
UMyWidget* HUDWidget;

// CORRECT
UPROPERTY()
TObjectPtr<UMyWidget> HUDWidget;
```

### ERROR-UI06: BindWidgetAnim not binding
**Cause:** Missing `Transient` specifier on the animation property.
**Fix:**
```cpp
UPROPERTY(meta=(BindWidgetAnim), Transient)  // Transient is required
TObjectPtr<UWidgetAnimation> MyAnim;
```

### ERROR-UI07: Widget Component (3D widget) not showing
**Cause:** Widget class not set, or draw size is zero, or component not attached.
**Fix:** Set `WidgetClass` in constructor or Blueprint. Set `DrawSize` to non-zero. Call `SetupAttachment`.

---

## 11. AGENT RULES

- BindWidget null crash → check name match C++ ↔ BP, check NativeConstruct timing (ERROR-UI01/02)
- Widget not visible → AddToViewport called? Visibility correct? (ERROR-UI03)
- Player can't move after menu → input mode not restored to GameOnly (ERROR-UI04)
- Widget crash → missing UPROPERTY on widget pointer (ERROR-UI05)
- BindWidgetAnim not working → missing Transient specifier (ERROR-UI06)
- 3D widget not showing → check WidgetClass, DrawSize, attachment (ERROR-UI07)
- Input routing issues → CommonUI for production menus (Section 9)
- Multiplayer: create widgets only where `IsLocalPlayerController()` is true
