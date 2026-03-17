# UE5 Render Pipeline (RDG) & PCG — Guide
### UE5 Dev Agent — Knowledge v1.0

---

## PART 1: RENDER DEPENDENCY GRAPH (RDG)

---

## RDG OVERVIEW

RDG = Render Dependency Graph. UE5's GPU scheduling system.

Instead of executing GPU commands immediately, RDG:
1. **Setup phase** — records all passes and their resource dependencies
2. **Compile phase** — figures out resource lifetimes, culls unused passes
3. **Execute phase** — dispatches to GPU in dependency order

Benefits: automatic async compute, memory aliasing, barrier optimization.

**Threading model:**
```
Game Thread    → gameplay logic, spawning
Render Thread  → RDG pass setup, resource management
RHI Thread     → actual GPU command submission
```

Never access game thread objects from render thread directly.
Use `ENQUEUE_RENDER_COMMAND` to pass data across.

---

## RDG BASICS

### RDG1 — Module Dependencies for Custom Passes

```csharp
// Build.cs — required for custom render passes:
PrivateDependencyModuleNames.AddRange(new string[]
{
    "Renderer",        // FSceneViewExtension, render hooks
    "RenderCore",      // RDG API, shader parameter structs
    "RHI",             // GPU resource types
    "Engine",          // Scene, ViewFamily
    "Projects",        // shader directory mapping
});

// For shader module (must load at PostConfigInit):
// Module LoadingPhase = "PostConfigInit" in .uplugin
```

---

### RDG2 — FSceneViewExtension — Hooking Into Render Pipeline

The cleanest way to add custom passes without modifying engine code.

```cpp
// .h
class FMyRenderExtension : public FSceneViewExtensionBase
{
public:
    FMyRenderExtension(const FAutoRegister& AutoRegister)
        : FSceneViewExtensionBase(AutoRegister) {}

    // Available hooks (override what you need):
    virtual void PreRenderViewFamily_RenderThread(
        FRDGBuilder& GraphBuilder,
        FSceneViewFamily& InViewFamily) override {}

    virtual void PostRenderBasePassDeferred_RenderThread(
        FRDGBuilder& GraphBuilder,
        FSceneView& InView,
        const FRenderTargetBindingSlots& RenderTargets,
        TRDGUniformBufferRef<FSceneTextureUniformParameters> SceneTextures) override {}

    virtual void PrePostProcessPass_RenderThread(
        FRDGBuilder& GraphBuilder,
        const FSceneView& View,
        const FPostProcessingInputs& Inputs) override;
    // ↑ Most common — runs right before post-process, has access to SceneColor
};
```

**Register in StartupModule:**
```cpp
MyExtension = FSceneViewExtensions::NewExtension<FMyRenderExtension>();
```

**Unregister in ShutdownModule:**
```cpp
MyExtension.Reset(); // TSharedPtr reset = unregisters
```

---

### RDG3 — Adding a Custom Compute Pass

```cpp
void FMyRenderExtension::PrePostProcessPass_RenderThread(
    FRDGBuilder& GraphBuilder,
    const FSceneView& View,
    const FPostProcessingInputs& Inputs)
{
    // 1. Get SceneColor as RDG texture:
    FRDGTextureRef SceneColorTexture = (*Inputs.SceneTextures)->SceneColorTexture;

    // 2. Create output texture (or UAV on SceneColor for in-place edit):
    FRDGTextureRef OutputTexture = GraphBuilder.CreateTexture(
        SceneColorTexture->Desc,
        TEXT("MyOutputTexture"));

    // 3. Set up shader parameters:
    FMyShaderClass::FParameters* PassParams =
        GraphBuilder.AllocParameters<FMyShaderClass::FParameters>();
    PassParams->InputTexture = SceneColorTexture;
    PassParams->OutputTexture = GraphBuilder.CreateUAV(OutputTexture);
    PassParams->View = View.ViewUniformBuffer;

    // 4. Get shader:
    TShaderMapRef<FMyShaderClass> Shader(GetGlobalShaderMap(View.FeatureLevel));

    // 5. Add pass to graph:
    FComputeShaderUtils::AddPass(
        GraphBuilder,
        RDG_EVENT_NAME("MyCustomPass"),
        ERDGPassFlags::Compute,
        Shader,
        PassParams,
        FIntVector(
            FMath::DivideAndRoundUp(View.ViewRect.Width(), 8),
            FMath::DivideAndRoundUp(View.ViewRect.Height(), 8),
            1)
    );

    // 6. Copy output back to SceneColor if needed:
    AddCopyTexturePass(GraphBuilder, OutputTexture, SceneColorTexture);
}
```

---

### RDG4 — Global Shader Declaration

