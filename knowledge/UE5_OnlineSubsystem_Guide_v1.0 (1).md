# UE5 Online Subsystem & Sessions — Guide
### UE5 Dev Agent — Knowledge v1.0

---

## OVERVIEW

Online Subsystem (OSS) = UE's abstraction layer for online services.
Same C++ code works with Steam, EOS, NULL (LAN), Xbox, PlayStation.

**Available subsystems:**
```
NULL     → LAN / offline testing, no authentication required
Steam    → Valve's Steamworks (free, well-tested)
EOS      → Epic Online Services (cross-platform, free tier)
EOSPlus  → EOS + Steam combined (best of both)
```

---

## CHAPTER 1: SETUP

---

### OSS1 — Build.cs Dependencies

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "OnlineSubsystem",
    "OnlineSubsystemUtils",
    "OnlineSubsystemSteam",  // if using Steam
    "OnlineSubsystemEOS",    // if using EOS
});
```

---

### OSS2 — DefaultEngine.ini — Steam Setup

```ini
[/Script/Engine.GameEngine]
+NetDriverDefinitions=(DefName="GameNetDriver",DriverClassName="OnlineSubsystemSteam.SteamNetDriver",DriverClassNameFallback="OnlineSubsystemUtils.IpNetDriver")

[OnlineSubsystem]
DefaultPlatformService=Steam

[OnlineSubsystemSteam]
bEnabled=True
SteamDevAppId=480          ; 480 = Spacewar test app (for development)
                           ; Replace with your AppId for shipping
bRelaunchInSteam=False
GameServerQueryPort=27015
bVACEnabled=True

[/Script/OnlineSubsystemSteam.SteamNetDriver]
NetConnectionClassName="OnlineSubsystemSteam.SteamNetConnection"
```

---

### OSS3 — DefaultEngine.ini — EOS Setup

```ini
[OnlineSubsystem]
DefaultPlatformService=EOS

[OnlineSubsystemEOS]
bEnabled=true

[/Script/OnlineSubsystemEOS.NetDriverEOS]
bIsUsingP2PSockets=true
NetConnectionClassName="OnlineSubsystemEOS.NetConnectionEOS"

[/Script/Engine.GameEngine]
+NetDriverDefinitions=(DefName="GameNetDriver",DriverClassName="OnlineSubsystemEOS.NetDriverEOS",DriverClassNameFallback="OnlineSubsystemUtils.IpNetDriver")
```

EOS credentials set via Edit → Project Settings → Online Subsystem EOS.

---

### OSS4 — NULL Subsystem (LAN / Testing)

```ini
; DefaultEngine.ini for LAN-only testing:
[OnlineSubsystem]
DefaultPlatformService=NULL
```

NULL subsystem is perfect for:
- Local multiplayer testing without Steam/EOS credentials
- CI/CD automated testing
- Offline single-player with session code in place

---

## CHAPTER 2: SESSION MANAGEMENT C++

---

### OSS5 — Complete Session Manager Pattern

```cpp
// GameInstanceSubsystem is the recommended location for session logic:
UCLASS()
class UMySessionSubsystem : public UGameInstanceSubsystem
{
    GENERATED_BODY()

public:
    void CreateSession(int32 MaxPlayers, bool bIsLAN);
    void FindSessions(bool bIsLAN);
    void JoinSession(const FOnlineSessionSearchResult& Result);
    void DestroySession();

    // Delegates broadcast to Blueprint/game code:
    DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnCreateSessionComplete, bool, bWasSuccessful);
    UPROPERTY(BlueprintAssignable) FOnCreateSessionComplete OnCreateSessionComplete;

    DECLARE_DYNAMIC_MULTICAST_DELEGATE_OneParam(FOnFindSessionsComplete, bool, bWasSuccessful);
    UPROPERTY(BlueprintAssignable) FOnFindSessionsComplete OnFindSessionsComplete;

