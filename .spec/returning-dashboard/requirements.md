# Requirements: Returning Customer Dashboard

## Introduction

Returning customers — pet parents who have already uploaded health documents — currently see the same full-size sequential card layout as first-time users. Stakeholder Anu requested a compact, tracker-led layout for returning customers that prioritizes the care plan over document recognition, since returning users have already been through that step. First-time customers keep the current layout unchanged. The duplicate HealthRecordsNav card is removed for all users.

---

## Requirements

### Requirement 1: Returning Customer Detection

**User Story:** As a pet parent returning to the dashboard, I want the system to recognize that I've already uploaded documents, so that I see a layout optimized for ongoing care rather than first-time onboarding.

#### Acceptance Criteria

1. WHEN a dashboard loads AND `data.documents.length > 0` THEN the system SHALL render the returning customer layout.
2. WHEN a dashboard loads AND `data.documents` is empty or absent THEN the system SHALL render the existing first-time layout unchanged.
3. The system SHALL evaluate the returning condition on every render (no caching of user type).

---

### Requirement 2: Compact Health Records Card

**User Story:** As a returning customer, I want to see a minimal "Organized Health Records" row instead of the full RecognitionCard, so that I can quickly access my records without the card occupying significant vertical space.

#### Acceptance Criteria

1. WHEN the returning layout renders THEN the system SHALL display a single-row CompactRecordsCard with the text "Organized Health Records" on the left and a "View All" button on the right.
2. WHEN the user taps "View All" THEN the system SHALL navigate to the Records view.
3. The CompactRecordsCard SHALL display the report count alongside the title.
4. The card SHALL take "negligible space" — single-row height, no multi-line content.

---

### Requirement 3: Collapsed Analysis Summary

**User Story:** As a returning customer, I want the Life Stage, Health Conditions, and Diet Analysis cards grouped under a collapsible "Analysis" section that starts collapsed, so that I can expand them when needed without them consuming space by default.

#### Acceptance Criteria

1. WHEN the returning layout renders THEN the system SHALL display an AnalysisSummaryCard using the existing `CollapsibleCard` primitive with `defaultOpen={false}`.
2. WHEN the user taps the Analysis header THEN the system SHALL expand to show LifeStageCard, HealthConditionsCard, and DietAnalysisCard in order.
3. WHEN rendered inside the AnalysisSummaryCard THEN each of the 3 analysis cards SHALL suppress their outer `.card` wrapper (via a `compact` boolean prop) to avoid double-bordered nesting.
4. The HealthConditionsCard inside the collapsible SHALL retain its "Discuss with your vet" button and `onGoToTrends` navigation.

---

### Requirement 4: Care Plan Tracker

**User Story:** As a returning customer, I want to see a quick status summary of my pet's care plan at a glance, so that I know how many items are on track, due soon, or overdue without scrolling through the full care plan.

#### Acceptance Criteria

1. WHEN the returning layout renders THEN the system SHALL display a CarePlanTracker heading "{petName}'s Care Plan" with 3 colored count pills.
2. The green pill SHALL show "X On Track" (items where `itemStatusClass()` returns `s-tag-g`).
3. The amber pill SHALL show "Y Due Soon" (items where `itemStatusClass()` returns `s-tag-y`).
4. The red pill SHALL show "Z Overdue" (items where `itemStatusClass()` returns `s-tag-r`).
5. IF all three counts are zero THEN the CarePlanTracker SHALL be hidden.
6. The counts SHALL be computed by a `computeCarePlanCounts()` utility that iterates all items across all 3 care plan buckets.

---

### Requirement 5: Returning Layout Composition

**User Story:** As a returning customer, I want to see the dashboard cards in a specific order that prioritizes my care plan, so that the most actionable information is immediately visible.

#### Acceptance Criteria

1. WHEN the returning layout renders THEN the system SHALL display components in this order (top to bottom):
   - ProfileBanner (unchanged)
   - CompactRecordsCard
   - AnalysisSummaryCard (collapsed)
   - CarePlanTracker
   - CarePlanCard (existing 3-bucket card, labels unchanged)
   - CartFloater (existing floating cart button)
2. The NudgeBanner SHALL NOT render in the returning layout (replaced by CarePlanTracker).
3. The returning layout SHALL use the same `DashboardViewProps` interface as the existing DashboardView.
4. The cart animation logic (IntersectionObserver on `.order-btn`, addedIds flash, timer cleanup) SHALL work identically to the existing DashboardView.

---

### Requirement 6: Remove HealthRecordsNav for All Users

**User Story:** As any user (first-time or returning), I want a non-redundant dashboard, so that I don't see duplicate navigation to health records.

#### Acceptance Criteria

1. The system SHALL remove the HealthRecordsNav component from the existing DashboardView (first-time layout).
2. The HealthRecordsNav component SHALL NOT appear in the returning layout.
3. The RecognitionCard in the first-time layout SHALL continue to provide "View all reports" navigation to Records, preserving the navigation path.

---

### Requirement 7: Cart Parity

**User Story:** As a returning customer, I want cart functionality (add to cart, floater button, cart count) to work exactly the same as the first-time layout.

#### Acceptance Criteria

1. WHEN a returning customer adds an item to the cart THEN the CartFloater SHALL appear and update identically to the first-time layout.
2. WHEN a returning customer taps the CartFloater THEN the system SHALL navigate to the Cart view.
3. The "Added" flash animation on cart items SHALL work identically in both layouts.

---

### Requirement 8: Build Integrity

**User Story:** As a developer, I want the build to pass cleanly after these changes.

#### Acceptance Criteria

1. `npm run build` SHALL complete without TypeScript or build errors.
2. No existing component behavior SHALL be altered except the explicit removal of HealthRecordsNav from DashboardView.
