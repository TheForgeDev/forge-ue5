# UE5 Multithreading & Performance — Knowledge File
### UE5 Dev Agent — Knowledge v1.0
### Source: Community documentation (condensed)

---

## PART 1: MULTITHREADING

---

## OVERVIEW

UE5 supports multithreading but uses it partially by default.

Dedicated threads exist for: audio, rendering, stats.
Most operations including Tick and Blueprints run on the **game thread**.
Expensive calculations on game thread = framerate loss.

**Two major approaches:**

**Runnables** — Dedicated newly created threads. Full control. Good for large, continuous computations.

**Tasks (TaskGraph)** — Job manager balancing work across existing threads. Good for small, discrete operations. Lower overhead than creating new threads.

---

## THREADING CLASSES

---

### FRunnable — Full Control Thread

```cpp
// .h
#pragma once
#include "CoreMinimal.h"

class FMyThread : public FRunnable
{
    FRunnableThread* Thread;
    bool bShutdown = false;

public:
    FMyThread(/* parameters */)
    {
        Thread = FRunnableThread::Create(this, TEXT("MyThread"));
    }

    virtual bool Init() override;   // Runs on game thread — return true to start
    virtual uint32 Run() override;  // Runs on new thread — main work here
    virtual void Exit() override;   // Runs on new thread after Run() completes
    virtual void Stop() override;   // Called from game thread to stop early
};

// .cpp
bool FMyThread::Init() { return true; }

uint32 FMyThread::Run()
{
    while (!bShutdown)
    {
        /* threaded work */
    }
    return 0;
}

void FMyThread::Stop() { bShutdown = true; }
```

**Start the thread:**
```cpp
auto* Thread = new FMyThread(/* parameters */);
```

**Stop the thread:**
```cpp
Thread->Kill();        // controlled stop — calls Stop()
Thread->Kill(false);   // force terminate
Thread->WaitForCompletion(); // stall caller until thread finishes
```

---

### AsyncTask — Quick Lambda on TaskGraph

No dedicated class needed. For small async operations.

```cpp
AsyncTask(ENamedThreads::AnyHiPriThreadNormalTask, [this]()
{
    /* work on TaskGraph */
});

// Run something back on game thread from a thread:
AsyncTask(ENamedThreads::GameThread, [this]()
{
    /* safe to update UObjects here */
});
```

**Important:** Variables outside the lambda must be captured.
- `[this]` — captures class instance
- `[&]` — captures local variables by reference
- `[=]` — captures by copy (safer for threading)

---

### ParallelFor — Parallel Loop

Splits a for loop across multiple TaskGraph threads.

```cpp
ParallelFor(Array.Num(), [&](int32 i)
{
    /* work — order of execution NOT guaranteed */
    ++Array[i];
});
```

**Warning:** No guarantee on execution order or thread safety.
Use mutexes or atomics if threads write to shared data.

---

### FNonAbandonableTask — Reusable Task Class

```cpp
class FMyTask : public FNonAbandonableTask
{
    friend class FAutoDeleteAsyncTask<FMyTask>;

    FMyTask(/* parameters */) { /* constructor */ }

    void DoWork()
    {
        /* work on TaskGraph */
    }

    FORCEINLINE TStatId GetStatId() const
    {
        RETURN_QUICK_DECLARE_CYCLE_STAT(FMyTask, STATGROUP_ThreadPoolAsyncTasks);
    }
};

// Start:
auto* MyTask = new FAsyncTask<FMyTask>(/* parameters */);
MyTask->StartBackgroundTask();
```

---

## THREAD SAFETY

### The Core Rule

**Reading** from a shared variable = generally thread safe.
**Writing** to a shared variable from multiple threads = data race = crash.

**Never write to UObjects or AActors from a non-game thread.**
Do computation in thread → write results back on game thread via AsyncTask.

---

### Thread Safety Tools

**std::atomic — Atomic Variables**
```cpp
std::atomic<int> Counter;
std::atomic<bool> bReady;

Counter.fetch_add(1);  // thread-safe increment
```
Use `std::atomic`, not Unreal's deprecated `TAtomics`.
Cannot wrap containers like TArray — only simple types.

---

