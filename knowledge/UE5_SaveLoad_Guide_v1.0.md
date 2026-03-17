# UE5 Save / Load System — Knowledge Guide v1.0

## 1. BASIC STRUCTURE

UE5's save system consists of three layers:

```
USaveGame (data container)
    ↕ serialize / deserialize
UGameplayStatics::SaveGameToSlot / LoadGameFromSlot
    ↕
Disk: Saved/SaveGames/<SlotName>.sav
```

Optional architecture: `UGameInstanceSubsystem` → centralized save manager (recommended pattern).

---

## 2. BASIC SETUP — STEP BY STEP

### 2.1 USaveGame Subclass
```cpp
// MySaveGame.h
UCLASS()
class UMySaveGame : public USaveGame
{
    GENERATED_BODY()
public:
    UPROPERTY(SaveGame)
    FVector PlayerLocation;

    UPROPERTY(SaveGame)
    float PlayerHealth;

    UPROPERTY(SaveGame)
    TArray<FActorSaveData> SavedActors;

    UPROPERTY(SaveGame)
    int32 SaveVersion = 1; // For version control
};
```

### 2.2 Actor Data Struct
```cpp
USTRUCT()
struct FActorSaveData
{
    GENERATED_BODY()

    UPROPERTY(SaveGame)
    FName ActorName;

    UPROPERTY(SaveGame)
    TArray<uint8> ByteData; // Serialized actor state
};
```

### 2.3 SaveGame Interface
```cpp
UINTERFACE()
class USaveGameInterface : public UInterface { GENERATED_BODY() };

class ISaveGameInterface
{
    GENERATED_BODY()
public:
    UFUNCTION(BlueprintNativeEvent)
    void OnLoadGame();
};
```

---

## 3. SAVING — SaveGame Subsystem Pattern

```cpp
// SaveGameSubsystem.cpp
void USaveGameSubsystem::SaveGame()
{
    CurrentSaveGame->SavedActors.Empty();

    TArray<AActor*> SaveActors;
    UGameplayStatics::GetAllActorsWithInterface(
        GetWorld(), USaveGameInterface::StaticClass(), SaveActors);

    for (AActor* Actor : SaveActors)
    {
        FActorSaveData ActorData;
        ActorData.ActorName = Actor->GetFName();

        FMemoryWriter MemWriter(ActorData.ByteData);
        FObjectAndNameAsStringProxyArchive Ar(MemWriter, true);
        Ar.ArIsSaveGame = true;
        Actor->Serialize(Ar);

        CurrentSaveGame->SavedActors.Add(ActorData);
    }

    UGameplayStatics::SaveGameToSlot(CurrentSaveGame, SaveSlotName, 0);
}
```

### 3.1 Async Saving (for large worlds)
```cpp
void USaveGameSubsystem::SaveGameAsync()
{
    // Prepare data first (sync)
    PrepareActorData();

    // Then write to disk async
    UGameplayStatics::AsyncSaveGameToSlot(
        CurrentSaveGame,
        SaveSlotName,
        0,
        FAsyncSaveGameToSlotDelegate::CreateUObject(
            this, &USaveGameSubsystem::OnSaveComplete)
    );
}

void USaveGameSubsystem::OnSaveComplete(const FString& SlotName, int32 UserIndex, bool bSuccess)
{
    if (!bSuccess)
    {
        UE_LOG(LogTemp, Error, TEXT("Save failed: %s"), *SlotName);
    }
}
```

---

## 4. LOADING

```cpp
void USaveGameSubsystem::LoadGame()
{
    CurrentSaveGame = Cast<UMySaveGame>(
        UGameplayStatics::LoadGameFromSlot(SaveSlotName, 0));

    if (!CurrentSaveGame)
    {
        // New game
        CurrentSaveGame = Cast<UMySaveGame>(
            UGameplayStatics::CreateSaveGameObject(UMySaveGame::StaticClass()));
        return;
    }

    // Version check
    if (CurrentSaveGame->SaveVersion < CURRENT_SAVE_VERSION)
    {
        MigrateSaveData(CurrentSaveGame);
    }

    // Restore data to actors
    TArray<AActor*> WorldActors;
    UGameplayStatics::GetAllActorsWithInterface(
        GetWorld(), USaveGameInterface::StaticClass(), WorldActors);

    for (AActor* Actor : WorldActors)
    {
        for (FActorSaveData& Data : CurrentSaveGame->SavedActors)
        {
            if (Data.ActorName == Actor->GetFName())
            {
                FMemoryReader MemReader(Data.ByteData);
                FObjectAndNameAsStringProxyArchive Ar(MemReader, true);
                Ar.ArIsSaveGame = true;
                Actor->Serialize(Ar);

                ISaveGameInterface::Execute_OnLoadGame(Actor);
                break;
            }
        }
    }
}
```

---

## 5. COMMON ERRORS AND FIXES

### ERROR-SL01: `FArchive does not support FSoftObjectPtr serialization. Use FArchiveUObject instead.`
**Cause:** Using plain `FArchive` instead of `FObjectAndNameAsStringProxyArchive`; trying to serialize `TSoftObjectPtr` or `TSoftClassPtr`.
**Fix:**
```cpp
// WRONG
FMemoryWriter MemWriter(ByteData);
FArchive Ar(MemWriter); // Not supported

// CORRECT
FMemoryWriter MemWriter(ByteData);
FObjectAndNameAsStringProxyArchive Ar(MemWriter, true);
Ar.ArIsSaveGame = true;
```
If you need to save a `TSoftObjectPtr` → store the path as `FString`, resolve with `FSoftObjectPath` on load.

