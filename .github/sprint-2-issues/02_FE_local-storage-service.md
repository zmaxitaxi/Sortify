---
title: "feat(frontend): Local Storage Service Abstraction & Data Synchronization"
labels: ["sprint-2", "frontend", "feature"]
subteam: "frontend"
deliverable_branch: "feat/frontend/<claimant>/local-storage-service"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-local-storage-service-abstraction--data-synchronization"
---

## 🎯 Objective
Encapsulate `AsyncStorage` CRUD operations into clean service methods to ensure data integrity across the mobile client, prevent memory bloat by capping cached items, and initialize a unique client device UUID to allow future cloud sync without email/password barriers.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: Local Storage Service Abstraction & Data Synchronization](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-local-storage-service-abstraction--data-synchronization)
- **Frontend Subteam Plan:** [Frontend Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_frontend.md#ticket-local-storage-service-abstraction--data-synchronization)
- **Starter Code Reference:** [starter_code/updated_frontend_code.md#ticket-local-storage-abstraction-helper](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_frontend_code.md#ticket-local-storage-abstraction-helper)

## 📁 Expected Files
- `src/services/storage.js`
- `src/services/__tests__/storage.test.js` (or unit test suite)

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/frontend/<claimant>/local-storage-service`
- **Storage Service (`src/services/storage.js`):**
  - Implement `saveScanRecord(scanData)`: generates unique `id`, ISO timestamp, prepends to scan array, caps to 100 items (`updated.slice(0, 100)`), and serializes to JSON.
  - Implement `loadSavedScans()`: deserializes scans array safely with fallback to `[]` on null or corrupt data.
  - Implement `clearHistory()`: clears cached records for user resets or debugging.
  - Implement `getOrCreateDeviceUuid()`: reads `@sortify_device_uuid` from storage, or creates a pseudo-UUID / nanoid string and persists it.
- **Verification:**
  - Execute unit tests for storage helpers; verify records serialize and deserialize cleanly without schema errors.
  - Verify that storing 105 records retains exactly the 100 most recent records.

---

## 💻 Starter Scaffold

### `src/services/storage.js`
```javascript
// src/services/storage.js
import AsyncStorage from '@react-native-async-storage/async-storage';

const SCANS_STORAGE_KEY = '@sortify_saved_scans';
const STREAK_STORAGE_KEY = '@sortify_user_streak';
const DEVICE_UUID_KEY = '@sortify_device_uuid';

/**
 * Saves a single scan record to local AsyncStorage, capped at the 100 most recent items.
 */
export async function saveScanRecord(scanData) {
  try {
    const existing = await loadSavedScans();
    const newRecord = {
      id: `scan_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`,
      timestamp: new Date().toISOString(),
      ...scanData,
    };
    const updated = [newRecord, ...existing];
    await AsyncStorage.setItem(SCANS_STORAGE_KEY, JSON.stringify(updated.slice(0, 100))); // keep latest 100
    return newRecord;
  } catch (error) {
    console.error('Error saving scan to local storage:', error);
    return null;
  }
}

/**
 * Retrieves all saved scan records from local AsyncStorage.
 */
export async function loadSavedScans() {
  try {
    const raw = await AsyncStorage.getItem(SCANS_STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (error) {
    console.error('Error loading scans from local storage:', error);
    return [];
  }
}

/**
 * Clears all scan history from local AsyncStorage.
 */
export async function clearHistory() {
  try {
    await AsyncStorage.removeItem(SCANS_STORAGE_KEY);
    return true;
  } catch (error) {
    console.error('Error clearing scan history:', error);
    return false;
  }
}

/**
 * Gets or initializes a unique guest device UUID for device-level cloud sync.
 */
export async function getOrCreateDeviceUuid() {
  try {
    let deviceId = await AsyncStorage.getItem(DEVICE_UUID_KEY);
    if (!deviceId) {
      deviceId = `dev_${Date.now()}_${Math.random().toString(36).substring(2, 10)}`;
      await AsyncStorage.setItem(DEVICE_UUID_KEY, deviceId);
    }
    return deviceId;
  } catch (error) {
    console.error('Error managing device UUID:', error);
    return 'fallback_device_uuid';
  }
}
```