**FCriticalSection — Mutex**
```cpp
FCriticalSection Section;

uint32 FMyThread::Run()
{
    Section.Lock();
    /* thread-safe section */
    Section.Unlock();
    return 0;
}
```

**FScopeLock — Auto-releasing Mutex (preferred)**
```cpp
FCriticalSection Section;

uint32 FMyThread::Run()
{
    {
        FScopeLock Lock(&Section);
        /* thread-safe until closing brace */
    }
    return 0;
}
```

---

**TQueue — Thread-Safe Queue**
```cpp
TQueue<int> Queue; // SPSC mode (single producer, single consumer)
TQueue<int, EQueueMode::Mpsc> Queue; // MPSC mode (multi producer)

Queue.Enqueue(Value);  // add to queue
int Out;
Queue.Dequeue(Out);    // remove from queue
```

Best pattern: one thread enqueues, one thread dequeues.

---

**FPlatformAtomics — Atomic Operations Without Atomic Type**
```cpp
FPlatformAtomics::InterlockedAdd(&MyInt, 10);
FPlatformAtomics::InterlockedIncrement(&MyInt);
```

Built-in atomic classes: `FThreadSafeBool`, `FThreadSafeCounter`.

---

### Pausing Threads

**Sleep:**
```cpp
FPlatformProcess::Sleep(0.01f); // seconds

// Sleep until condition:
bool bResume = false;
FPlatformProcess::ConditionalSleep([this]() -> bool
{
    return bResume;
});
```

**FScopedEvent — Sleep until another thread triggers:**
```cpp
{
    FScopedEvent Event;
    DoThreadedWork(Event.Get()); // pass pointer to other thread
    /* sleeps here until other thread calls Event.Trigger() */
}
```

---

### Callbacks from Threads

**Option 1 — Direct call (runs in the thread, be careful):**
```cpp
uint32 FMyThread::Run()
{
    /* work */
    Actor->ThreadCallback(); // runs in thread, not game thread
    return 0;
}
```

**Option 2 — AsyncTask back to game thread (recommended):**
```cpp
uint32 FMyThread::Run()
{
    /* work */
    FVector Result = ComputeSomething();

    AsyncTask(ENamedThreads::GameThread, [this, Result]()
    {
        Actor->ThreadCallback(Result); // safe — runs on game thread
    });
    return 0;
}
```

---

## PART 2: PERFORMANCE

---

## CONTAINERS

### TArray — When to Use What

```cpp
// SLOW — scans entire array each call:
Array.AddUnique(Item);  // O(n)
Array.Remove(Item);     // O(n)
Array.Contains(Item);   // O(n)

// FASTER alternatives:
Array.RemoveSingle(Item);         // stops at first match
Array.RemoveSwap(Item);           // O(1) but doesn't preserve order
Array.RemoveAtSwap(Index);        // same, by index
```

**Reserve memory upfront to avoid reallocation:**
```cpp
TArray<int> Array;
Array.Reserve(1024); // no reallocation until 1024 elements exceeded

for (int i = 0; i < 1024; ++i)
{
    Array.Add(i);
}
```

**Reuse containers — Reset() instead of Empty():**
```cpp
Array.Empty();  // deallocates memory
Array.Reset();  // keeps memory allocated, just sets size to 0 — faster
```

---

### TSet — Use When Order Doesn't Matter

TSet has **constant time O(1)** for Add, Remove, Find.
TArray has **linear time O(n)** for the same operations.

```cpp
TSet<int> Set;
Set.Add(5);           // O(1)
Set.Remove(5);        // O(1)
bool b = Set.Contains(5); // O(1)
```

Use TSet when you frequently check if items exist.
Checking a TArray against a TSet is faster than TArray vs TArray.

---

### TMap — Key-Value with Constant Time

```cpp
TMap<FString, float> Stats;
Stats.Add("Health", 100.f);   // O(1)
Stats.Remove("Health");        // O(1)
float* Val = Stats.Find("Health"); // O(1) — returns pointer, nullptr if not found
```

---

### MoveTemp — Avoid Expensive Copies

