# UE5 Material & Shader — Error & Setup Guide
### UE5 Dev Agent — Knowledge v1.0

---

## TERMINOLOGY

```
Material       → node graph in UE editor, defines appearance
Shader         → compiled HLSL code generated from Material
Material Instance (MIC) → child of Material, constant parameters, no recompile
Material Instance Dynamic (MID) → runtime-editable MIC, changed via C++
Material Parameter Collection (MPC) → global parameters shared across many materials
HLSL Custom Node → raw HLSL code embedded in Material graph
```

One Material generates **many shader permutations** — per vertex factory,
per render pass, per platform. This is why compilation takes long.

---

## CHAPTER 1: MATERIAL INSTANCE ERRORS

---

### MAT1 — Creating MID Every Frame (Performance Killer)
**Tier:** 1 — Extremely common mistake
**Symptom:** FPS drops, high CPU usage

```cpp
// WRONG — creates new MID every tick:
void AMyActor::Tick(float DeltaTime)
{
    UMaterialInstanceDynamic* MID =
        UKismetMaterialLibrary::CreateDynamicMaterialInstance(
            GetWorld(), BaseMaterial); // expensive! creates new object
    MID->SetScalarParameterValue("Health", CurrentHealth);
}

// RIGHT — create once in BeginPlay, reuse:
UPROPERTY()
TObjectPtr<UMaterialInstanceDynamic> DynamicMaterial;

void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    // Create MID from mesh's existing material:
    DynamicMaterial = GetMesh()->CreateAndSetMaterialInstanceDynamic(0);
    // OR from a base material asset:
    DynamicMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);
    GetMesh()->SetMaterial(0, DynamicMaterial);
}

void AMyActor::Tick(float DeltaTime)
{
    if (IsValid(DynamicMaterial))
        DynamicMaterial->SetScalarParameterValue("Health", CurrentHealth);
}
```

---

### MAT2 — Parameter Name Case Sensitivity
**Tier:** 1 — Silent failure, no error
**Symptom:** SetScalarParameterValue has no visible effect

```cpp
// Material Editor parameter name: "EmissiveStrength"
// Code must match EXACTLY — case sensitive:

DynamicMaterial->SetScalarParameterValue("EmissiveStrength", 2.f); // works
DynamicMaterial->SetScalarParameterValue("emissivestrength", 2.f); // silent fail
DynamicMaterial->SetScalarParameterValue("Emissive Strength", 2.f); // silent fail
```

**Debug:** Enable material parameter name logging or use
`Window → HLSL Code` in Material Editor to verify parameter names.

---

### MAT3 — Wrong Set Function for Parameter Type
**Tier:** 1

```cpp
// Float → SetScalarParameterValue:
MID->SetScalarParameterValue(FName("Roughness"), 0.5f);
MID->SetScalarParameterValue(FName("EmissiveIntensity"), 3.0f);

// Color / Vector → SetVectorParameterValue:
MID->SetVectorParameterValue(FName("BaseColor"), FLinearColor(1, 0, 0, 1));
MID->SetVectorParameterValue(FName("Tint"), FLinearColor::Red);

// Texture → SetTextureParameterValue:
MID->SetTextureParameterValue(FName("DiffuseTexture"), MyTexture);

// Double check: what type is the parameter in Material Editor?
// Scalar → float → SetScalarParameterValue
// Vector/Color → FLinearColor → SetVectorParameterValue
// Texture2D → UTexture → SetTextureParameterValue
```

---

### MAT4 — Parameter Not Exposed in Base Material
**Tier:** 1 — Silent failure
**Symptom:** SetParameter has no effect even with correct name/type

For a parameter to be settable on an Instance, it must be a
**named Parameter node** in the Material Editor — not a hardcoded value.

```
Material Editor fix:
- Roughness constant 0.5 → NOT settable
- ScalarParameter named "Roughness" with default 0.5 → settable

Right-click any value → "Convert to Parameter"
Give it a name that matches your C++ code
```

---

### MAT5 — MID Null After CreateAndSetMaterialInstanceDynamic
**Tier:** 2
**Symptom:** Access violation when calling SetParameter

```cpp
// Common causes:
// 1. Mesh has no material assigned at slot 0
// 2. Called before mesh is initialized (too early in BeginPlay)
// 3. Mesh component not valid

// RIGHT — always check validity:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();
    if (USkeletalMeshComponent* Mesh = GetMesh())
    {
        DynamicMaterial = Mesh->CreateAndSetMaterialInstanceDynamic(0);
        if (!IsValid(DynamicMaterial))
        {
            UE_LOG(LogTemp, Error,
                TEXT("Failed to create MID — check mesh has material at slot 0"));
        }
    }
}
```

