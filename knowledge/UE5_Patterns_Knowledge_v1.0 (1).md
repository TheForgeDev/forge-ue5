# UE5 Code Patterns Library
### UE5 Dev Agent — Knowledge v1.0

---

## PATTERN 1: Safe Actor Reference

**Problem:** Storing reference to another Actor — crashes when that Actor is destroyed.

```cpp
// WRONG
AActor* MyTarget;

void AMyActor::Tick(float DeltaTime)
{
    MyTarget->DoSomething(); // crash if MyTarget was destroyed
}

// RIGHT
UPROPERTY()
TObjectPtr<AActor> MyTarget; // UPROPERTY protects from GC, sets to null on destroy

void AMyActor::Tick(float DeltaTime)
{
    if (IsValid(MyTarget))
    {
        MyTarget->DoSomething();
    }
}
```

---

## PATTERN 2: Component Communication

**Problem:** Actor A needs to talk to a component on Actor B.

```cpp
// Find specific component on another actor
UMyComponent* Comp = OtherActor->FindComponentByClass<UMyComponent>();
if (IsValid(Comp))
{
    Comp->DoSomething();
}

// Better — use interface instead of direct coupling:
if (OtherActor->Implements<UMyInterface>())
{
    IMyInterface::Execute_DoSomething(OtherActor);
}
```

---

## PATTERN 3: Async Asset Loading

**Problem:** Loading large assets synchronously freezes the game.

```cpp
// WRONG — synchronous load, hitches game thread
UTexture2D* Tex = LoadObject<UTexture2D>(nullptr, TEXT("/Game/Textures/MyTex"));

// RIGHT — async load
#include "Engine/StreamableManager.h"
#include "Engine/AssetManager.h"

void AMyActor::LoadAssetAsync()
{
    FSoftObjectPath AssetPath(TEXT("/Game/Textures/MyTex.MyTex"));
    
    TSharedPtr<FStreamableHandle> Handle = UAssetManager::GetStreamableManager()
        .RequestAsyncLoad(AssetPath,
            FStreamableDelegate::CreateUObject(this, &AMyActor::OnAssetLoaded));
}

void AMyActor::OnAssetLoaded()
{
    // Asset is ready, safe to use
    UTexture2D* Tex = Cast<UTexture2D>(
        FSoftObjectPath(TEXT("/Game/Textures/MyTex.MyTex")).ResolveObject());
}
```

---

## PATTERN 4: Timer Usage

```cpp
// One-shot timer
FTimerHandle TimerHandle;
GetWorldTimerManager().SetTimer(
    TimerHandle,
    this,
    &AMyActor::OnTimerFired,
    2.0f,   // delay in seconds
    false   // not looping
);

// Looping timer
GetWorldTimerManager().SetTimer(
    TimerHandle,
    this,
    &AMyActor::OnTimerFired,
    1.0f,
    true    // looping
);

// Lambda timer
GetWorldTimerManager().SetTimerForNextTick([this]()
{
    // runs next frame
});

// Cancel timer
GetWorldTimerManager().ClearTimer(TimerHandle);

// Check if running
bool bIsRunning = GetWorldTimerManager().IsTimerActive(TimerHandle);
```

---

## PATTERN 5: Delegate Usage

```cpp
// Declare delegate
DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnHealthChanged, float, NewHealth);

// In class .h
UPROPERTY(BlueprintAssignable)
FOnHealthChanged OnHealthChanged;

// Broadcast
OnHealthChanged.Broadcast(CurrentHealth);

// Bind in C++
MyActor->OnHealthChanged.AddDynamic(this, &AMyOtherActor::HandleHealthChanged);

// Unbind — important to prevent crashes
MyActor->OnHealthChanged.RemoveDynamic(this, &AMyOtherActor::HandleHealthChanged);
```

---

## PATTERN 6: Gameplay Tags

```cpp
// Add to Build.cs:
PublicDependencyModuleNames.Add("GameplayTags");

// .h
#include "GameplayTagContainer.h"

UPROPERTY(EditAnywhere)
FGameplayTag AbilityTag;

UPROPERTY(EditAnywhere)
FGameplayTagContainer BlockedTags;

// Check tags
if (TagContainer.HasTag(FGameplayTag::RequestGameplayTag("Status.Burning")))
{
    // actor is burning
}

// Add/Remove tags
TagContainer.AddTag(FGameplayTag::RequestGameplayTag("Status.Burning"));
TagContainer.RemoveTag(FGameplayTag::RequestGameplayTag("Status.Burning"));
```

---

## PATTERN 7: Object Pooling

**Problem:** Spawning/destroying actors frequently is expensive (projectiles, effects).

```cpp
// Simple object pool
UCLASS()
class AProjectilePool : public AActor
{
    GENERATED_BODY()

    TArray<AProjectile*> AvailableProjectiles;

public:
    AProjectile* GetProjectile()
    {
        if (AvailableProjectiles.Num() > 0)
        {
            AProjectile* Proj = AvailableProjectiles.Pop();
            Proj->SetActorHiddenInGame(false);
            Proj->SetActorEnableCollision(true);
            return Proj;
        }
        // Pool empty — spawn new one
        return GetWorld()->SpawnActor<AProjectile>();
    }

    void ReturnProjectile(AProjectile* Proj)
    {
        Proj->SetActorHiddenInGame(true);
        Proj->SetActorEnableCollision(false);
        Proj->SetActorVelocity(FVector::ZeroVector);
        AvailableProjectiles.Add(Proj);
    }
};
```

---

## PATTERN 8: Interface Implementation

