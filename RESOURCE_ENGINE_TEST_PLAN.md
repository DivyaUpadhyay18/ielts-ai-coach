# Resource Engine - Test & Fix Plan

## Executive Summary
Comprehensive testing and validation of the entire Resource Engine including CRUD, Recommendation Engine, Bookmarks, Notes, Search, Analytics, Quality Score, and Admin Panel.

## Critical Issues Identified

### 1. MISSING FILES (CRITICAL - Will Cause Application Failure)
- **`backend/app/repositories/recommendation_repo.py`** - MISSING
  - Imported by: `backend/app/services/recommendation_engine_service.py`
  - Impact: Recommendation Engine will fail on startup
  - Fix: Create the repository file

- **`backend/app/models/recommendation.py`** - MISSING
  - Imported by: `backend/app/api/v1/recommendation_engine.py`
  - Impact: API endpoints will fail
  - Fix: Create the models file

- **`backend/app/models/resource_management.py`** - MISSING
  - Imported by: `backend/app/api/v1/resource_management.py`
  - Impact: Resource Management API will fail
  - Fix: Create the models file

- **`backend/app/models/learning_session.py`** - MISSING
  - Imported by: `backend/app/api/v1/learning_session.py`
  - Impact: Learning Session API will fail
  - Fix: Create the models file

### 2. DATABASE SCHEMA ISSUES

#### 2.1 Missing Columns in `resources` Table
The code expects these columns but they may not exist in migration 003_core_domains.sql:
- `sub_skill` (TEXT) - Used in recommendation engine
- `estimated_time` (INTEGER) - Used in recommendation engine
- `popularity_score` (INTEGER) - Used in sorting
- `rating` (NUMERIC) - Used in resource management
- `source` (TEXT) - Used in resource management
- `author` (TEXT) - Used in recommendation engine
- `thumbnail` (TEXT) - Used in recommendation engine
- `language` (TEXT) - Used in recommendation engine
- `verified` (BOOLEAN) - Used in multiple places
- `official` (BOOLEAN) - Used in multiple places
- `is_free` (BOOLEAN) - Used in multiple places
- `minimum_band` (NUMERIC) - Used in recommendation engine
- `maximum_band` (NUMERIC) - Used in recommendation engine
- `provider` (TEXT) - Partially exists
- `duration_minutes` (SMALLINT) - Exists
- `tags` (TEXT[]) - Exists

**Fix:** Update migration 003_core_domains.sql to include all required columns

#### 2.2 Duplicate Table Definitions
Tables defined in multiple migrations:
- `resource_likes` - Defined in both 013_analytics.sql and 015_admin_resource_dashboard.sql
- `resource_ratings` - Defined in both 013_analytics.sql and 015_admin_resource_dashboard.sql
- `resource_views` - Defined in both 013_analytics.sql and 015_admin_resource_dashboard.sql
- `resource_completions` - Defined in both 013_analytics.sql and 015_admin_resource_dashboard.sql

**Fix:** Remove duplicate definitions from 015_admin_resource_dashboard.sql

#### 2.3 Missing Tables
- `resource_suggestions` - Referenced in admin.py and resource_management_repo.py
- `resource_verification_log` - Referenced in resource_management_repo.py
- `recommendation_logs` - Referenced in recommendation_engine_service.py
- `user_skill_performance` - Referenced in recommendation_engine_service.py
- `user_mock_scores` - Referenced in recommendation_engine_service.py

**Fix:** Create migration for missing tables

### 3. API ROUTING ISSUES

#### 3.1 Duplicate Routes
- `/api/v1/resources` - Defined in both `resources.py` and `resource_management.py`
- `/api/v1/resources/{id}/view` - Defined in both files
- `/api/v1/resources/{id}/bookmark` - Defined in both files

**Fix:** Consolidate routes or remove duplicates

#### 3.2 Missing Route Prefixes
Some endpoints in resource_management.py should be under `/resource-management` prefix but are also under `/resources`

