# TODO — Band Estimation Engine

## Backend
- [x] Create migration `backend/app/db/migrations/025_band_estimation.sql`
- [x] Create model `backend/app/models/band_estimation.py`
- [x] Create repository `backend/app/repositories/band_estimation_repo.py`
- [x] Create service `backend/app/services/band_estimation_service.py`
- [x] Create API router `backend/app/api/v1/band_estimation.py`
- [x] Wire `backend/app/api/deps.py` (imports + get_service dependency)
- [x] Wire `backend/app/api/v1/router.py` (import + include with `/band-estimation` prefix)
- [x] Update `backend/app/main.py` endpoints map
- [x] Create verify script `backend/verify_band_estimation.py`

## Frontend
- [x] Create types in `frontend/src/types/index.ts` (BandEstimationInput/Response/HistoryItem/Response)
- [x] Create service `bandEstimationService` in `frontend/src/services/api.ts`
- [x] Create page `frontend/src/app/estimation/page.tsx` (self-contained UI)
- [x] Wire sidebar nav entry in `frontend/src/components/shared/sidebar.tsx`

## Documentation
- [x] Create `BAND_ESTIMATION.md` (formula reference + architecture + API docs)

## Verification
- [x] Run `python verify_band_estimation.py` — ALL TESTS PASSED
- [x] Frontend types/service/component consistency verified against backend response keys