### ERROR-SL02: Property not being saved — value reverts to default after load
**Cause:** Missing `UPROPERTY(SaveGame)` specifier.
**Fix:**
```cpp
// WRONG
UPROPERTY()
float MyValue;

// CORRECT
UPROPERTY(SaveGame)
float MyValue;
```
Also, if `Ar.ArIsSaveGame = true` is not set, SaveGame-specifier properties are ignored.

### ERROR-SL03: `ArNoDelta` issue — unchanged properties not being saved
**Cause:** With `ArNoDelta = false` (default), properties that haven't changed from their default value aren't serialized.
**Fix:** To always save all properties:
```cpp
FObjectAndNameAsStringProxyArchive Ar(MemWriter, true);
Ar.ArIsSaveGame = true;
Ar.ArNoDelta = true; // Save even if value is the default
```

### ERROR-SL04: DataAsset reference becomes invalid after rename/move
**Cause:** Save file stores the old path, can't be found after asset is moved.
**Fix:** Don't save DataAssets directly — use an `FName` or `FString` ID instead:
```cpp
// WRONG
UPROPERTY(SaveGame)
UItemDataAsset* ItemData; // Direct object reference

// CORRECT
UPROPERTY(SaveGame)
FName ItemID; // e.g. "Sword_01"

// On load, find the DataAsset from ID:
UItemDataAsset* Found = ItemDatabase->FindItemByID(ItemID);
```
If redirect is needed: keep an OldPath → NewPath mapping in a DataTable.

### ERROR-SL05: `cannot initialize a parameter of type 'USaveGame*' with lvalue of type 'UObject*'`
**Cause:** Type mismatch in a template function.
**Fix:** Use `Cast<USaveGame>(MyObject)`, don't pass a raw `UObject*`.

### ERROR-SL06: Runtime-spawned actors can't be found on load
**Cause:** Runtime-spawned actors have inconsistent `FName` values (auto-generated, counter-based).
**Fix:** Generate a deterministic `FGuid` at spawn time:
```cpp
UPROPERTY(SaveGame)
FGuid ActorGuid;

// At spawn:
if (ActorGuid.IsValid() == false)
    ActorGuid = FGuid::NewGuid();
```
Use Guid instead of ActorName in save data; match by Guid during `GetAllActors` on load.

### ERROR-SL07: Saving is very slow / causes hitching
**Cause:** `GetAllActorsWithInterface` scans the entire world on every save in a large world.
**Fix:**
1. Keep actors to be saved in a `TArray<TWeakObjectPtr<AActor>>` list.
2. Update this list on spawn/destroy events.
3. Use `AsyncSaveGameToSlot`.

---

## 6. VERSION CONTROL AND MIGRATION

```cpp
// Add version to SaveGame
UPROPERTY(SaveGame)
int32 SaveVersion = 1;

// Migration in Subsystem
void USaveGameSubsystem::MigrateSaveData(UMySaveGame* Save)
{
    if (Save->SaveVersion < 2)
    {
        // V1→V2: e.g. PlayerHealth float → int conversion
        Save->SaveVersion = 2;
    }
    if (Save->SaveVersion < 3)
    {
        // V2→V3 migration
        Save->SaveVersion = 3;
    }
}
```

---

## 7. INVENTORY SAVING — RECOMMENDED PATTERN

```cpp
// Struct for inventory item (no DataAsset reference — ID only)
USTRUCT()
struct FInventoryItemSaveData
{
    GENERATED_BODY()

    UPROPERTY(SaveGame)
    FName ItemID;

    UPROPERTY(SaveGame)
    int32 Quantity;

    UPROPERTY(SaveGame)
    TMap<FName, float> DynamicStats; // Durability, damage, etc.
};

UPROPERTY(SaveGame)
TArray<FInventoryItemSaveData> InventoryItems;
```

---

## 8. SUBSYSTEM INIT PATTERN

```cpp
void USaveGameSubsystem::Initialize(FSubsystemCollectionBase& Collection)
{
    Super::Initialize(Collection);
    SaveSlotName = TEXT("SaveGame01");

    if (UGameplayStatics::DoesSaveGameExist(SaveSlotName, 0))
    {
        CurrentSaveGame = Cast<UMySaveGame>(
            UGameplayStatics::LoadGameFromSlot(SaveSlotName, 0));
    }
    else
    {
        CurrentSaveGame = Cast<UMySaveGame>(
            UGameplayStatics::CreateSaveGameObject(UMySaveGame::StaticClass()));
    }
}
```

---

## 9. AGENT RULES

- Serialize error → check `FObjectAndNameAsStringProxyArchive` + `ArIsSaveGame = true` first (ERROR-SL01, SL02)
- Property not being saved → check `UPROPERTY(SaveGame)` + `ArNoDelta` (ERROR-SL02, SL03)
- DataAsset reference disappearing → switch to ID pattern (ERROR-SL04)
- Runtime-spawned actors not found → suggest FGuid pattern (ERROR-SL06)
- Performance issue → suggest AsyncSave + actor list cache (ERROR-SL07)
- Version mismatch → suggest migration system