**Fix:** Review and consolidate routing

### 4. TYPE MISMATCHES

#### 4.1 Skill Name Capitalization
- Database schema uses: `'writing','speaking','reading','listening','vocabulary','grammar','general'`
- Recommendation engine expects: `'Writing','Listening','Speaking','Reading','Vocabulary','Grammar'`
- Resource management expects: `'Reading','Listening','Writing','Speaking','Vocabulary','Grammar'`

**Fix:** Standardize skill names (recommend lowercase in DB, capitalize in API responses)

#### 4.2 Resource Type Mismatches
- Migration 003: `'video','article','pdf','practice_test','guide','flashcard_set'`
- RESOURCE_ENGINE.md: `'youtube','pdf','website','vocab_sheet','grammar_guide','listening','writing_sample','speaking','practice_test','strategy'`
- Code uses: `'Quiz','Flashcard'` for diversity scoring

**Fix:** Align resource types across all documents and code

### 5. MISSING DEPENDENCY INJECTIONS

#### 5.1 Missing Dependencies in `deps.py`
- `get_resource_management_repo` - Used in resource_management.py
- `get_resource_quality_repo` - Used in resource_quality.py
- `get_current_admin` - Used in admin.py and resource_management.py
- `get_current_super_admin` - Used in admin.py

**Fix:** Add missing dependency functions to `deps.py`

### 6. SERVICE INITIALIZATION ISSUES

#### 6.1 Singleton Pattern
- `recommendation_engine_service` is created at module level in `recommendation_engine_service.py`
- `learning_session_service` is created at module level in `learning_session_service.py`
- These may cause circular import issues

**Fix:** Use proper dependency injection or lazy initialization

## Test Plan

### Phase 1: Fix Critical Issues (Blocking)
1. Create missing repository and model files
2. Fix database schema mismatches
3. Add missing dependency injections
4. Fix duplicate table definitions

### Phase 2: CRUD Operations Testing
1. **Create Resource**
   - Test: POST /api/v1/resources
   - Validate: All fields, constraints, defaults
   - Expected: 201 Created with full resource object

2. **Read Resource**
   - Test: GET /api/v1/resources/{id}
   - Validate: Returns correct resource
   - Expected: 200 OK with resource object

3. **Update Resource**
   - Test: PATCH /api/v1/resources/{id}
   - Validate: Partial updates work
   - Expected: 200 OK with updated resource

4. **Delete Resource**
   - Test: DELETE /api/v1/resources/{id}
   - Validate: Resource removed
   - Expected: 204 No Content

5. **List Resources**
   - Test: GET /api/v1/resources
   - Validate: Pagination, filters, sorting
   - Expected: 200 OK with array

### Phase 3: Recommendation Engine Testing
1. **Get Recommendations**
   - Test: GET /api/v1/recommendations
   - Validate: Returns ranked resources based on user context
   - Expected: 200 OK with scored recommendations

2. **Recommendation History**
   - Test: GET /api/v1/recommendations/history
   - Validate: Returns past recommendations
   - Expected: 200 OK with array

3. **Track Interaction**
   - Test: POST /api/v1/recommendations/track
   - Validate: Logs user interaction
   - Expected: 201 Created

4. **Recommendation Stats**
   - Test: GET /api/v1/recommendations/stats
   - Validate: Returns statistics
   - Expected: 200 OK with stats object

### Phase 4: Bookmarks Testing
1. **Add Bookmark**
   - Test: POST /api/v1/resources/{id}/bookmark
   - Validate: Bookmark created
   - Expected: 201 Created

2. **List Bookmarks**
   - Test: GET /api/v1/bookmarks
   - Validate: Returns user's bookmarks
   - Expected: 200 OK with array

3. **Remove Bookmark**
   - Test: DELETE /api/v1/bookmarks/{resource_id}
   - Validate: Bookmark removed
   - Expected: 204 No Content

