# UE5 Version Differences — Knowledge File
### UE5 Dev Agent — Knowledge v1.0

---

## UE5.0 (April 2022)

### What's new
- **Lumen** — fully dynamic global illumination, stable release
- **Nanite** — virtualized geometry, stable release
- **Chaos Physics** — PhysX fully replaced
- **World Partition** — open world streaming system
- **Control Rig** — procedural animation system
- **MetaHuman** — high-fidelity character framework

### Breaking changes from UE4
- PhysX removed → must migrate to Chaos
- Lightmass baking still available but Lumen preferred
- `TObjectPtr<T>` introduced — new recommended pointer type for UPROPERTY headers
- Build system changes — UnrealBuildTool updates

### Known issues in 5.0
- Lumen performance on Software mode was expensive — improved in later versions
- Nanite foliage not supported (added later)
- World Partition still maturing

---

## UE5.1 (November 2022)

### What's new
- **Enhanced Input** — new input system, legacy system deprecated
- **Substrate** — new material system (experimental, opt-in)
- **Procedural Animation** — improvements to Control Rig
- **Lumen improvements** — better performance, reduced noise
- **Nanite improvements** — better foliage support (still limited)
- **One File Per Actor** — collaborative level editing

### Migration notes from 5.0
- Start migrating from legacy Input system to Enhanced Input
- Legacy Input still works in 5.1 but shows deprecation warnings

### Enhanced Input migration checklist
```
1. Project Settings → Input → Default Player Input Class → EnhancedPlayerInput
2. Project Settings → Input → Default Input Component Class → EnhancedInputComponent
3. Create InputAction assets for each action
4. Create InputMappingContext asset
5. Add MappingContext in PlayerController/Character BeginPlay
6. Bind actions using UEnhancedInputComponent::BindAction
```

---

## UE5.2 (May 2023)

### What's new
- **PCG (Procedural Content Generation)** — node-based procedural placement system
- **Nanite Tessellation** — displacement maps on Nanite meshes (experimental)
- **Substrate** — more stable, still experimental
- **Virtual Shadow Maps** — improvements, better performance
- **Motion Warping** — improved character animation warping
- **Skeletal Mesh Editor** — unified asset editor

### Breaking changes
- Some Blueprint nodes deprecated — check migration notes
- Chaos Vehicle improvements may require reconfiguration

### PCG quick start
```cpp
// Access PCG in C++:
#include "PCGComponent.h"
#include "PCGGraph.h"

// Add module to Build.cs:
PublicDependencyModuleNames.AddRange(new string[] { "PCG" });
```

---

## UE5.3 (September 2023)

### What's new
- **Substrate** — production-ready (still opt-in but stable)
- **Mass Entity** — ECS framework, stable release
- **Nanite for Skeletal Meshes** — experimental
- **Virtual Shadow Maps** — significant quality improvements
- **Path Tracer** — production-quality path tracing for cinematics
- **Temporal Super Resolution (TSR)** — improved upscaling
- **HLOD improvements** — better streaming for open worlds

### Mass Entity basics
```cpp
// Add to Build.cs:
PublicDependencyModuleNames.AddRange(new string[] {
    "MassEntity", "MassCommon", "MassSpawner"
});

// Core concepts:
// Fragment = data component (position, health, etc.)
// Tag = marker (no data)
// Processor = system that operates on fragments
```

### Substrate migration
Substrate replaces the traditional material model with a layered approach.
Opt-in: `Project Settings → Rendering → Substrate`
Old materials auto-convert but may need manual adjustment.

---

## UE5.4 (April 2024)

### What's new
- **Nanite for Skeletal Meshes** — stable (no morph targets yet)
- **Motion Matching** — production-ready locomotion system
- **Chaos Flesh** — soft body simulation
- **Displacement Maps** — Nanite tessellation improvements
- **Shader execution reordering** — significant GPU performance improvement
- **Low Latency Mode** — reduced input latency for competitive games
- **PCG improvements** — runtime generation, better performance

### Motion Matching setup
```
1. Create PoseSearch Database asset
2. Populate with animation sequences
3. Add MotionMatchingComponent to character
4. Configure chooser tables for transitions
```

### Nanite Skeletal Mesh limitations in 5.4
- No morph targets
- No cloth simulation
- No vertex animation
- Static poses only (cinematic use cases)

---

## UE5.5 (November 2024)

### What's new
- **Morph targets on Nanite Skeletal Meshes** — major addition
- **Megafusion** — Niagara + PCG integration
- **OCIO (OpenColorIO)** — color management for film pipelines
- **Lumen improvements** — better indoor performance
- **Chaos Visual Debugger** — improved physics debugging
- **Blueprint diff improvements** — better source control integration
- **Audio improvements** — MetaSounds stability

### Nanite Skeletal Mesh — now supports
- Morph targets ✓
- Still no cloth simulation
- Still no vertex animation shaders

---

## VERSION-SPECIFIC ISSUE LOOKUP

### "Enhanced Input not working"
- UE5.0 → Legacy input, Enhanced Input available but not default
- UE5.1+ → Enhanced Input recommended, check Project Settings migration
- UE5.2+ → Legacy input shows more warnings

### "Nanite mesh not rendering correctly"
- UE5.0-5.2 → Skeletal meshes not supported at all
- UE5.3 → Skeletal meshes experimental, no morphs
- UE5.4 → Skeletal meshes stable, no morphs
- UE5.5+ → Morph targets supported

### "PCG not available"
- UE5.0-5.1 → Not available
- UE5.2+ → Available, add PCG module to Build.cs

### "Mass Entity crashes"
- UE5.0-5.2 → Experimental, expect instability
- UE5.3+ → Stable for production use

### "Substrate material issues"
- UE5.0 → Not available
- UE5.1-5.2 → Experimental, opt-in
- UE5.3+ → Production ready, opt-in

---

## UPGRADE MIGRATION CHECKLIST

### Upgrading to UE5.1
- [ ] Migrate Input system to Enhanced Input
- [ ] Check deprecated Blueprint nodes
- [ ] Recompile all C++ with new toolchain

### Upgrading to UE5.2
- [ ] Add PCG module if using procedural content
- [ ] Check Chaos vehicle configurations
- [ ] Test Nanite meshes for visual differences

### Upgrading to UE5.3
- [ ] Evaluate Substrate for new materials
- [ ] Consider Mass Entity for crowd systems
- [ ] Update Virtual Shadow Map settings

### Upgrading to UE5.4
- [ ] Test Motion Matching if using locomotion
- [ ] Evaluate Nanite for skeletal meshes (static poses)
- [ ] Check shader compilation times (may increase)

### Upgrading to UE5.5
- [ ] Re-evaluate Nanite skeletal meshes (morph support now available)
- [ ] Update Niagara systems if using PCG integration
- [ ] Check OCIO settings for film pipelines
