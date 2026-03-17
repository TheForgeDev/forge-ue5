# UE5 Animation — IK Retargeter & Motion Matching Knowledge Guide v1.0

## 1. IK RETARGETER — CORE CONCEPTS

### 1.1 Required Assets
```
Source Skeleton  →  IK Rig (Source)  ─┐
                                       ├→  IK Retargeter  →  Retargeted animation
Target Skeleton  →  IK Rig (Target)  ─┘
```

### 1.2 IK Rig Setup Steps
1. Right-click the source skeleton → **Create → IK Rig**
2. Open IK Rig → **Add Retarget Root**: usually `pelvis` or `root`
3. **Add IK Goal**: for each chain (left hand, right hand, left foot, right foot)
4. **Add Retarget Chain**: define a chain for each IK goal (spine, left_arm, right_leg, etc.)
5. Repeat the same steps for the target skeleton

### 1.3 IK Retargeter Setup
1. **Create → IK Retargeter** → assign Source + Target IK Rig
2. **Chain Mapping**: map source chains → target chains
3. Check the animation in Preview
4. **Export Selected Animations** → produce new animation assets

---

## 2. IK RETARGETER — COMMON ERRORS AND FIXES

### ERROR-IK01: Animation is completely static after export — only head moves or nothing moves at all
**Cause (UE 5.5.x known bug):** Retarget data isn't being bound to the animation asset during export.
**Fix:**
1. **Save, close, and reopen the Retargeter** before exporting
2. If the animation looks correct in the Preview panel, try exporting again
3. Try redirecting the export destination to a different folder
4. Update UE version (known issue in 5.5.4, fixed in 5.5.5+ patch)

### ERROR-IK02: No root motion — character running in place
**Cause:** Root bone chain mapping is missing, or wrong bone assigned as "Retarget Root".
**Fix:**
- In IK Rig, select the `root` bone as **Retarget Root** (not pelvis)
- Explicitly map the Root bone chain in the IK Retargeter
- Check if "Enable Root Motion" is active in the animation asset
- If from Mixamo: Mixamo's root bone is `Hips` — rename it to `root` or map `Hips` → `root` in chain mapping

### ERROR-IK03: Character floating above / sinking into the ground
**Cause:** Source and target skeleton heights differ, scale hasn't been adjusted.
**Fix:**
- IK Retargeter → **Preview Settings → Target Mesh Scale** (e.g. 1.05)
- In Retarget Chains, try **Translation Mode**:
  - `Global Scaled` for spine chain
  - `Global` for root

### ERROR-IK04: Hand or foot positions are wrong — reverting to T-pose
**Cause:** A-pose and T-pose mismatch; source is in A-pose, target is in T-pose.
**Fix:**
- Edit **Retarget Pose** in IK Rigs
- Bring both skeletons to the same reference pose (A or T)
- Use **Rotation Offset** in the chain (e.g. right thigh: +2.5° correction)

### ERROR-IK05: IK bone data not being transferred
**Cause:** IK bones (like ik_hand_l) weren't included in a Retarget Chain.
**Fix:**
- Don't create separate chains for each IK bone — they're usually tied to the FK system
- IK goals are derived from FK chains; don't add IK bones directly to chains
- Only define chains for FK bones — IK is solved automatically

### ERROR-IK06: Retargeting with multiple skeletons — some animations look different
**Cause:** Each animation may have a different source pose.
**Fix:** Create a separate IK Retargeter for each source skeleton type; don't mix different providers in a single retargeter.

---

## 3. MOTION MATCHING — BASIC SETUP (UE 5.4+)

### 3.1 Requirements
- Plugin: **Pose Search** (built-in in 5.4+, experimental in 5.3)
- Animation set: root motion active, enough variety (walk/run/turn/stop)

### 3.2 Setup Steps

**Step 1: Pose Search Schema**
```
Content Browser → Create → Animation → Pose Search → Pose Search Schema
```
In Schema:
- Assign skeleton
- Add channel: `UPoseSearchFeatureChannel_Trajectory` (future + past pose)
- Add channel: `UPoseSearchFeatureChannel_Pose` (reference bones: pelvis, feet, hands)

**Step 2: Pose Search Database**
```
Create → Animation → Pose Search → Pose Search Database
```
- Assign Schema
- Add animation assets
- Press **Build** — index is created

**Step 3: Integration into Animation Blueprint**
```
AnimGraph → Add Motion Matching node
```
- Connect Database
- Feed trajectory input from Character Movement Component

**Step 4: Trajectory Generation (C++)**
```cpp
#include "PoseSearch/MotionMatchingAnimNodeLibrary.h"
#include "PoseSearch/PoseSearchTrajectoryTypes.h"

// Trajectory from CharacterMovementComponent
FPoseSearchQueryTrajectory Trajectory;
UMotionMatchingAnimNodeLibrary::GetTrajectory(
    GetMesh()->GetAnimInstance(), Trajectory);
```

---

## 4. MOTION MATCHING — COMMON ERRORS

