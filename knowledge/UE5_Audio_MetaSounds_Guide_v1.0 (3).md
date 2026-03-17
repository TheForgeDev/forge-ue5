# UE5 Audio & MetaSounds — Error & Setup Guide
### UE5 Dev Agent — Knowledge v1.0

---

## AUDIO SYSTEMS OVERVIEW

```
Sound Wave      → raw audio file
Sound Cue       → node-based audio logic (UE4 style, still supported)
MetaSound       → DSP graph, sample-accurate, C++ extensible (UE5 preferred)
Sound Class     → volume/priority grouping
Sound Attenuation → 3D spatial settings
Sound Concurrency → controls simultaneous sound limits
Audio Component → actor component that plays audio
```

---

## CHAPTER 1: BASIC AUDIO C++

---

### AU1 — Playing Sounds — Four Methods

```cpp
// 1. One-shot at location (fire and forget):
UGameplayStatics::PlaySoundAtLocation(
    GetWorld(),
    MySoundAsset,       // USoundBase* (SoundWave, SoundCue, MetaSoundSource)
    GetActorLocation(),
    FRotator::ZeroRotator,
    1.0f,               // volume multiplier
    1.0f,               // pitch multiplier
    0.0f,               // start time
    nullptr,            // attenuation override
    nullptr             // concurrency override
);

// 2. Attached to component (follows actor):
UGameplayStatics::SpawnSoundAttached(
    MySoundAsset,
    GetRootComponent(),
    NAME_None,          // socket name
    FVector::ZeroVector,
    EAttachLocation::KeepRelativeOffset,
    true                // stop when attached component destroyed
);

// 3. 2D (non-spatial, UI sounds, music):
UGameplayStatics::PlaySound2D(GetWorld(), MySoundAsset);

// 4. Audio Component (controllable, stoppable):
UAudioComponent* AudioComp =
    UGameplayStatics::SpawnSoundAtLocation(
        GetWorld(), MySoundAsset, GetActorLocation());
// Can then: AudioComp->Stop(), AudioComp->SetVolumeMultiplier(0.5f)
```

---

### AU2 — Audio Component — Setup and Control

```cpp
// .h
UPROPERTY()
TObjectPtr<UAudioComponent> AudioComponent;

// BeginPlay — create persistent audio component:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    AudioComponent = UGameplayStatics::SpawnSoundAttached(
        LoopSound,
        GetRootComponent());

    if (IsValid(AudioComponent))
    {
        AudioComponent->SetAutoActivate(false);
        AudioComponent->Stop();
    }
}

// Play/Stop:
if (IsValid(AudioComponent))
{
    AudioComponent->Play();
    AudioComponent->Stop();
    AudioComponent->SetVolumeMultiplier(0.5f);
    AudioComponent->SetPitchMultiplier(1.2f);
    AudioComponent->FadeIn(1.0f, 1.0f);   // fade duration, target volume
    AudioComponent->FadeOut(1.0f, 0.0f);  // fade duration, target volume
}
```

---

### AU3 — Sound Not Playing — Common Causes

```
Checklist:
[ ] Sound asset assigned (not null)?
[ ] Volume multiplier > 0?
[ ] Not outside attenuation range?
[ ] Sound Concurrency not blocking it?
    (too many instances of same sound)
[ ] Sound Class volume not 0?
[ ] Audio device initialized?
    (may not init in headless server builds)
[ ] Platform audio device present?
    (some CI/CD environments have no audio)

Debug:
au.Debug.SoundVisualizations 1    // show active sounds in world
stat SoundWaves                   // audio memory stats  
stat SoundMixes                   // active sound mix info
au.3DVisualize.Enabled 1         // 3D debug visualization
```

---

### AU4 — Looping Sound Memory Leak
**Symptom:** RAM increases over time, audio keeps playing after actor destroyed

```cpp
// WRONG — sound keeps playing after actor destroyed:
UGameplayStatics::SpawnSoundAttached(LoopSound, GetRootComponent());
// No reference kept, can't stop it

// RIGHT — keep reference, stop in EndPlay:
UPROPERTY()
TObjectPtr<UAudioComponent> LoopAudioComp;

void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    LoopAudioComp = UGameplayStatics::SpawnSoundAttached(
        LoopSound, GetRootComponent());
}

void AMyActor::EndPlay(const EEndPlayReason::Type EndPlayReason)
{
    Super::EndPlay(EndPlayReason);
    if (IsValid(LoopAudioComp))
    {
        LoopAudioComp->Stop();
        LoopAudioComp->DestroyComponent();
    }
}
```

---

## CHAPTER 2: METASOUNDS

---

### AU5 — MetaSound vs Sound Cue — When to Use

| Feature | Sound Cue | MetaSound |
|---|---|---|
| Sample-accurate timing | ❌ | ✅ |
| Custom DSP nodes in C++ | ❌ | ✅ |
| Real-time parameter control | Limited | ✅ Full |
| Audio engine integration | ✅ Mature | ✅ UE5 native |
| Mobile support | ✅ | ✅ (UE5.2+) |
| Learning curve | Lower | Higher |

**Use MetaSound for:** Music, complex SFX, procedural audio, DSP effects
**Use Sound Cue for:** Simple random variations, legacy projects

---

### AU6 — MetaSound Modules Required

```csharp
// Build.cs:
PublicDependencyModuleNames.AddRange(new string[]
{
    "MetasoundEngine",    // core MetaSound runtime
    "MetasoundFrontend",  // MetaSound graph API
    "AudioExtensions",    // audio parameter interface
});
```

```json
// .uplugin (if in a plugin):
"Plugins": [
    { "Name": "MetasoundEngine", "Enabled": true }
]
```