4. **Check Bookmark Status**
   - Test: GET /api/v1/resources/{id}/bookmark-status
   - Validate: Returns boolean
   - Expected: 200 OK with {is_bookmarked: true/false}

### Phase 5: Notes Testing
1. **Create Note**
   - Test: POST /api/v1/resource-notes/notes
   - Validate: Note created with correct fields
   - Expected: 201 Created

2. **List Notes**
   - Test: GET /api/v1/resource-notes/notes
   - Validate: Returns user's notes, supports filtering
   - Expected: 200 OK with array

3. **Update Note**
   - Test: PATCH /api/v1/resource-notes/notes/{id}
   - Validate: Note updated
   - Expected: 200 OK with updated note

4. **Delete Note**
   - Test: DELETE /api/v1/resource-notes/notes/{id}
   - Validate: Note removed
   - Expected: 204 No Content

5. **Highlights**
   - Test: POST /api/v1/resource-notes/highlights
   - Validate: Highlight created
   - Expected: 201 Created

6. **Revision Reminders**
   - Test: POST /api/v1/resource-notes/reminders
   - Validate: Reminder created
   - Expected: 201 Created

### Phase 6: Search Testing
1. **Basic Search**
   - Test: GET /api/v1/resources/search?q=ielts
   - Validate: Returns matching resources
   - Expected: 200 OK with filtered results

2. **Advanced Search**
   - Test: GET /api/v1/resources/search with multiple filters
   - Validate: All filters applied correctly
   - Expected: 200 OK with filtered results

3. **Search by Skill**
   - Test: GET /api/v1/resources/by-skill/writing
   - Validate: Returns writing resources
   - Expected: 200 OK with array

4. **Search by Type**
   - Test: GET /api/v1/resources/by-type/video
   - Validate: Returns video resources
   - Expected: 200 OK with array

### Phase 7: Analytics Testing
1. **Track Event**
   - Test: POST /api/v1/analytics/events
   - Validate: Event logged
   - Expected: 201 Created

2. **Dashboard**
   - Test: GET /api/v1/analytics/dashboard
   - Validate: Returns comprehensive analytics
   - Expected: 200 OK with dashboard object

3. **Resource Analytics**
   - Test: GET /api/v1/analytics/resources/{id}
   - Validate: Returns resource-specific analytics
   - Expected: 200 OK with analytics object

4. **User Analytics**
   - Test: GET /api/v1/analytics/me
   - Validate: Returns user's analytics
   - Expected: 200 OK with analytics object

5. **Record View/Completion/Bookmark**
   - Test: POST /api/v1/analytics/resources/{id}/view
   - Validate: View recorded
   - Expected: 200 OK

### Phase 8: Quality Score Testing
1. **Submit Feedback**
   - Test: POST /api/v1/resource-quality/feedback
   - Validate: Feedback created
   - Expected: 201 Created

2. **Get Quality Scores**
   - Test: GET /api/v1/resource-quality/resources/{id}/scores
   - Validate: Returns computed scores
   - Expected: 200 OK with scores

3. **Get Leaderboard**
   - Test: GET /api/v1/resource-quality/leaderboard
   - Validate: Returns top resources
   - Expected: 200 OK with ranked list

4. **Recompute Scores**
   - Test: POST /api/v1/resource-quality/resources/{id}/recompute
   - Validate: Scores recomputed
   - Expected: 200 OK with new scores

5. **Moderation Queue**
   - Test: GET /api/v1/resource-quality/admin/queue
   - Validate: Returns pending feedback
   - Expected: 200 OK with queue

### Phase 9: Admin Panel Testing
1. **List Users**
   - Test: GET /api/v1/admin/users
   - Validate: Returns all users
   - Expected: 200 OK with array

2. **Update User Role**
   - Test: PATCH /api/v1/admin/users/{id}/role
   - Validate: Role updated
   - Expected: 200 OK with updated user

3. **Update User Status**
   - Test: PATCH /api/v1/admin/users/{id}/status
   - Validate: Status updated
   - Expected: 200 OK with updated user

