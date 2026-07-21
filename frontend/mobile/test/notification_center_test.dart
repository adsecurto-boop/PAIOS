// The M14 mirror: center behaviour and dashboard diffing.
import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/models/models.dart';
import 'package:paios_mobile/services/notification_center.dart';

import 'fixtures.dart';

DashboardData data(Map<String, dynamic> json) => DashboardData.fromJson(json);

void main() {
  group('NotificationCenter', () {
    test('unread, mark read, clear', () {
      final center = NotificationCenter();
      for (var i = 0; i < 3; i++) {
        center.add(MobileNotification(message: 'm$i', category: 'App'));
      }
      expect(center.unreadCount, 3);
      expect(center.entries.first.message, 'm2'); // newest first
      expect(center.markAllRead(), 3);
      expect(center.unreadCount, 0);
      expect(center.clear(), 3);
      expect(center.entries, isEmpty);
    });

    test('bounded ring', () {
      final center = NotificationCenter(limit: 2);
      for (var i = 0; i < 4; i++) {
        center.add(MobileNotification(message: 'm$i', category: 'App'));
      }
      expect(center.entries.map((n) => n.message), ['m3', 'm2']);
    });

    test('round-trips through JSON (persisted history)', () {
      final center = NotificationCenter();
      center.add(MobileNotification(
          message: 'hello', category: 'Event', kind: 'ok', read: true));
      final restored = NotificationCenter()..restore(center.toJson());
      expect(restored.entries.single.message, 'hello');
      expect(restored.entries.single.read, isTrue);
      expect(restored.unreadCount, 0);
    });
  });

  group('DashboardWatcher', () {
    test('first observation is a silent baseline', () {
      final watcher = DashboardWatcher();
      expect(watcher.observe(data(dashboardJson())), isEmpty);
    });

    test('new recommendation and disturber detected', () {
      final watcher = DashboardWatcher();
      watcher.observe(data(dashboardJson()));
      final fresh = watcher.observe(data(dashboardJson(
        recommendations: [
          {
            'recommendation_id': 'r1',
            'status': 'Pending',
            'reason': 'old',
            'priority': 1.0,
          },
          {
            'recommendation_id': 'r2',
            'status': 'Pending',
            'reason': 'Study ISTQB for 60 minutes',
            'priority': 2.0,
          },
        ],
        disturbers: [
          {
            'event_disturber_id': 'd1',
            'type': 'Work',
            'severity': 'High',
            'description': 'Urgent call',
            'state': 'Analyzed',
          },
        ],
      )));
      final messages = fresh.map((n) => n.message).toList();
      expect(messages,
          contains('Recommendation: Study ISTQB for 60 minutes'));
      expect(messages, contains('Disturbance: [High] Urgent call'));
      expect(
          fresh.firstWhere((n) => n.category == 'Disturbance').kind, 'error');
      // r1 was already known at baseline: not re-announced.
      expect(messages.any((m) => m.contains('old')), isFalse);
    });

    test('unchanged snapshot reports nothing', () {
      final watcher = DashboardWatcher();
      watcher.observe(data(dashboardJson()));
      expect(watcher.observe(data(dashboardJson())), isEmpty);
    });

    test('running event and context change detected', () {
      final watcher = DashboardWatcher();
      watcher.observe(data(dashboardJson()));
      final fresh = watcher.observe(data(dashboardJson(
        currentEvent: {
          'event_id': 'e1',
          'description': 'Deep work',
          'status': 'Started',
        },
        executionContext: 'EventExecutionContext',
      )));
      final messages = fresh.map((n) => n.message).toSet();
      expect(messages, contains('Now running: Deep work'));
      expect(messages,
          contains('Context changed: EventExecutionContext'));
    });
  });
}