---

### AU7 — Setting MetaSound Parameters from C++

MetaSound parameters are set via the Audio Parameter Interface.

```cpp
#include "MetasoundParameterTransmitter.h"
#include "AudioParameter.h"

// Get the audio component playing the MetaSound:
UAudioComponent* AudioComp = /* your audio component */;

// Set float parameter:
AudioComp->SetFloatParameter(FName("Speed"), 100.0f);

// Set bool parameter (triggers):
AudioComp->SetBoolParameter(FName("Jump"), true);

// Set int parameter:
AudioComp->SetIntParameter(FName("WeaponType"), 2);

// Trigger an event (one-shot pulse):
AudioComp->SetBoolParameter(FName("FireTrigger"), true);
// For triggers: set true, MetaSound handles the one-shot internally
```

**Parameter names must match the Input node names in the MetaSound graph exactly.**

---

### AU8 — FObjectFinder with MetaSound Crashes Editor
**Known UE5 bug (fixed in later versions):**

```cpp
// WRONG — crashes editor when MetaSound asset is open:
static ConstructorHelpers::FObjectFinder<UMetaSoundSource>
    MetaSoundFinder(TEXT("MetaSoundSource'/Game/Sounds/MS_Explosion.MS_Explosion'"));

// WORKAROUND — use TSoftObjectPtr instead:
UPROPERTY(EditAnywhere)
TSoftObjectPtr<UMetaSoundSource> MetaSoundAsset;

// Load when needed:
UMetaSoundSource* Sound = MetaSoundAsset.LoadSynchronous();
if (Sound)
    UGameplayStatics::PlaySoundAtLocation(GetWorld(), Sound, Location);
```

---

### AU9 — MetaSound Not Playing on Mobile
**Symptom:** MetaSound silent on Android/iOS, works on PC

```
UE5.0-5.1: MetaSound had limited mobile support
UE5.2+: Full mobile support

Fix for UE5.0-5.1:
→ Use Sound Cue wrapping a Sound Wave for mobile
→ Or upgrade to UE5.2+

Check:
Project Settings → Audio → Platform-specific settings
Ensure MetaSound is enabled for target platform
```

---

### AU10 — Sound Attenuation Not Working
**Symptom:** 3D sound heard everywhere, no distance falloff

```cpp
// Attenuation must be assigned or overridden:

// Option 1 — assign attenuation asset to sound:
// Sound asset → Details → Attenuation → Override Attenuation

// Option 2 — pass attenuation at play time:
USoundAttenuation* MyAttenuation = /* asset reference */;
UGameplayStatics::PlaySoundAtLocation(
    GetWorld(),
    MySoundAsset,
    Location,
    FRotator::ZeroRotator,
    1.0f, 1.0f, 0.0f,
    MyAttenuation  // override here
);

// Common attenuation settings:
// Inner Radius: distance at full volume
// Outer Radius: distance at zero volume
// Falloff Mode: Linear, Logarithmic, Custom
```

**Non-sphere attenuation shapes (Box, Cone, Capsule) had bugs in early UE5.**
If using non-sphere: test on UE5.3+ for reliable behavior.

---

## CHAPTER 3: SOUND CONCURRENCY

---

### AU11 — Too Many Sounds Causing Audio Dropouts

```cpp
// Sound Concurrency limits simultaneous instances.
// When limit exceeded: oldest or quietest is stopped.

// Create Concurrency asset in editor, or override in C++:
USoundConcurrency* MyConcurrency = /* asset reference */;

UGameplayStatics::PlaySoundAtLocation(
    GetWorld(), MySoundAsset, Location,
    FRotator::ZeroRotator, 1.0f, 1.0f, 0.0f,
    nullptr,        // attenuation
    MyConcurrency   // concurrency
);

// Concurrency settings:
// Max Count: max simultaneous instances
// Resolution Rule:
//   StopFarthest → stop farthest from listener
//   StopOldest → stop oldest instance
//   StopQuietest → stop quietest instance
//   PreventNew → reject new instances when limit reached
```

---

## CHAPTER 4: AUDIO OPTIMIZATION

---

### AU12 — Audio Performance Tips

```
1. Virtualization — sounds outside range go "virtual" (paused, not destroyed)
   Sound asset → Virtualization Mode → Restart (recommended for looping)

2. Sound Quality settings per distance:
   Closer sounds → higher quality streaming
   Distant sounds → compressed/virtualized

3. Compression:
   Voice/SFX: ADPCM or OGG Vorbis
   Music: OGG Vorbis with higher quality
   UI: Uncompressed (short, needs instant playback)

4. Streaming vs In-Memory:
   Short SFX → In-Memory (no streaming overhead)
   Music/Long ambient → Streaming (saves RAM)
   Sound Wave → Details → Loading Behavior → Streaming

5. Batch similar sounds with Sound Concurrency:
   Don't play 50 simultaneous footstep sounds
   Use concurrency to limit to 4-6 at most

Console commands:
stat SoundWaves        // memory and active sounds
au.Debug.Sounds 1     // list active sounds
au.VirtualLoops 1     // enable loop virtualization
```

---

## QUICK REFERENCE

| Problem | Entry |
|---|---|
| Sound not playing | AU3 |
| Looping sound memory leak | AU4 |
| MetaSound vs Sound Cue choice | AU5 |
| Missing modules for MetaSound | AU6 |
| Set MetaSound parameter | AU7 |
| FObjectFinder crash | AU8 |
| MetaSound silent on mobile | AU9 |
| No distance falloff | AU10 |
| Audio dropouts | AU11 |
| Performance | AU12 |
