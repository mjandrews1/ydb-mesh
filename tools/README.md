# ydb-mesh M libraries (tools/)

Classic M data-structure libraries over globals. Portable ISO M (no `$Z*`
intrinsics); safe to `DO` from loaders/REPL on YottaDB or RSM.

See project rule: classic structures belong in **M over globals**, not engine
code. Hash is a portable 31-bit rolling hash (not `$ZHASH`).

## Libraries

| Routine | ADT | Global | Smoke |
|---------|-----|--------|-------|
| `HMAP.m` | hash map (separate chaining) | `^HM` | `HMAPRUN.m` |
| `HSTACK.m` | LIFO stack | `^HSTK` | `HSTKRUN.m` |
| `HQUEUE.m` | FIFO queue (monotonic slots) | `^HQUE` | — |
| `HHEAP.m` | binary min-heap | `^HHEAP` | — |
| `HPQUE.m` | min-priority queue (FIFO ties) | `^HPQ` | — |

All names are **string** map/stack/queue keys (logical instance id), so one
global can hold many independent structures.

---

### HMAP — hash map

**Schema** (per map `name`):
- `^HM(name,0)` insert count
- `^HM(name,1,bucket)` chain length
- `^HM(name,2,key)` value
- `^HM(name,3,bucket,key)` = 1 chain membership
- `^HM(name,4)` optional bucket count (default 1024)

**API**
```m
D PUT^HMAP(name,key,val)      ; insert / overwrite
S ok=$$GET^HMAP(name,key,.v)  ; 1/0 + value
D GETV^HMAP(name,key,.v)      ; DO-style lookup
D DEL^HMAP(name,key)          ; no-op if absent
D CLEAR^HMAP(name)
S b=$$BUCKET^HMAP(key,nb)     ; 0..nb-1
S h=$$HASH^HMAP(key)          ; 31-bit hash
```

### HSTACK — LIFO stack

**Schema:** `^HSTK(name,0)` = top index · `^HSTK(name,1,n)` = value (1 = bottom)

```m
D PUSH^HSTACK(name,val)
S ok=$$POP^HSTACK(name,.val)
S ok=$$PEEK^HSTACK(name,.val)
S d=$$DEPTH^HSTACK(name)
D CLEAR^HSTACK(name)
```

### HQUEUE — FIFO queue

**Schema:** `^HQUE(name,0)` count · `(1)` head · `(2)` tail · `^HQUE(name,3,i)` slots  
Slots advance monotonically (no wrap); `CLEAR` resets. Fine for long-lived service queues.

```m
D ENQ^HQUEUE(name,val)
S ok=$$DEQ^HQUEUE(name,.val)
S ok=$$FRONT^HQUEUE(name,.val)
S n=$$QCOUNT^HQUEUE(name)
D CLEAR^HQUEUE(name)
```

### HHEAP — binary min-heap

**Schema:** `^HHEAP(name,0)` = n · `(1,i)` key · `(2,i)` payload  
Parent key ≤ child (numeric strings compared numerically; else string order).

```m
D PUSH^HHEAP(name,key,payload)
S ok=$$POP^HHEAP(name,.key,.payload)   ; extract-min
S ok=$$PEEK^HHEAP(name,.key,.payload)
S n=$$HHEAPN^HHEAP(name)
D CLEAR^HHEAP(name)
```

### HPQUE — min-priority queue

Same tree as HHEAP plus tie-break sequence (`^HPQ(name,3,i)`); equal priorities
served **FIFO**.

```m
D ENQ^HPQUE(name,priority,payload)
S ok=$$DEQ^HPQUE(name,.priority,.payload)
S ok=$$TOP^HPQUE(name,.priority,.payload)
S n=$$QLEN^HPQUE(name)
D CLEAR^HPQUE(name)
```

---

## Smoke runners

```text
HMAPRUN.m   — insert/lookup/delete + collision cases
HSTKRUN.m   — push/pop/peek order
```

Load onto a YottaDB region and `D RUN` (or tag in the runner). Keep smokes on
a **test** map name (`TESTMAP`, …) so they do not touch production globals.

## Notes

- Values are text; numeric strings are not coerced on store.
- Do not mix `^HM` / `^HSTK` / `^HQUE` / `^HHEAP` / `^HPQ` with unrelated keys
  that share those globals without a `name` prefix.
- Cleanup: `D CLEAR^<LIB>(name)` per instance; delete the root only when the
  whole library namespace is disposable.
