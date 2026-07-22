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

  group('M20 models', () {
    test('PlanEntry list parses and tolerates gaps', () {
      final entries = PlanEntry.listFrom(planJson());
      expect(entries, hasLength(5));
      expect(entries.first.eventId, 'e1');
      expect(entries.first.durationMinutes, 60);
      expect(entries.first.priority, 8.0);
      // Tolerance: garbage in, empty list out - never a throw.
      expect(PlanEntry.listFrom(null), isEmpty);
      expect(PlanEntry.listFrom({'entries': 'nope'}), isEmpty);
      final bare = PlanEntry.fromJson(const {});
      expect(bare.eventId, '');
      expect(bare.plannedStart, isNull);
    });

    test('InboxItem list parses from envelope or bare list', () {
      final items = InboxItem.listFrom(inboxJson());
      expect(items, hasLength(2));
      expect(items.first.text, 'Buy milk');
      expect(items.first.status, 'open');
      expect(items.last.convertedTo, 'goal:g9');
      expect(InboxItem.listFrom(inboxJson()['items']), hasLength(2));
      expect(InboxItem.listFrom(null), isEmpty);
      expect(InboxItem.fromJson(const {}).status, 'open');
    });

    test('ProposalItem list parses with duplicate flag', () {
      final items = ProposalItem.listFrom(assistantPlanJson());
      expect(items, hasLength(3));
      expect(items[0].kind, 'event');
      expect(items[0].duplicateOf, isNull);
      expect(items[2].duplicateOf, 'e1');
      // Title falls back to the raw text when absent.
      final bare = ProposalItem.fromJson(const {'text': 'buy milk'});
      expect(bare.title, 'buy milk');
      expect(bare.kind, 'inbox');
    });

    test('DayReason list parses', () {
      final reasons = DayReason.listFrom(assistantExplainJson());
      expect(reasons, hasLength(1));
      expect(reasons.first.title, 'Deep work');
      expect(reasons.first.reason, contains('priority'));
      expect(DayReason.listFrom(const {}), isEmpty);
    });

    test('EventMetadata parses and tolerates gaps', () {
      final metadata = EventMetadata.fromJson(eventMetadataJson());
      expect(metadata.tags, ['work', 'focus']);
      expect(metadata.energy, 'high');
      expect(metadata.estimatedDurationMinutes, 60);
      final bare = EventMetadata.fromJson(const {});
      expect(bare.tags, isEmpty);
      expect(bare.deadline, isNull);
    });
  });
}
