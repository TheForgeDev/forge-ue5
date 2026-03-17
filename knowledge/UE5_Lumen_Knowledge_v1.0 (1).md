# UE5 Lumen — Deep Dive Knowledge File
### UE5 Dev Agent — Knowledge v1.0

---

## WHAT IS LUMEN

Lumen is UE5's fully dynamic global illumination and reflections system. It replaces baked lighting workflows and enables real-time indirect lighting without precomputed lightmaps.

Two implementation modes:
- **Hardware Lumen** — uses ray tracing (RTX / equivalent GPU required)
- **Software Lumen** — runs on any modern GPU, uses screen-space and SDF tracing

---

## HARDWARE vs SOFTWARE LUMEN

### Hardware Lumen
**Requirements:**
- GPU with hardware ray tracing support (NVIDIA RTX, AMD RX 6000+)
- DX12 / Vulkan
- UE5 project with ray tracing enabled

**Advantages:**
- More accurate indirect lighting
- Better reflections in off-screen geometry
- Higher quality at same performance budget

**Enable:**
```
Project Settings → Rendering → Hardware Ray Tracing → Enable
r.RayTracing 1
```

### Software Lumen
**Requirements:**
- Any modern GPU (DX11 compatible)
- No special hardware

**Advantages:**
- Broad hardware compatibility
- Good enough for most games
- Lower VRAM usage

**Enable:**
```
Project Settings → Rendering → Global Illumination → Lumen
r.RayTracing 0  (force software)
```

---

## CONSOLE VARIABLES — COMPLETE LIST

### Global Controls
```
r.Lumen.DiffuseIndirect.Allow 1          // Enable/disable Lumen GI
r.Lumen.Reflections.Allow 1              // Enable/disable Lumen reflections
r.RayTracing.ForceAllRayTracingEffects 0 // Force software mode
```

### Quality
```
r.Lumen.DiffuseIndirect.RayCount 4         // Rays per pixel (higher = better quality, lower performance)
r.Lumen.Reflections.RayCount 1             // Reflection rays per pixel
r.Lumen.DiffuseIndirect.DenoisingMethod 1  // 0=off, 1=temporal, 2=spatial
r.Lumen.TemporalFilter 1                   // Temporal accumulation (reduces noise)
```

### Performance
```
r.Lumen.DiffuseIndirect.CardUpdateFrequency 1  // How often surface cache updates (lower = faster)
r.Lumen.TraceMeshSDFs 1                        // SDF tracing for small objects
r.Lumen.MaxTraceDistance 2000                  // Max trace distance (reduce for performance)
r.Lumen.Scene.CardCaptureRefreshFraction 0.125 // Fraction of cards refreshed per frame
```

### Debugging
```
r.Lumen.Visualize.Overview 1     // Visualize Lumen internals
r.Lumen.Visualize.CardPlacement  // Show surface card placement
r.Lumen.Visualize.Radiosity      // Show radiosity solution
```

---

## COMMON ISSUES AND FIXES

---

### Issue: Lighting not updating / stuck on old light

**Cause:**
Static or Stationary lights don't work with Lumen. Lumen requires Movable lights.

**Fix:**
Set all lights to **Movable** in their transform settings.

```
Light Actor → Transform → Mobility → Movable
```

---

### Issue: Dark areas / light not bouncing correctly

**Cause 1:** MaxTraceDistance too low — light rays not reaching far geometry.
```
r.Lumen.MaxTraceDistance 10000
```

**Cause 2:** Mesh doesn't have Lumen surface cards generated.
Check: Does the mesh show in `r.Lumen.Visualize.CardPlacement`?

**Cause 3:** Material uses Unlit shading model — Lumen ignores unlit surfaces.

---

### Issue: Flickering / noise in dark areas

**Cause:**
Low ray count combined with fast camera movement.

**Fix:**
```
r.Lumen.DiffuseIndirect.RayCount 8        // Increase ray count
r.Lumen.TemporalFilter 1                  // Enable temporal filter
r.Lumen.DiffuseIndirect.DenoisingMethod 1 // Enable denoising
```

---

### Issue: Reflections showing wrong / outdated content

**Cause 1:** Off-screen geometry — Software Lumen can't reflect what's not on screen.
Hardware Lumen handles this better.

