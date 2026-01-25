---
name: react-tailwind-architect
description: Use when developing or refactoring React components with Tailwind CSS, focusing on UI consistency, theming, and component decoupling.
---

# React & Tailwind Architect

## Overview
Enforces UI architecture best practices for "Dark Mode" capable, premium interfaces. Focuses on component decoupling, consistent theming via utility classes, and avoid hardcoded values.

## When to Use
- Creating new UI components for the investigation report or dashboard.
- Refactoring frontend code for the "Three-Segment Report" visualization.
- Implementing dark/light mode switching.
- Fixing inconsistent styling or hardcoded colors.

## Core Rules

### 1. No Hardcoded Colors
**STOP**: Writing hex codes like `#1a1a2e` or `rgba(0,0,0,0.5)` directly in classes.
**USE**: Semantic CSS variables or Tailwind theme tokens.

```jsx
// ❌ BAD
<div className="bg-[#1a1a2e] text-[#e0e0e0]">

// ✅ GOOD (Configured in tailwind.config.js)
<div className="bg-primary-900 text-text-main dark:bg-slate-900">
```

### 2. Component Decoupling
**STOP**: Mixing API fetching logic deeply inside UI components.
**USE**: Container/Presentational pattern or Custom Hooks. Pass data as props.

```jsx
// ❌ BAD: Fetches data inside the button
const ReportButton = () => {
   const data = fetch('/api/...');
   return <button>{data.status}</button>
}

// ✅ GOOD
const ReportButton = ({ status, onClick }) => (
   <button onClick={onClick}>{status}</button>
)
```

### 3. Tailwind: Utility First vs @apply
- **Utility First**: Write classes directly in JSX for readability and rapid dev.
- **@apply**: Use ONLY for highly reusable, complex component primitives (like `.btn-primary`) or resetting base styles. **Do not overuse.**

### 4. Dynamic Class Management
**STOP**: String concatenation for classes.
**USE**: `clsx` or `tailwind-merge` to handle conditional classes cleanly.

```jsx
// ❌ BAD
className={"btn " + (isActive ? "active" : "")}

// ✅ GOOD
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
className={twMerge(clsx("btn px-4 py-2", isActive && "bg-blue-500"))}
```

## Theming Strategy (Dark/Light)
- Use `dark:` modifier extensively.
- Define colors in `tailwind.config.js` referencing CSS variables (e.g., `--bg-primary`) for auto-switching.

```css
/* global.css */
:root {
  --bg-primary: #ffffff;
}
.dark {
  --bg-primary: #0f172a;
}
```