---

## CHAPTER 2: MATERIAL PARAMETER COLLECTION (MPC)

---

### MAT6 — MPC vs MID — When to Use Which

**Use MPC when:** Effect applies to many objects simultaneously
(time of day, rain wetness, global dissolve, storm boundary)

**Use MID when:** Effect is per-actor specific
(health bar, weapon glow, individual damage flash)

```cpp
// Set MPC parameter from C++:
#include "Materials/MaterialParameterCollection.h"
#include "Materials/MaterialParameterCollectionInstance.h"
#include "Kismet/KismetMaterialLibrary.h"

// In any function:
UKismetMaterialLibrary::SetScalarParameterValue(
    GetWorld(),
    MyParameterCollection, // UMaterialParameterCollection* asset reference
    FName("TimeOfDay"),
    CurrentHour
);

UKismetMaterialLibrary::SetVectorParameterValue(
    GetWorld(),
    MyParameterCollection,
    FName("SunColor"),
    FLinearColor(1.0f, 0.9f, 0.7f, 1.0f)
);
```

**Important:** MPC updates all materials using that collection in one call.
Much more efficient than updating each MID individually.

---

## CHAPTER 3: SHADER COMPILATION

---

### MAT7 — Shader Compilation on First Run / Loading Screen
**Symptom:** Hitches or freezes the first time objects appear

UE compiles shaders asynchronously but some trigger synchronous compilation.

**Mitigation:**
```
Project Settings → Rendering → Shader Permutation Reduction
→ Enable "Support Stationary Skylight" only if needed
→ Disable unused features (reduces permutation count)

Project Settings → Rendering → Shader Compilation
→ Enable "Share Material Shader Code" — reduces duplication
→ Enable "Pre-compile Material Shaders" — bakes shaders at package time

Console: r.ShaderPipelineCache.BatchSize 50  (controls batch size)
```

---

### MAT8 — Shader Compilation Errors in Custom Node
**Tier:** 2
**Symptom:** Red error in Material Editor, "Shader compile failed"

```
Custom Node HLSL rules:
1. Code is pasted inside a function — cannot define functions at global scope
   WRONG: float MyFunc() { return 1; }
   RIGHT: Use struct trick (see below)

2. Must have a return statement:
   return 1; // required even for void-like operations

3. Missing closing brace on purpose:
   UE adds one automatically — don't add it yourself

4. Input pins accessed by their pin name directly:
   // If input pin named "MyValue":
   return MyValue * 2;

5. Global variables trick:
   // Define outside the function using struct:
   struct Helpers {
       float MyFunc(float x) { return x * 2; }
   };
   Helpers h;
   return h.MyFunc(MyInput);
```

**Debug:** `Window → HLSL Code` in Material Editor — see generated code.

---

### MAT9 — Custom Node: External .usf File Not Found
**Tier:** 3
**Symptom:** #include in Custom Node fails

```cpp
// 1. Create /Shaders/ folder at project root (same level as /Content/)

// 2. Add to primary module's StartupModule():
void FMyGameModule::StartupModule()
{
    FString ShaderDir = FPaths::Combine(
        FPaths::ProjectDir(), TEXT("Shaders"));
    AddShaderSourceDirectoryMapping(TEXT("/Project"), ShaderDir);
}

// 3. In Custom Node:
#include "/Project/MyShader.usf"
return MyFunction(Input);

// 4. Module must load at PostConfigInit:
// MyGame.uproject → Modules → LoadingPhase → PostConfigInit
```

---

### MAT10 — Shader Compilation Speed — Reducing Time

```
1. Reduce permutations:
   Material → Details → Usage
   Uncheck any "Used with X" that you don't actually use
   Each checked box = more permutations = longer compile

2. Use Static Switch Parameters instead of dynamic branches:
   Static switches compile separate permutations
   but reduce runtime cost vs dynamic if/else in shader

3. Separate slow materials:
   Materials with many instructions compile slower
   Split complex materials into simpler ones where possible

4. Shader compiler settings (ConsoleVariables.ini):
   r.ShaderDevelopmentMode=1    // better error messages
   r.Shaders.Optimize=0         // faster iteration (debug only)
   r.Shaders.KeepDebugInfo=1    // better shader debugging
```

---

## CHAPTER 4: COMMON MATERIAL FEATURES

---

