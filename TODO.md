# Low Severity Issues - Fix Status

## ✅ Completed - All issues resolved

### ESLint Issues (react/no-unescaped-entities)
- [x] **frontend/src/app/not-found.tsx** - Escaped apostrophes
- [x] **frontend/src/app/dashboard/page.tsx** - Escaped apostrophes
- [x] **frontend/src/app/page.tsx** - Escaped quotes in JSX
- [x] **frontend/src/app/speaking/page.tsx** - Escaped quotes in JSX
- [x] **frontend/src/app/writing/page.tsx** - Escaped quotes in JSX

### @next/next/no-img-element Warning
- [x] **frontend/src/components/ui/avatar.tsx** - Replaced `<img>` with `<Image>` from `next/image`

### Unused Imports Removed
- [x] **frontend/src/app/analytics/page.tsx** - Removed unused `TrendingUp` import
- [x] **frontend/src/app/diagnostic/result/page.tsx** - Removed unused `Target` import
- [x] **frontend/src/app/signup/page.tsx** - Removed unused `Chrome` import
- [x] **frontend/src/app/notifications/page.tsx** - Removed unused `Button` import
- [x] **frontend/src/app/notifications/page.tsx** - Removed unused `Bell, Settings, History, Trash2` imports
- [x] **frontend/src/app/privacy/page.tsx** - Removed unused `Button` import
- [x] **frontend/src/app/terms/page.tsx** - Removed unused `Button` import
- [x] **frontend/src/app/cookies/page.tsx** - Removed unused `Button` import
- [x] **frontend/src/components/shared/navbar.tsx** - Removed unused `cn` import
- [x] **frontend/src/components/shared/sidebar.tsx** - Removed unused `History` import
- [x] **backend/app/services/ielts_service.py** - Removed unused `Dict` import

### Formatting Inconsistencies Fixed
- [x] **frontend/src/components/shared/navbar.tsx** - Fixed `navLinks` indentation, `Logo Area` comment indentation, `DropdownItem` indentation
- [x] **frontend/src/components/shared/sidebar.tsx** - Fixed `routes` indentation
- [x] **frontend/src/app/writing/page.tsx** - Fixed timer `div` indentation, `Tabs` indentation
- [x] **frontend/src/app/speaking/page.tsx** - Fixed `button` indentation
- [x] **frontend/src/app/roadmap/page.tsx** - Fixed `Progress` indentation
- [x] **frontend/src/app/signup/page.tsx** - Fixed `Input` indentation in all form fields

## Result
- **`npx next lint`** → ✔ No ESLint warnings or errors