**Problem:** Coupling between actor types — A needs to call specific function on B but doesn't know B's type.

```cpp
// Declare interface — MyInterface.h
UINTERFACE(MinimalAPI, Blueprintable)
class UMyInterface : public UInterface
{
    GENERATED_BODY()
};

class IMyInterface
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintNativeEvent)
    void OnInteract(AActor* Interactor);
};

// Implement in Actor — MyActor.h
class AMyActor : public AActor, public IMyInterface
{
    virtual void OnInteract_Implementation(AActor* Interactor) override;
};

// Call without knowing the type
void APlayerCharacter::Interact(AActor* Target)
{
    if (IsValid(Target) && Target->Implements<UMyInterface>())
    {
        IMyInterface::Execute_OnInteract(Target, this);
    }
}
```

---

## PATTERN 9: Save Game

```cpp
// Create save game class
UCLASS()
class UMySaveGame : public USaveGame
{
    GENERATED_BODY()
public:
    UPROPERTY()
    float PlayerHealth;
    
    UPROPERTY()
    FVector PlayerLocation;
    
    UPROPERTY()
    TArray<FString> CollectedItems;
};

// Save
void SaveGame()
{
    UMySaveGame* SaveData = Cast<UMySaveGame>(
        UGameplayStatics::CreateSaveGameObject(UMySaveGame::StaticClass()));
    
    SaveData->PlayerHealth = GetHealth();
    SaveData->PlayerLocation = GetActorLocation();
    
    UGameplayStatics::SaveGameToSlot(SaveData, TEXT("Slot1"), 0);
}

// Load
void LoadGame()
{
    if (UGameplayStatics::DoesSaveGameExist(TEXT("Slot1"), 0))
    {
        UMySaveGame* SaveData = Cast<UMySaveGame>(
            UGameplayStatics::LoadGameFromSlot(TEXT("Slot1"), 0));
        
        if (IsValid(SaveData))
        {
            SetHealth(SaveData->PlayerHealth);
            SetActorLocation(SaveData->PlayerLocation);
        }
    }
}
```

---

## PATTERN 10: Debug Helpers

```cpp
// Visual debug — draw sphere at location
DrawDebugSphere(
    GetWorld(),
    GetActorLocation(),
    50.f,           // radius
    12,             // segments
    FColor::Red,
    false,          // persistent (false = one frame)
    2.0f            // duration in seconds
);

// Draw line
DrawDebugLine(GetWorld(), Start, End, FColor::Green, false, 2.0f);

// Draw string in world
DrawDebugString(GetWorld(), GetActorLocation(), TEXT("Debug Text"), nullptr, FColor::White, 2.0f);

// Log with category
UE_LOG(LogTemp, Warning, TEXT("Value: %f"), MyFloat);
UE_LOG(LogTemp, Error, TEXT("Actor: %s"), *GetName());

// Screen message
GEngine->AddOnScreenDebugMessage(-1, 5.f, FColor::Yellow,
    FString::Printf(TEXT("Health: %f"), Health));

// Ensure with message
ensureMsgf(IsValid(MyComponent), TEXT("MyComponent is null in %s"), *GetName());
```

---

## PATTERN 11: Subsystem Usage

**UE5 subsystems replace singletons — cleaner, lifecycle managed by engine.**

```cpp
// Game Instance Subsystem — lives for entire game session
UCLASS()
class UMyGameSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()
public:
    virtual void Initialize(FSubsystemCollectionBase& Collection) override;
    virtual void Deinitialize() override;
    
    void DoSomething();
};

// Access anywhere:
UGameInstance* GI = GetGameInstance();
UMyGameSubsystem* Subsystem = GI->GetSubsystem<UMyGameSubsystem>();
if (IsValid(Subsystem))
{
    Subsystem->DoSomething();
}

// Other subsystem types:
// UWorldSubsystem — per world/level
// ULocalPlayerSubsystem — per local player
// UEngineSubsystem — entire engine lifetime
```

---

## PATTERN 12: Data Tables

```cpp
// Define row struct
USTRUCT(BlueprintType)
struct FWeaponData : public FTableRowBase
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere)
    float Damage;

    UPROPERTY(EditAnywhere)
    float FireRate;

    UPROPERTY(EditAnywhere)
    TSoftObjectPtr<UStaticMesh> Mesh;
};

// Reference DataTable asset
UPROPERTY(EditAnywhere)
UDataTable* WeaponDataTable;

// Look up row
FWeaponData* WeaponData = WeaponDataTable->FindRow<FWeaponData>(
    FName("Rifle"), TEXT("WeaponLookup"));

if (WeaponData)
{
    ApplyDamage(WeaponData->Damage);
}
```

---

## PATTERN 13: Collision Queries

```cpp
// Line trace
FHitResult HitResult;
FVector Start = GetActorLocation();
FVector End = Start + GetActorForwardVector() * 1000.f;

FCollisionQueryParams Params;
Params.AddIgnoredActor(this); // ignore self

bool bHit = GetWorld()->LineTraceSingleByChannel(
    HitResult,
    Start,
    End,
    ECC_Visibility,
    Params
);

if (bHit)
{
    AActor* HitActor = HitResult.GetActor();
    FVector HitLocation = HitResult.Location;
    FVector HitNormal = HitResult.Normal;
}

// Sphere sweep
TArray<FHitResult> HitResults;
GetWorld()->SweepMultiByChannel(
    HitResults,
    Start,
    End,
    FQuat::Identity,
    ECC_Pawn,
    FCollisionShape::MakeSphere(50.f),
    Params
);
```