### MAT11 — Nanite Incompatible Materials
**Symptom:** Mesh invisible or falls back to default material with Nanite

**Materials incompatible with Nanite:**
```
- Two-sided foliage shading model (UE5.0-5.2)
- World Position Offset with heavy deformation (limited support)
- Unlit shading model (limited support)
- Tessellation (UE5.0-5.2, added experimental in 5.3)
- Subsurface / Eye / Hair shading models (check version support)
```

**Check compatibility:**
```
Material Editor → Stats panel → "Nanite" row
Green checkmark = compatible
Red X = incompatible, will fall back to non-Nanite rendering
```

---

### MAT12 — World Position Offset Not Working
**Symptom:** WPO material applied to Nanite mesh has no effect

```
UE5.0: WPO not supported on Nanite meshes
UE5.1+: Limited WPO support (static mesh subdivides into clusters)

For heavy vertex animation (wind, cloth):
→ Disable Nanite on that mesh
→ Or use non-deforming Nanite mesh + separate skeletal deformation
```

---

### MAT13 — Translucent Material Sorting Issues
**Symptom:** Translucent objects render in wrong order, Z-fighting

```
Translucent materials sort by distance from camera — no depth write.
When two translucent objects overlap = sorting artifacts.

Solutions:
1. Use Dithered Opacity (Material → Details → Dithered LOD Transition)
   Looks like transparency but writes depth

2. Masked blend mode instead of Translucent
   Hard edges but correct depth sorting

3. Separate Sort Priority:
   Component → Details → Translucency Sort Priority
   Higher number = rendered in front

4. Screen Space Reflections won't hit translucent surfaces
   Use Lumen reflections or Planar Reflections instead
```

---

### MAT14 — Emissive Not Affecting Lumen
**Symptom:** Emissive material surface is bright but doesn't light nearby geometry

```
Emissive surfaces affect Lumen IF:
→ Material has Emissive Color connected with meaningful output
→ "Use Emissive for Static Lighting" checked in Material Details
→ Lumen surface cache can "see" the emissive surface

Debug: r.Lumen.Visualize.Overview 1
→ Check if emissive surface shows up in Lumen surface cache
```

---

## CHAPTER 5: C++ MATERIAL OPERATIONS

---

### MAT15 — Full C++ Material Setup Pattern

```cpp
// .h
UPROPERTY(EditAnywhere, Category = "Materials")
TObjectPtr<UMaterialInterface> BaseMaterial;

UPROPERTY()
TObjectPtr<UMaterialInstanceDynamic> DynamicMaterial;

// .cpp BeginPlay:
void AMyActor::BeginPlay()
{
    Super::BeginPlay();

    // Create MID:
    if (IsValid(BaseMaterial))
    {
        DynamicMaterial = UMaterialInstanceDynamic::Create(BaseMaterial, this);
        GetMesh()->SetMaterial(0, DynamicMaterial);
    }
}

// Update parameters:
void AMyActor::UpdateMaterial(float Health, FLinearColor TeamColor)
{
    if (!IsValid(DynamicMaterial)) return;

    DynamicMaterial->SetScalarParameterValue(FName("HealthPercent"),
        FMath::Clamp(Health / MaxHealth, 0.f, 1.f));
    DynamicMaterial->SetVectorParameterValue(FName("TeamColor"), TeamColor);
}
```

---

### MAT16 — Material on Multiple Mesh Slots

```cpp
// Apply MID to all material slots:
int32 SlotCount = GetMesh()->GetNumMaterials();
for (int32 i = 0; i < SlotCount; ++i)
{
    UMaterialInstanceDynamic* MID =
        GetMesh()->CreateAndSetMaterialInstanceDynamic(i);
    MIDArray.Add(MID);
}

// Update all slots:
for (UMaterialInstanceDynamic* MID : MIDArray)
{
    if (IsValid(MID))
        MID->SetScalarParameterValue("Dissolve", DissolveAmount);
}
```

---

## QUICK REFERENCE

| Problem | Entry |
|---|---|
| SetParameter no effect | MAT2 (name), MAT3 (type), MAT4 (not exposed) |
| FPS drops from materials | MAT1 (creating MID every frame) |
| MID null crash | MAT5 |
| Global material effect | MAT6 (use MPC) |
| Shader compile error | MAT8 |
| External HLSL not found | MAT9 |
| Nanite mesh invisible | MAT11 |
| WPO not working | MAT12 |
| Emissive not lighting scene | MAT14 |
| Shader compile too slow | MAT7, MAT10 |