**Cause 2:** Reflection capture actors overriding Lumen.
Remove or disable Sphere/Box Reflection Captures if using Lumen reflections.

**Cause 3:** Screen Space Reflections (SSR) conflicting.
```
r.SSR.Quality 0  // Disable SSR, let Lumen handle reflections
```

---

### Issue: Lumen not working on certain meshes

**Cause:**
Lumen generates surface cards for Static Meshes. Meshes must meet requirements:

- Must be **Static Mesh** (not Skeletal)
- Must have valid lightmap UVs OR Nanite enabled
- Must not be too small (below minimum card size threshold)

**Check card generation:**
```
r.Lumen.Visualize.CardPlacement 1
```
If no cards visible on mesh → Lumen won't affect it.

**Force card generation on small mesh:**
```
Static Mesh Editor → Build Settings → Min Lightmap Resolution → lower value
```

---

### Issue: Performance drop after enabling Lumen

**Diagnosis steps:**

1. Check GPU time in `stat GPU`
2. Identify which Lumen pass is expensive:
   - `Lumen.DiffuseIndirect` — GI cost
   - `Lumen.Reflections` — Reflection cost
   - `Lumen.SceneUpdate` — Scene card update cost

**Quick performance wins:**
```
r.Lumen.MaxTraceDistance 1000              // Reduce trace distance
r.Lumen.DiffuseIndirect.RayCount 2         // Reduce rays
r.Lumen.Scene.CardCaptureRefreshFraction 0.05  // Update cards less frequently
r.Lumen.TraceMeshSDFs 0                    // Disable SDF tracing for small objects
```

**Platform-specific:**
For consoles / lower-end PC: use Software Lumen with reduced settings.
For high-end PC / next-gen: Hardware Lumen with full settings.

---

### Issue: Indoor lighting looks wrong / too bright or too dark

**Cause:**
Lumen sky light is leaking through geometry that's too thin.

**Fix:**
- Ensure walls have sufficient thickness (minimum ~10cm)
- Use `Extend Sky Light Occlusion` on the Sky Light actor
- Check for gaps in geometry

---

### Issue: Lumen not working in packaged build

**Cause:**
Shader compilation settings or platform settings may disable ray tracing in shipping.

**Fix:**
```
Project Settings → Platforms → [Your Platform] → 
Enable Ray Tracing in Shipping builds
```

Also verify:
```
DefaultEngine.ini:
[/Script/Engine.RendererSettings]
r.RayTracing=1
```

---

## LUMEN WITH NANITE

Lumen and Nanite are designed to work together. Best practices:

- Enable Nanite on high-poly meshes → Lumen card generation improves
- Nanite meshes get higher quality Lumen surface cards
- Don't use Nanite on foliage with wind animation (causes Lumen flickering)

---

## LUMEN PERFORMANCE TARGETS

| Quality Preset | Ray Count | Max Distance | Target Use |
|---|---|---|---|
| Low | 1 | 500 | Mobile / Low-end |
| Medium | 2 | 1000 | Console / Mid PC |
| High | 4 | 2000 | High-end PC |
| Epic | 8 | 5000 | Cinematic |

---

## SKYLIGHT AND LUMEN

Lumen relies heavily on the Sky Light for exterior scenes.

```
Sky Light:
- Mobility: Movable (required)
- Real Time Capture: Enabled (for dynamic skies)
- Intensity: 1.0 (start here, adjust)
- Indirect Lighting Intensity: 1.0
```

Without a properly configured Sky Light, Lumen interiors will be completely dark.

---

## LUMEN IN DIFFERENT SCENARIOS

### Open World
- Increase MaxTraceDistance to 5000+
- Use Hardware Lumen if available
- Enable World Partition streaming — Lumen handles it automatically

### Interior Scenes
- Reduce MaxTraceDistance to 500-1000
- Ensure wall thickness > 10cm
- Place point/spot lights as Movable

### Caves / Underground
- Sky light won't reach — use emissive materials or point lights
- Emissive mesh surfaces work as light sources with Lumen

### Night Scenes
- Lumen works with artificial lights
- Ensure all lights are Movable
- May need higher ray count for accurate dark-scene GI