### ERROR-MM01: Pose Search Database empty — no animations visible in preview
**Cause:** Root motion not enabled, or Build wasn't run after adding animations to the DB.
**Fix:**
1. For each animation: **Asset Details → Root Motion → Force Root Lock: false**, **EnableRootMotion: true**
2. Add animations while the Database is open, then press **Build**
3. Make sure animations are long enough when a trajectory channel is in the Schema (at least 0.5s)

### ERROR-MM02: Character teleporting / popping during transitions
**Cause:** No similar poses in the Database — MM can't find the nearest pose.
**Fix:**
- Expand the animation dataset: more idle variations, turn animations
- Increase `Blend Time` (0.2 → 0.4s)
- Increase `History Trajectory Sample Count` in Schema

### ERROR-MM03: Motion Matching not working in UE 5.4 with custom skeleton
**Cause:** Retargeted animations aren't fully compatible with Pose Search Schema.
**Fix:**
- Retarget animations to UE5 Mannequin skeleton
- Add the retargeted animations to the Database (not the originals)
- Reference bones in Schema must match the target skeleton

### ERROR-MM04: `Motion Matching` node not visible in AnimGraph
**Cause:** Pose Search plugin not enabled.
**Fix:** Edit → Plugins → "Pose Search" → Enable → Restart

---

## 5. IK — FULL BODY IK (FBIK) C++ INTEGRATION

### 5.1 Runtime IK Setup
```cpp
// Control Full Body IK from C++ through AnimInstance
void AMyCharacter::UpdateFootIK(float DeltaTime)
{
    UAnimInstance* AnimInst = GetMesh()->GetAnimInstance();
    if (!AnimInst) return;

    // Find ground with LineTrace
    FHitResult HitResult;
    FVector TraceStart = GetMesh()->GetBoneLocation(TEXT("foot_l")) + FVector(0, 0, 50);
    FVector TraceEnd = TraceStart - FVector(0, 0, 150);

    if (GetWorld()->LineTraceSingleByChannel(HitResult, TraceStart, TraceEnd, ECC_Visibility))
    {
        LeftFootTargetLocation = HitResult.Location;
        LeftFootTargetNormal = HitResult.Normal;
    }
}
```

### 5.2 Passing Values to AnimBP
```cpp
// In AnimInstance subclass
UPROPERTY(BlueprintReadWrite, Category=IK)
FVector LeftFootIKLocation;

UPROPERTY(BlueprintReadWrite, Category=IK)
FVector RightFootIKLocation;

// Set from Character
UMyAnimInstance* AnimInst = Cast<UMyAnimInstance>(GetMesh()->GetAnimInstance());
if (AnimInst)
{
    AnimInst->LeftFootIKLocation = LeftFootTargetLocation;
}
```

---

## 6. CONTROL RIG & IK RETARGETER C++ RUNTIME USAGE

### 6.1 Runtime Retarget (UE 5.2+)
```cpp
#include "Retargeter/IKRetargeter.h"
#include "RetargetingManager.h" // if available

// Runtime retarget is usually done through BP
// In C++ with UIKRetargetProcessor:
UIKRetargetProcessor* Processor = NewObject<UIKRetargetProcessor>();
Processor->Initialize(SourceSkeleton, TargetSkeleton, RetargeterAsset, TargetMeshComp);

// Each frame
Processor->RunRetargeter(SourcePose, TargetPose);
```

**Note:** Runtime retarget is expensive. Export animations offline whenever possible.

---

## 7. ANIMATION DEBUG TOOLS

```
// General animation debug
ShowDebug Animation

// Pose Search debug (Motion Matching)
a.PoseSearch.Debug 1
a.PoseSearch.DrawSearchIndex 1

// IK debug
p.IK.Debug 1

// Foot placement debug
a.AnimNode.FootPlacement.Debug 1
```

Query animation state from C++:
```cpp
UAnimInstance* Anim = GetMesh()->GetAnimInstance();
FAnimInstanceProxy& Proxy = Anim->GetProxyOnAnyThread<FAnimInstanceProxy>();

// Active state machine state
FName CurrentState = Anim->GetCurrentStateName(0); // 0 = first state machine
```

---

## 8. MIXAMO-SPECIFIC NOTES

Mixamo → UE5 retarget is a very common workflow. Known issues:
- No root bone → download "In Place" animation from Mixamo or add a root bone
- T-pose mismatch → fix Retarget Pose in IK Rig
- Shoulder rotation drift → set rotation offset in the Clavicle chain
- Finger chain too long → map Finger chains individually or skip them

---

## 9. AGENT RULES

- Static animation after retarget → ERROR-IK01 (UE 5.5.x export bug)
- Root motion not working → check Retarget Root bone + Enable Root Motion (ERROR-IK02)
- Floating above / sinking below ground → Target Mesh Scale + Translation Mode (ERROR-IK03)
- T-pose drift → Retarget Pose editing + Rotation Offset (ERROR-IK04)
- MM Database empty → check root motion + Build step (ERROR-MM01)
- MM pop/teleport → expand animation dataset + Blend Time (ERROR-MM02)
- MM node missing → is Pose Search plugin enabled? (ERROR-MM04)
- Mixamo issues → use the Mixamo-specific notes section above
