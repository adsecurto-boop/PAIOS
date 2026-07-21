// Model parsing: REST payloads -> typed views, tolerant of gaps.
import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/models/models.dart';

import 'fixtures.dart';

void main() {
  group('DashboardData', () {
    test('parses the full payload', () {
      final data = DashboardData.fromJson(dashboardJson());
      expect(data.currentTime, '2026-07-21T09:00:00');
      expect(data.currentEvent, isNull);
      expect(data.executionContext, 'IdleExecutionContext');
      expect(data.recommendations, hasLength(1));
      expect(data.recommendations.first.reason, contains('rest to recover'));
      expect(data.goals.first.name, 'Learn Sanskrit');
      expect(data.projects.first.completion, 40.0);
      expect(data.healthResources.first.type, 'Energy');
      expect(data.latestReflection?.lessonLearned, 'Breaks work');
      expect(data.kernel, 'Running');
      expect(data.operational, isTrue);
    });

    test('survives an empty payload without crashing', () {
      final data = DashboardData.fromJson(const {});
      expect(data.currentEvent, isNull);
      expect(data.recommendations, isEmpty);
      expect(data.operational, isFalse);
    });

    test('parses a running current event', () {
      final data = DashboardData.fromJson(dashboardJson(currentEvent: {
        'event_id': 'e1',
        'description': 'Deep work',
        'status': 'Started',
        'started_at': '2026-07-21T09:00:00',
        'elapsed_minutes': 12,
        'duration_minutes': 60,
        'remaining_minutes': 48,
      }));
      expect(data.currentEvent!.description, 'Deep work');
      expect(data.currentEvent!.remainingMinutes, 48);
    });
  });

  group('formatters', () {
    test('clock and dayTime', () {
      expect(clock('2026-07-21T09:05:00'), '09:05');
      expect(clock(null), '—');
      expect(dayTime('2026-07-21T09:05:00'), '2026-07-21 09:05');
      expect(dayTime(null), '—');
    });
  });

  test('EventItem parses', () {
    final event = EventItem.fromJson(eventsJson().first);
    expect(event.id, 'e1');
    expect(event.status, 'Ready');
    expect(event.durationMinutes, 60);
    expect(event.transitions, hasLength(1));
  });

  test('ResourceItem parses decimals', () {
    final resource = ResourceItem.fromJson(resourcesJson()[1]);
    expect(resource.value, 250.5);
    expect(resource.unit, 'EUR');
  });
}
