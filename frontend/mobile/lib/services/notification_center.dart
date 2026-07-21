// The M14 pattern on the phone: notifications derived by diffing
// consecutive /dashboard snapshots. Pure Dart, no Flutter imports -
// presentation diffing of ids the API already sent, never business
// logic.
import '../models/models.dart';

class MobileNotification {
  final String message;
  final String category; // Recommendation | Disturbance | Event | Context | App
  final String kind; // info | ok | warn | error
  final String occurredAt; // display clock string
  bool read;

  MobileNotification({
    required this.message,
    required this.category,
    this.kind = 'info',
    this.occurredAt = '',
    this.read = false,
  });

  Map<String, dynamic> toJson() => {
        'message': message,
        'category': category,
        'kind': kind,
        'occurred_at': occurredAt,
        'read': read,
      };

  factory MobileNotification.fromJson(Map<String, dynamic> json) =>
      MobileNotification(
        message: json['message'] as String? ?? '',
        category: json['category'] as String? ?? 'App',
        kind: json['kind'] as String? ?? 'info',
        occurredAt: json['occurred_at'] as String? ?? '',
        read: json['read'] == true,
      );
}

/// Bounded, newest-first history with unread tracking (mirrors the
/// desktop NotificationCenter; JSON-serializable so it survives app
/// restarts - one of the three permitted local stores).
class NotificationCenter {
  final int limit;
  final List<MobileNotification> _entries = [];

  NotificationCenter({this.limit = 200});

  List<MobileNotification> get entries => List.unmodifiable(_entries);

  int get unreadCount => _entries.where((n) => !n.read).length;

  void add(MobileNotification notification) {
    _entries.insert(0, notification);
    if (_entries.length > limit) {
      _entries.removeRange(limit, _entries.length);
    }
  }

  int markAllRead() {
    var marked = 0;
    for (final notification in _entries) {
      if (!notification.read) {
        notification.read = true;
        marked += 1;
      }
    }
    return marked;
  }

  int clear() {
    final dropped = _entries.length;
    _entries.clear();
    return dropped;
  }

  List<Map<String, dynamic>> toJson() =>
      _entries.map((n) => n.toJson()).toList();

  void restore(List<dynamic> stored) {
    _entries
      ..clear()
      ..addAll(stored
          .whereType<Map<String, dynamic>>()
          .map(MobileNotification.fromJson));
  }
}

/// Diffs consecutive dashboards. The first observation is a silent
/// baseline - opening the app must not replay current state as news.
class DashboardWatcher {
  bool _baselineTaken = false;
  Set<String> _recommendationIds = {};
  Set<String> _disturberIds = {};
  String? _runningEventId;
  String? _executionContext;

  List<MobileNotification> observe(DashboardData dashboard) {
    final at = clock(dashboard.currentTime);
    final recommendationIds =
        dashboard.recommendations.map((r) => r.id).toSet();
    final disturberIds = dashboard.disturbers.map((d) => d.id).toSet();
    final runningId = dashboard.currentEvent?.id;
    final context = dashboard.executionContext;

    final fresh = <MobileNotification>[];
    if (_baselineTaken) {
      for (final recommendation in dashboard.recommendations) {
        if (_recommendationIds.contains(recommendation.id)) continue;
        fresh.add(MobileNotification(
          message: 'Recommendation: ${recommendation.reason}',
          category: 'Recommendation',
          kind: 'info',
          occurredAt: at,
        ));
      }
      for (final disturber in dashboard.disturbers) {
        if (_disturberIds.contains(disturber.id)) continue;
        fresh.add(MobileNotification(
          message:
              'Disturbance: [${disturber.severity}] ${disturber.description}',
          category: 'Disturbance',
          kind: disturber.severity == 'High' ? 'error' : 'warn',
          occurredAt: at,
        ));
      }
      if (runningId != _runningEventId && dashboard.currentEvent != null) {
        fresh.add(MobileNotification(
          message: 'Now running: ${dashboard.currentEvent!.description}',
          category: 'Event',
          kind: 'ok',
          occurredAt: at,
        ));
      }
      if (context != _executionContext && context.isNotEmpty) {
        fresh.add(MobileNotification(
          message: 'Context changed: $context',
          category: 'Context',
          kind: 'info',
          occurredAt: at,
        ));
      }
    }

    _baselineTaken = true;
    _recommendationIds = recommendationIds;
    _disturberIds = disturberIds;
    _runningEventId = runningId;
    _executionContext = context;
    return fresh;
  }
}
