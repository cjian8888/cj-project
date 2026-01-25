---
name: python-pandas-performance
description: Use when writing or refactoring Python Pandas code, especially for large datasets or performance-critical paths to prevent memory issues and improve speed.
---

# Python Pandas Performance Specialist

## Overview
Optimizes Pandas code for memory efficiency and execution speed. Prevents common pitfalls like loop iteration, incorrect types, and memory leaks.

## When to Use
- Processing large datasets (e.g., transaction logs, bank flows).
- Encountering "MemoryError" or slow execution.
- Refactoring `apply` functions or loops over DataFrames.
- Defining data types for new DataFrames.

## Core Rules

### 1. Vectorization over Iteration
**STOP**: Never use `for` loops or `iterrows()` for calculation.
**USE**: Vectorized operations or `numpy` functions.

```python
# ❌ BAD
for idx, row in df.iterrows():
    df.at[idx, 'total'] = row['price'] * row['qty']

# ✅ GOOD
df['total'] = df['price'] * df['qty']
```

### 2. DataType Optimization (The "Dtype Discipline")
**STOP**: Allowing pandas to infer types (often results in `object` or `int64` where unnecessary).
**USE**: Explicit `dtype` specification or downcasting.

- **Strings**: Use `category` for low-cardinality strings (e.g., gender, status). User `string[pyarrow]` for others if available.
- **Numbers**: Use `int32`/`float32` instead of 64-bit if range permits.
- **Dates**: Ensure `datetime64[ns]`, not strings.

```python
# ✅ GOOD
df = pd.read_csv('data.csv', dtype={
    'status': 'category',
    'count': 'int32'
})
```

### 3. Chunking for Large I/O
**STOP**: Reading massive CSVs/Excels all at once (`read_csv`).
**USE**: `chunksize` iterator or processing via streaming.

```python
# ✅ GOOD
chunks = []
for chunk in pd.read_csv('massive_log.csv', chunksize=50000):
    processed = process(chunk)
    chunks.append(processed)
df = pd.concat(chunks)
```

### 4. Avoid `apply` for Simple Logic
**STOP**: `df.apply(lambda x: ...)` usually iterates in Python space.
**USE**: `np.where`, `np.select`, or pandas built-ins.

```python
# ❌ BAD
df['tag'] = df.apply(lambda x: 'High' if x['val'] > 100 else 'Low', axis=1)

# ✅ GOOD
import numpy as np
df['tag'] = np.where(df['val'] > 100, 'High', 'Low')
```

## Common Pitfalls
- **Chained Assignment**: `df[mask]['col'] = 5` (SettingWithCopyWarning). Use `df.loc[mask, 'col'] = 5`.
- **String Manipulation**: Python string methods are slow on Series. Use `.str` accessor but prefer categorical codes if possible.