4. **Admin Stats**
   - Test: GET /api/v1/admin/stats
   - Validate: Returns comprehensive stats
   - Expected: 200 OK with stats object

5. **Resource Analytics**
   - Test: GET /api/v1/resource-management/admin/analytics
   - Validate: Returns resource analytics
   - Expected: 200 OK with analytics

6. **Bulk Operations**
   - Test: POST /api/v1/resource-management/bulk
   - Validate: Bulk create/update/delete
   - Expected: 200 OK with results

### Phase 10: Integration Testing
1. **End-to-End User Flow**
   - User signs up → takes diagnostic → gets recommendations → bookmarks resources → takes notes → completes resources → views analytics

2. **Admin Flow**
   - Admin logs in → views dashboard → manages resources → moderates feedback → verifies resources → views analytics

3. **Recommendation Flow**
   - User completes diagnostic → receives recommendations → views resource → completes resource → gets new recommendations

## Implementation Report Template

```markdown
# Resource Engine - Implementation Report

## Test Execution Summary
- **Date:** [Date]
- **Tester:** [Name]
- **Environment:** [Dev/Staging/Prod]
- **Total Tests:** [X]
- **Passed:** [X]
- **Failed:** [X]
- **Blocked:** [X]

## Issues Found and Fixed
1. [Issue description] - [Status: Fixed/Deferred]
2. ...

## Test Results by Component

### CRUD Operations
- Create: [PASS/FAIL]
- Read: [PASS/FAIL]
- Update: [PASS/FAIL]
- Delete: [PASS/FAIL]
- List: [PASS/FAIL]

### Recommendation Engine
- Get Recommendations: [PASS/FAIL]
- History: [PASS/FAIL]
- Track Interaction: [PASS/FAIL]
- Stats: [PASS/FAIL]

### Bookmarks
- Add: [PASS/FAIL]
- List: [PASS/FAIL]
- Remove: [PASS/FAIL]
- Check Status: [PASS/FAIL]

### Notes
- Create Note: [PASS/FAIL]
- List Notes: [PASS/FAIL]
- Update Note: [PASS/FAIL]
- Delete Note: [PASS/FAIL]
- Highlights: [PASS/FAIL]
- Reminders: [PASS/FAIL]

### Search
- Basic Search: [PASS/FAIL]
- Advanced Search: [PASS/FAIL]
- By Skill: [PASS/FAIL]
- By Type: [PASS/FAIL]

### Analytics
- Track Event: [PASS/FAIL]
- Dashboard: [PASS/FAIL]
- Resource Analytics: [PASS/FAIL]
- User Analytics: [PASS/FAIL]

### Quality Score
- Submit Feedback: [PASS/FAIL]
- Get Scores: [PASS/FAIL]
- Leaderboard: [PASS/FAIL]
- Recompute: [PASS/FAIL]
- Moderation: [PASS/FAIL]

### Admin Panel
- List Users: [PASS/FAIL]
- Update Role: [PASS/FAIL]
- Update Status: [PASS/FAIL]
- Stats: [PASS/FAIL]
- Bulk Operations: [PASS/FAIL]

## Performance Metrics
- Average Response Time: [X ms]
- Slowest Endpoint: [Endpoint] - [X ms]
- Fastest Endpoint: [Endpoint] - [X ms]

## Security Checks
- [ ] Authentication required on protected endpoints
- [ ] Authorization checks working
- [ ] SQL injection prevented
- [ ] XSS prevented
- [ ] CSRF protection enabled

## Recommendations
1. [Recommendation 1]
2. [Recommendation 2]

## Sign-off
- **Tested by:** [Name]
- **Date:** [Date]
- **Status:** [Approved/Needs Revision]
```

## Next Steps
1. Fix all critical issues (missing files, schema mismatches)
2. Run database migrations
3. Execute test plan
4. Generate implementation report
5. Commit changes
6. Deploy to staging for UAT