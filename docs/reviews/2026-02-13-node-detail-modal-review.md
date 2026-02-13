# Code Review: Node Detail Modal Feature

**Date:** 2026-02-13
**Reviewer:** pr-review-toolkit:code-reviewer
**Feature:** Double-click node to open detail modal across 3 visualization views

---

## Files Reviewed

**New files:**
- `frontend/src/components/project/NodeDetailModal.css`
- `frontend/src/components/project/NodeDetailModal.jsx`
- `frontend/src/components/project/nodeDetails/TableNodeDetail.jsx`
- `frontend/src/components/project/nodeDetails/FunctionNodeDetail.jsx`
- `frontend/src/components/project/nodeDetails/BlueprintNodeDetail.jsx`
- `frontend/src/components/project/nodeDetails/RouteNodeDetail.jsx`

**Modified files:**
- `frontend/src/components/project/FlowVisualization.jsx`
- `frontend/src/components/project/ApiRoutesVisualization.jsx`
- `frontend/src/components/project/ProjectVisualization.jsx`

**Reference:**
- `docs/plans/2026-02-13-node-detail-modal.md`

---

## CRITICAL Issues

### 1. `flow_type.replace('_', '/')` only replaces the first underscore (Confidence: 95)

**File:** `frontend/src/components/project/nodeDetails/FunctionNodeDetail.jsx`, line 206

```js
{cf.flow_type.replace('_', '/')}
```

JavaScript's `String.replace()` with a string argument only replaces the **first** occurrence. If a `flow_type` value contains multiple underscores (e.g., `try_except_finally`), only the first underscore is replaced, producing `try/except_finally` instead of `try/except/finally`.

**Fix:** Use a regex with the global flag:
```js
{cf.flow_type.replace(/_/g, '/')}
```

### 2. Body scroll lock can leak if both NodeDetailModal and InsightGuide are open simultaneously (Confidence: 90)

**File:** `frontend/src/components/project/NodeDetailModal.jsx`, lines 17-23

Both `NodeDetailModal` and `InsightGuide` set `document.body.style.overflow = 'hidden'` when open and reset it to `'unset'` on cleanup. If both modals are open (unlikely but possible since they are independent state), closing one will set `overflow: 'unset'` while the other is still open, re-enabling scrolling prematurely.

**Suggestion:** Use a ref-counted approach or check if any modal is still open before resetting overflow. Alternatively, since this is an existing pattern from `InsightGuide`, accept the risk and document it.

---

## IMPORTANT Issues

### 3. `FunctionNodeDetail` caller/callee filtering is overly restrictive (Confidence: 91)

**File:** `frontend/src/components/project/nodeDetails/FunctionNodeDetail.jsx`, lines 12-13

```js
const callers = calls.filter(c => c.callee_id === node.id && c.call_type === 'direct');
const callees = calls.filter(c => c.caller_id === node.id && c.call_type === 'direct');
```

Only `direct` call types are shown. The plan says to show callers/callees "with conditional/loop context" but does not restrict to `direct` only. Non-direct calls (e.g., indirect, dynamic) are silently hidden. The detail modal is the one place where showing all call types would be most valuable.

**Suggestion:** Consider removing the `c.call_type === 'direct'` filter, or display non-direct calls in a separate sub-list.

### 4. `onClose` callback is not stable -- causes unnecessary effect re-runs (Confidence: 82)

**Files:**
- `frontend/src/components/project/FlowVisualization.jsx`, line 344
- `frontend/src/components/project/ApiRoutesVisualization.jsx`, line 410
- `frontend/src/components/project/ProjectVisualization.jsx`, line 1117

All three views pass an inline arrow function to `onClose`:
```jsx
onClose={() => setDetailNode(null)}
```

This creates a new function reference every render. Inside `NodeDetailModal.jsx`, the ESC handler `useEffect` depends on `[isOpen, onClose]`, causing the effect to tear down and re-add the event listener on every parent re-render.

**Fix:** Wrap the close handler in `useCallback`:
```js
const handleDetailClose = useCallback(() => setDetailNode(null), []);
```

### 5. `handleSchemaNodeDoubleClick` uses fragile placeholder guard (Confidence: 85)

**File:** `frontend/src/components/project/ProjectVisualization.jsx`, lines 793-796

```js
if (node.type === 'stickyNote' || node.id === '1') return;
```

The guard `node.id === '1'` only skips the specific placeholder node. A more robust check:

```js
if (node.type === 'stickyNote' || !node.data?.tableName) return;
```

This ensures only nodes with actual table data will open the modal.

### 6. Sibling routes heading has hardcoded light-mode color (Confidence: 84)

**File:** `frontend/src/components/project/nodeDetails/RouteNodeDetail.jsx`, line 146

```jsx
<h4 style={{ fontSize: '12px', color: '#6b7280', marginTop: '12px', marginBottom: '8px' }}>
```

The inline `color: '#6b7280'` provides poor contrast against the dark-mode modal background (`#1f2937`). Use a CSS class with dark-mode variant instead.

**Fix:**
```jsx
<h4 className="node-detail-section-title" style={{ fontSize: '12px', marginTop: '12px', marginBottom: '8px' }}>
```

### 7. `FunctionNodeDetail` renders inconsistent caller/callee context text (Confidence: 83)

**File:** `frontend/src/components/project/nodeDetails/FunctionNodeDetail.jsx`, lines 148-151

```jsx
{c.is_conditional && 'conditional'}
{c.is_conditional && c.is_loop && ' / '}
{c.is_loop && 'in loop'}
```

When both flags are false, nothing renders (correct). But whitespace and separators are inconsistent. Better approach:

```js
const callContext = [
  c.is_conditional && 'conditional',
  c.is_loop && 'in loop',
].filter(Boolean).join(' / ');
```

---

## Plan Conformance

| Plan Item | Status |
|-----------|--------|
| Step 1: CSS with `.node-detail-` prefix, dark mode | Fully implemented |
| Step 2: Four detail components with `{ node, edges, contextData }` | Fully implemented |
| Step 3: Modal shell with ESC, backdrop click, body scroll lock, type dispatch | Fully implemented |
| Step 4: FlowVisualization wiring | Fully implemented |
| Step 5: ApiRoutesVisualization wiring | Fully implemented |
| Step 6: ProjectVisualization with `schemaData` state | Fully implemented |
| `stickyNote` type skipped | Correct in all three views |
| Placeholder node `'1'` skipped in schema view | Correct |
| `contextData` shape per view | Correct: `{ flowData }`, `{ routesData }`, `{ schema: schemaData }` |

---

## Overall Assessment

This is a well-structured feature implementation that follows the plan accurately and mirrors existing patterns in the codebase (InsightGuide). The data lookup strategy is sound -- detail components correctly look up full records from `contextData` using node IDs that match the backend data. Null/undefined handling is thorough with early returns and fallback text.

### Priority fixes before merging:

1. **`flow_type.replace('_', '/')` -- use regex for global replace** (Issue 1, 1-line fix)
2. **Stabilize `onClose` callbacks with `useCallback`** across all three views (Issue 4, prevents unnecessary effect churn)
3. **Fix dark-mode contrast on sibling routes heading** in `RouteNodeDetail` (Issue 6, inline style ignores dark mode)
4. **Use `!node.data?.tableName` guard** instead of `node.id === '1'` for schema double-click (Issue 5, more robust)
5. **Consider removing `call_type === 'direct'` filter** in callers/callees to show richer data (Issue 3, design decision)