```cpp
// .h
class FMyShaderClass : public FGlobalShader
{
    DECLARE_GLOBAL_SHADER(FMyShaderClass);
    SHADER_USE_PARAMETER_STRUCT(FMyShaderClass, FGlobalShader);

    BEGIN_SHADER_PARAMETER_STRUCT(FParameters, )
        SHADER_PARAMETER_STRUCT_REF(FViewUniformShaderParameters, View)
        SHADER_PARAMETER_RDG_TEXTURE(Texture2D, InputTexture)
        SHADER_PARAMETER_RDG_TEXTURE_UAV(RWTexture2D, OutputTexture)
        SHADER_PARAMETER(float, MyFloat)
    END_SHADER_PARAMETER_STRUCT()

    static bool ShouldCompilePermutation(
        const FGlobalShaderPermutationParameters& Parameters)
    {
        return IsFeatureLevelSupported(Parameters.Platform, ERHIFeatureLevel::SM5);
    }
};

// .cpp — link to .usf file:
IMPLEMENT_GLOBAL_SHADER(FMyShaderClass, "/Project/MyShader.usf", "MainCS", SF_Compute);
```

---

### RDG5 — Shader Directory Mapping

```cpp
// In module StartupModule():
void FMyShaderModule::StartupModule()
{
    FString ShaderDir = FPaths::Combine(
        FPluginManager::Get().FindPlugin(TEXT("MyPlugin"))->GetBaseDir(),
        TEXT("Shaders"));
    AddShaderSourceDirectoryMapping(TEXT("/Project"), ShaderDir);
}

// Module LoadingPhase MUST be PostConfigInit in .uplugin
// Otherwise shaders register too late
```

---

### RDG6 — RDG Debugging

```ini
; ConsoleVariables.ini — for shader/RDG debugging:
r.RDG.ImmediateMode=1    ; execute passes immediately, easier crash debugging
r.RDG.Debug=1            ; verbose RDG warnings
r.ShaderDevelopmentMode=1
r.Shaders.Optimize=0     ; faster iteration (don't ship with this)
```

```
RenderDoc integration:
RDG_EVENT_SCOPE(GraphBuilder, "MyPassGroup")  → visible in RenderDoc
RDG_EVENT_NAME("MyPass")                       → pass label in RDG Insights

UE Insights → RDG tab → shows pass graph, resource lifetimes
```

---

## PART 2: PCG (PROCEDURAL CONTENT GENERATION)

---

## PCG OVERVIEW

PCG = node-based procedural placement system. Available UE5.2+.

**Key concepts:**
```
PCGGraph      → node graph defining generation logic
PCGComponent  → actor component that runs a PCGGraph
PCGVolume     → actor that defines generation bounds
Point         → basic PCG data unit (position, transform, metadata)
Data Layer    → input source (landscape, splines, actors, custom)
```

**Version history:**
```
UE5.2 → Introduced as experimental
UE5.3 → Beta, major features added
UE5.4 → Production ready, runtime generation stable
UE5.5 → Megafusion (Niagara + PCG integration)
```

---

### PCG1 — Build.cs Setup

```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "PCG",
    "PCGCompute",    // if using GPU compute nodes (UE5.4+)
});
```

---

### PCG2 — Custom PCG Node in C++

```cpp
// .h
UCLASS(BlueprintType, ClassGroup=(Custom))
class UPCGMyNode : public UPCGSettings
{
    GENERATED_BODY()

public:
    // Node configuration exposed in editor:
    UPROPERTY(BlueprintReadWrite, EditAnywhere, Category = "Settings")
    float ScatterRadius = 100.f;

    // Required overrides:
    virtual TArray<FPCGPinProperties> InputPinProperties() const override;
    virtual TArray<FPCGPinProperties> OutputPinProperties() const override;

protected:
    virtual FPCGElementPtr CreateElement() const override;
};

// The execution element:
class FPCGMyElement : public FSimplePCGElement
{
protected:
    virtual bool ExecuteInternal(
        FPCGContext* Context) const override;
};
```

---

### PCG3 — Runtime PCG Generation

```cpp
// Generate PCG at runtime (UE5.4+):
UPCGComponent* PCGComp = MyActor->FindComponentByClass<UPCGComponent>();
if (IsValid(PCGComp))
{
    PCGComp->Generate(true); // true = force regenerate
}

// Common error: partitioned PCG won't generate on demand
// Fix: ensure PCG Volume is loaded before calling Generate()
// LogPCG: Error: [ScheduleComponent] Didn't schedule any task
// → Component not initialized or volume not streamed in
```

---

### PCG4 — Common PCG Errors

**Graph not generating:**
```
1. PCGComponent on actor?
2. PCGGraph assigned to component?
3. PCGVolume bounds cover generation area?
4. Landscape/Spline inputs valid?
   → Check "Generate on Creation" setting
   → Try manual Generate() call
```

**Points disappearing after streaming:**
```
World Partition + PCG: PCG re-generates when cells stream in.
For persistent PCG results: bake to static meshes or
use "Generate on Load" setting on PCGComponent.
```

**Performance — PCG too slow:**
```
1. Enable "Use Seed" for deterministic + cacheable results
2. Reduce point count before expensive operations
3. Use "Partition Component" for large areas
4. GPU compute nodes (UE5.4+) for heavy operations
5. Avoid GetActorsOfClass inside PCG — use dedicated data inputs
```

---

### PCG5 — PCG Debugging

```
PCG Editor:
- Click node → see point data at that stage
- Right-click → Inspect → visualize in viewport
- Enable "Debug" on graph → step through execution

Console:
pcg.debug.showgraph 1          → show active PCG graphs
pcg.debug.drawpoints 1         → visualize generated points
LogPCG Verbose                 → detailed execution log
```