private:
    IOnlineSessionPtr GetSessionInterface() const;

    FOnCreateSessionCompleteDelegate CreateSessionCompleteDelegate;
    FOnFindSessionsCompleteDelegate FindSessionsCompleteDelegate;
    FOnJoinSessionCompleteDelegate JoinSessionCompleteDelegate;

    FDelegateHandle CreateSessionCompleteDelegateHandle;
    FDelegateHandle FindSessionsCompleteDelegateHandle;
    FDelegateHandle JoinSessionCompleteDelegateHandle;

    TSharedPtr<FOnlineSessionSearch> SessionSearch;
};
```

```cpp
// Create session:
void UMySessionSubsystem::CreateSession(int32 MaxPlayers, bool bIsLAN)
{
    IOnlineSessionPtr Sessions = GetSessionInterface();
    if (!Sessions.IsValid()) return;

    // Remove any existing session first:
    if (Sessions->GetNamedSession(NAME_GameSession))
        Sessions->DestroySession(NAME_GameSession);

    FOnlineSessionSettings SessionSettings;
    SessionSettings.bIsLANMatch = bIsLAN;
    SessionSettings.NumPublicConnections = MaxPlayers;
    SessionSettings.bShouldAdvertise = true;
    SessionSettings.bAllowJoinInProgress = true;
    SessionSettings.bUsesPresence = true;      // required for EOS P2P
    SessionSettings.bUseLobbiesIfAvailable = true; // Steam lobbies
    SessionSettings.Set(
        FName("SEARCH_KEYWORDS"),
        FString("MyGame"),
        EOnlineDataAdvertisementType::ViaOnlineServiceAndPing);

    CreateSessionCompleteDelegateHandle = Sessions->AddOnCreateSessionCompleteDelegate_Handle(
        CreateSessionCompleteDelegate);
    Sessions->CreateSession(0, NAME_GameSession, SessionSettings);
}

// Callback:
void UMySessionSubsystem::OnCreateSessionComplete(FName SessionName, bool bWasSuccessful)
{
    IOnlineSessionPtr Sessions = GetSessionInterface();
    if (Sessions.IsValid())
        Sessions->ClearOnCreateSessionCompleteDelegate_Handle(
            CreateSessionCompleteDelegateHandle);

    OnCreateSessionComplete.Broadcast(bWasSuccessful);

    if (bWasSuccessful)
    {
        // Travel to game map:
        GetWorld()->ServerTravel(TEXT("/Game/Maps/GameMap?listen"));
    }
}
```

---

### OSS6 — Find Sessions

```cpp
void UMySessionSubsystem::FindSessions(bool bIsLAN)
{
    IOnlineSessionPtr Sessions = GetSessionInterface();
    if (!Sessions.IsValid()) return;

    SessionSearch = MakeShared<FOnlineSessionSearch>();
    SessionSearch->MaxSearchResults = 10000;
    SessionSearch->bIsLanQuery = bIsLAN;
    SessionSearch->QuerySettings.Set(
        SEARCH_PRESENCE, true, EOnlineComparisonOp::Equals);

    FindSessionsCompleteDelegateHandle = Sessions->AddOnFindSessionsCompleteDelegate_Handle(
        FindSessionsCompleteDelegate);
    Sessions->FindSessions(0, SessionSearch.ToSharedRef());
}

void UMySessionSubsystem::OnFindSessionsComplete(bool bWasSuccessful)
{
    IOnlineSessionPtr Sessions = GetSessionInterface();
    if (Sessions.IsValid())
        Sessions->ClearOnFindSessionsCompleteDelegate_Handle(
            FindSessionsCompleteDelegateHandle);

    // Results in SessionSearch->SearchResults
    OnFindSessionsComplete.Broadcast(
        bWasSuccessful && SessionSearch->SearchResults.Num() > 0);
}
```

---

### OSS7 — Join Session

```cpp
void UMySessionSubsystem::JoinSession(const FOnlineSessionSearchResult& Result)
{
    IOnlineSessionPtr Sessions = GetSessionInterface();
    if (!Sessions.IsValid()) return;

    JoinSessionCompleteDelegateHandle = Sessions->AddOnJoinSessionCompleteDelegate_Handle(
        JoinSessionCompleteDelegate);
    Sessions->JoinSession(0, NAME_GameSession, Result);
}