```cpp
// Moving entire containers:
TArray<int> NewArray = MoveTemp(OldArray); // OldArray becomes empty
NewArray.Append(MoveTemp(OtherArray));     // no copy

// Moving individual elements:
NewArray.Add(MoveTemp(BigStruct));
Queue.Enqueue(MoveTemp(BigStruct));

// Moving out:
int i = Array.Find(Elem);
auto Out = MoveTemp(Array[i]);
Array.RemoveAt(i);

// Or use built-in move functions:
auto Out = Array.Pop();               // removes and returns last element
Queue.Dequeue(Out);                   // moves into Out
Map.RemoveAndCopyValue(Key, Out);     // moves value into Out
```

---

## LOOPS

### Avoid Expensive Operations Inside Loops

```cpp
// WRONG — GetAllActorsOfClass is O(n), called every frame:
void AMyActor::Tick(float DeltaTime)
{
    TArray<AActor*> Actors;
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AEnemy::StaticClass(), Actors);
    // ...
}

// RIGHT — cache result, don't repeat expensive calls:
TArray<AActor*> CachedEnemies; // member variable

void AMyActor::BeginPlay()
{
    UGameplayStatics::GetAllActorsOfClass(GetWorld(), AEnemy::StaticClass(), CachedEnemies);
}
```

---

### Move Conditionals Outside Inner Loops

```cpp
// SLOW — condition checked 32768 times:
for (int x = 0; x < 32; ++x)
    for (int y = 0; y < 32; ++y)
        for (int z = 0; z < 32; ++z)
            if (bMyTest) { /* code */ }

// FAST — condition checked 1024 times:
for (int x = 0; x < 32; ++x)
{
    for (int y = 0; y < 32; ++y)
    {
        if (bMyTest)
        {
            for (int z = 0; z < 32; ++z) { /* code */ }
        }
        else
        {
            for (int z = 0; z < 32; ++z) { /* code */ }
        }
    }
}
```

---

### Precalculate — Don't Repeat Calculations

```cpp
// WRONG — same calculations done twice:
if (Array[GetID(x+1, y+1, z+1)] == 0)
    Array[GetID(x+1, y+1, z+1)] += 10;

// RIGHT — calculate once, reuse:
const int x1 = x+1, y1 = y+1, z1 = z+1;
auto* Element = &Array[GetID(x1, y1, z1)];
if (*Element == 0)
    *Element += 10;
```

---

### Fastest Array Access Pattern

```cpp
// Slowest — range-based for (has bounds checking overhead):
for (auto& i : Array) { i += 10; }

// Fastest — raw pointer:
auto* p = Array.GetData();
for (int i = 0; i < Array.Num(); ++i)
{
    *p += 10;
    ++p;
}
```

---

## TICK OPTIMIZATION

```cpp
// Disable Tick when not needed:
AMyActor::AMyActor()
{
    PrimaryActorTick.bCanEverTick = false;
}

// Reduce tick frequency:
PrimaryActorTick.TickInterval = 0.1f; // every 100ms instead of every frame
```

**Rule:** Never do O(n) operations (Find, Contains, GetAllActors) inside Tick.

---

## INLINING

Functions defined in .cpp cannot be optimized as aggressively by compiler.
Move small, frequently called functions to .h with `inline` or `FORCEINLINE`:

```cpp
// .h — compiler copies code in place, enables full optimization:
FORCEINLINE int GetID(int x, int y, int z) const
{
    return x * SizeY * SizeZ + y * SizeZ + z;
}
```

Use FORCEINLINE only for small functions called in hot paths (tight loops).

---

## ACTOR & COMPONENT SPAWNING

Spawning Actors is expensive — hundreds of milliseconds with 1000+ actors.
Cannot be multithreaded.

**Best practices:**
- Use object pooling for frequently spawned/destroyed actors (projectiles, effects)
- Prefer one Actor with multiple Components over many Actors
- Prefer C++ spawning over Blueprint spawning (slightly faster)
- ChildActors are more expensive than regular Actors — avoid when possible

---

## MEMORY — UPROPERTY PERFORMANCE NOTE

Large containers marked as `UPROPERTY(EditAnywhere)` can cause editor performance issues.
If you notice editor slowdown with big TArrays/TMaps, consider:
- Removing `EditAnywhere` if designer access isn't needed
- Using `VisibleAnywhere` instead (read-only in editor)
- Splitting into smaller containers
