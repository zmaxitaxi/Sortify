---
title: "feat(frontend): History Feed Screen & Stats / Streak Dashboard"
labels: ["sprint-2", "frontend", "feature"]
subteam: "frontend"
deliverable_branch: "feat/frontend/<claimant>/history-and-stats-screens"
ticket_url: "https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-history-feed-screen--stats--streak-dashboard"
---

## 🎯 Objective
Provide users with an engaging visual log of their past scans and impact metrics to build long-term sustainability habits without requiring an account registration wall.

## 🔗 Link to Ticket Description
- **Master Plan Ticket:** [Sprint 2: History Feed Screen & Stats / Streak Dashboard](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_team_weekly_assignments.md#ticket-history-feed-screen--stats--streak-dashboard)
- **Frontend Subteam Plan:** [Frontend Sprint 2 Plan](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/updated_frontend.md#ticket-history-feed-screen--stats--streak-dashboard)
- **Starter Code Reference:** [starter_code/updated_frontend_code.md#ticket-history-feed-screen](https://github.com/BoppingNoodles/Sortify/blob/main/weekly_assignments/starter_code/updated_frontend_code.md#ticket-history-feed-screen)

## 📁 Expected Files
- `src/screens/HistoryScreen.js`
- `src/screens/StatsScreen.js`
- `src/screens/ScanScreen.js` (update to automatically persist successful scans)

## 📦 Expected Deliverable
- **Deliverable & Branch:** `feat/frontend/<claimant>/history-and-stats-screens`
- **History Feed (`HistoryScreen.js`):**
  - Implement using `<FlatList>` displaying scan cards with image thumbnail, detected item name, target bin, timestamp, and "+10 pts" badge.
  - Pull-to-refresh (`RefreshControl`) re-fetching scans from local storage.
  - Empty-state component ("No scans yet! Snap an item to start your streak") with a direct CTA button to navigate to `ScanScreen`.
- **Stats Dashboard (`StatsScreen.js`):**
  - Hero card displaying current streak with flame emoji (`🔥 4 Day Streak!`).
  - Stats grid displaying Total Scans and Eco-Points earned (`total_scans * 10`).
  - Category breakdown distribution list showing items sorted by category (compost, plastic, paper, glass, landfill).
- **Scan Persistence:**
  - In `ScanScreen.js`, automatically invoke `saveScanRecord()` on classification success before or during navigation to `ResultModal`.
- **Verification:**
  - Complete 3 scans on an emulator or physical device.
  - Open the History tab and confirm all 3 scans appear immediately.
  - Restart the application and verify history and stats persist across launches.

---

## 💻 Starter Scaffold

### `src/screens/HistoryScreen.js`
```javascript
// src/screens/HistoryScreen.js
import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, FlatList, Image, TouchableOpacity, RefreshControl, SafeAreaView } from 'react-native';
import { loadSavedScans } from '../services/storage';

export default function HistoryScreen({ navigation }) {
  const [scans, setScans] = useState([]);
  const [refreshing, setRefreshing] = useState(false);

  const fetchHistory = async () => {
    setRefreshing(true);
    try {
      const data = await loadSavedScans();
      setScans(data);
    } catch (err) {
      console.error('Failed to load history:', err);
    } finally {
      setRefreshing(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, []);

  const renderItem = ({ item }) => (
    <View style={styles.scanCard}>
      {item.photoUri ? (
        <Image source={{ uri: item.photoUri }} style={styles.cardImage} />
      ) : (
        <View style={styles.cardPlaceholder}><Text style={styles.placeholderEmoji}>♻️</Text></View>
      )}
      <View style={styles.cardContent}>
        <Text style={styles.cardTitle}>{item.itemName || 'Waste Item'}</Text>
        <Text style={styles.cardSubtitle}>{item.bin || 'Sorted Item'}</Text>
        <Text style={styles.cardDate}>{item.date || 'Today'}</Text>
      </View>
      <View style={styles.pointsBadge}>
        <Text style={styles.pointsText}>+10 pts</Text>
      </View>
    </View>
  );

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.headerTitle}>Scan History</Text>
      </View>
      <FlatList
        data={scans}
        keyExtractor={(item, index) => item.id || `scan_${index}`}
        renderItem={renderItem}
        contentContainerStyle={scans.length === 0 ? styles.emptyContainer : styles.listContent}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={fetchHistory} />}
        ListEmptyComponent={
          <View style={styles.emptyView}>
            <Text style={styles.emptyEmoji}>📸</Text>
            <Text style={styles.emptyTitle}>No scans yet</Text>
            <Text style={styles.emptyBody}>Snap a photo of waste on campus to start your sorting streak!</Text>
            <TouchableOpacity style={styles.scanNowButton} onPress={() => navigation.navigate('ScanScreen')}>
              <Text style={styles.scanNowButtonText}>Scan First Item</Text>
            </TouchableOpacity>
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8F9FA' },
  header: { padding: 20, backgroundColor: '#FFF', borderBottomWidth: 1, borderBottomColor: '#EEE' },
  headerTitle: { fontSize: 22, fontWeight: '800', color: '#111' },
  listContent: { padding: 16 },
  emptyContainer: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  scanCard: {
    flexDirection: 'row',
    backgroundColor: '#FFF',
    borderRadius: 14,
    padding: 12,
    marginBottom: 10,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  cardImage: { width: 60, height: 60, borderRadius: 10, marginRight: 14 },
  cardPlaceholder: { width: 60, height: 60, borderRadius: 10, backgroundColor: '#E9ECEF', justifyContent: 'center', alignItems: 'center', marginRight: 14 },
  placeholderEmoji: { fontSize: 24 },
  cardContent: { flex: 1 },
  cardTitle: { fontSize: 16, fontWeight: '700', color: '#222' },
  cardSubtitle: { fontSize: 13, color: '#666', marginTop: 2 },
  cardDate: { fontSize: 12, color: '#999', marginTop: 4 },
  pointsBadge: { backgroundColor: '#E8F5E9', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12 },
  pointsText: { color: '#2E7D32', fontSize: 12, fontWeight: '700' },
  emptyView: { alignItems: 'center', paddingHorizontal: 30 },
  emptyEmoji: { fontSize: 50, marginBottom: 12 },
  emptyTitle: { fontSize: 18, fontWeight: '700', color: '#222', marginBottom: 6 },
  emptyBody: { fontSize: 14, color: '#666', textAlign: 'center', lineHeight: 20, marginBottom: 20 },
  scanNowButton: { backgroundColor: '#003262', paddingVertical: 12, paddingHorizontal: 24, borderRadius: 20 },
  scanNowButtonText: { color: '#FFF', fontWeight: '700', fontSize: 15 },
});
```

### `src/screens/StatsScreen.js`
```javascript
// src/screens/StatsScreen.js
import React, { useState, useEffect } from 'react';
import { StyleSheet, Text, View, ScrollView, SafeAreaView, ActivityIndicator } from 'react-native';

export default function StatsScreen() {
  const [stats, setStats] = useState({
    currentStreak: 4,
    totalScans: 28,
    ecoPoints: 280,
    breakdown: { compost: 12, plastic: 8, paper: 5, glass: 2, landfill: 1 },
  });

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.content}>
        <Text style={styles.screenTitle}>Impact Dashboard</Text>

        {/* Streak Flame Card */}
        <View style={styles.streakCard}>
          <Text style={styles.streakEmoji}>🔥</Text>
          <Text style={styles.streakCount}>{stats.currentStreak} Day Streak!</Text>
          <Text style={styles.streakSubtext}>Scan daily to keep the campus green</Text>
        </View>

        {/* Impact Counters Grid */}
        <View style={styles.statsGrid}>
          <View style={styles.statBox}>
            <Text style={styles.statNumber}>{stats.totalScans}</Text>
            <Text style={styles.statLabel}>Total Scans</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statNumber}>{stats.ecoPoints}</Text>
            <Text style={styles.statLabel}>Eco Points</Text>
          </View>
        </View>

        {/* Sorting Category Breakdown */}
        <View style={styles.breakdownCard}>
          <Text style={styles.cardHeader}>Category Distribution</Text>
          {Object.entries(stats.breakdown).map(([cat, count]) => (
            <View key={cat} style={styles.categoryRow}>
              <Text style={styles.categoryName}>{cat.toUpperCase()}</Text>
              <Text style={styles.categoryCount}>{count} items</Text>
            </View>
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#F8F9FA' },
  content: { padding: 20 },
  screenTitle: { fontSize: 24, fontWeight: '800', color: '#111', marginBottom: 16 },
  streakCard: {
    backgroundColor: '#FFF3E0',
    borderColor: '#FFE0B2',
    borderWidth: 1,
    borderRadius: 18,
    padding: 24,
    alignItems: 'center',
    marginBottom: 16,
  },
  streakEmoji: { fontSize: 44, marginBottom: 8 },
  streakCount: { fontSize: 22, fontWeight: '800', color: '#E65100' },
  streakSubtext: { fontSize: 13, color: '#BF360C', marginTop: 4 },
  statsGrid: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  statBox: {
    flex: 1,
    backgroundColor: '#FFF',
    borderRadius: 16,
    padding: 20,
    marginHorizontal: 4,
    alignItems: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  statNumber: { fontSize: 26, fontWeight: '800', color: '#003262' },
  statLabel: { fontSize: 13, color: '#666', marginTop: 4, fontWeight: '600' },
  breakdownCard: {
    backgroundColor: '#FFF',
    borderRadius: 16,
    padding: 20,
    shadowColor: '#000',
    shadowOpacity: 0.04,
    shadowRadius: 6,
    elevation: 2,
  },
  cardHeader: { fontSize: 16, fontWeight: '700', color: '#111', marginBottom: 14 },
  categoryRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: '#F0F0F0' },
  categoryName: { fontSize: 14, fontWeight: '600', color: '#444' },
  categoryCount: { fontSize: 14, fontWeight: '700', color: '#003262' },
});
```