void UMySessionSubsystem::OnJoinSessionComplete(
    FName SessionName, EOnJoinSessionCompleteResult::Type Result)
{
    IOnlineSessionPtr Sessions = GetSessionInterface();
    if (!Sessions.IsValid()) return;

    Sessions->ClearOnJoinSessionCompleteDelegate_Handle(
        JoinSessionCompleteDelegateHandle);

    if (Result == EOnJoinSessionCompleteResult::Success)
    {
        FString TravelURL;
        if (Sessions->GetResolvedConnectString(SessionName, TravelURL))
        {
            APlayerController* PC = GetGameInstance()->GetFirstLocalPlayerController();
            if (PC)
                PC->ClientTravel(TravelURL, ETravelType::TRAVEL_Absolute);
        }
    }
}
```

---

## CHAPTER 3: COMMON ERRORS

---

### OSS8 — Steam Not Working in Packaged Build
**Symptom:** Works in editor, fails in package

```
LogSteamShared: Warning: SteamAPI failed to initialize
LogOnline: Warning: STEAM: Steamworks: SteamUtils() failed!

Causes:
1. Steam not running — must have Steam client open
2. SteamDevAppId wrong — check DefaultEngine.ini
3. steam_appid.txt missing from build directory
   Create: [BuildDir]/steam_appid.txt with just "480" (or your AppId)
4. Steamworks SDK version mismatch — check plugin version
5. Running as different user than Steam — same account required
```

---

### OSS9 — Sessions Work in Editor, Fail in Standalone
**Symptom:** Create/Find sessions fail outside PIE

```
Editor uses special test credentials.
Standalone / packaged must use real Steam/EOS.

Fix for testing without full Steam setup:
→ Use NULL subsystem (LAN) for development
→ Set DefaultPlatformService=NULL in DefaultEngine.ini for testing builds
```

---

### OSS10 — Join Session Always Fails
**Symptom:** OnFailure delegate called immediately

```
Common causes:
1. Session not fully started before join:
   CreateSession → wait for OnCreateSessionComplete →
   THEN StartSession → THEN advertise

2. bUsesPresence mismatch:
   Host created with bUsesPresence=true
   Client searching with SEARCH_PRESENCE=false
   → Must match

3. Session not advertising:
   bShouldAdvertise must be true on host

4. AppId mismatch between host and client

5. Firewall blocking connection
   Test on same machine first (PIE multi-window)
```

---

### OSS11 — ServerTravel Failing After Session Join

```cpp
// Common mistake: travelling before session is fully established

// WRONG — travel immediately:
Sessions->JoinSession(0, NAME_GameSession, Result);
GetWorld()->ServerTravel(URL); // too early

// RIGHT — travel in callback:
void OnJoinSessionComplete(FName SessionName, EOnJoinSessionCompleteResult::Type Result)
{
    if (Result == EOnJoinSessionCompleteResult::Success)
    {
        // Get connection string AFTER session joined:
        FString TravelURL;
        Sessions->GetResolvedConnectString(SessionName, TravelURL);
        PC->ClientTravel(TravelURL, TRAVEL_Absolute);
    }
}
```

---

### OSS12 — Session Interface Null

```cpp
// GetSessionInterface pattern:
IOnlineSessionPtr UMySubsystem::GetSessionInterface() const
{
    IOnlineSubsystem* Subsystem = IOnlineSubsystem::Get();
    if (!Subsystem) return nullptr;
    return Subsystem->GetSessionInterface();
}

// Always check before use:
IOnlineSessionPtr Sessions = GetSessionInterface();
if (!Sessions.IsValid())
{
    UE_LOG(LogTemp, Error, TEXT("Session interface invalid — OSS not initialized"));
    return;
}
```

---

## QUICK REFERENCE

| Problem | Entry |
|---|---|
| Steam fails in package | OSS8 |
| Works in editor only | OSS9 |
| Join always fails | OSS10 |
| ServerTravel failing | OSS11 |
| Session interface null | OSS12 |
| Steam setup | OSS2 |
| EOS setup | OSS3 |
| LAN testing | OSS4 |
