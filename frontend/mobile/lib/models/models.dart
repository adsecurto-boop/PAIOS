// Typed views over REST payloads. Parsing only - tolerant of absent
// fields, no computation, no domain rules. Field names mirror the M12
// serialization contract verbatim.

String _s(dynamic value, [String fallback = '']) =>
    value is String ? value : fallback;

String? _sOrNull(dynamic value) => value is String ? value : null;

double? _dOrNull(dynamic value) =>
    value is num ? value.toDouble() : null;

int _i(dynamic value, [int fallback = 0]) =>
    value is num ? value.toInt() : fallback;

List<Map<String, dynamic>> _listOfMaps(dynamic value) => value is List
    ? value.whereType<Map<String, dynamic>>().toList()
    : const [];

/// '2026-07-21T09:05:00' -> '09:05'; null-safe.
String clock(String? iso) {
  if (iso == null || iso.isEmpty) return '—';
  final t = iso.contains('T') ? iso.split('T')[1] : iso;
  return t.length >= 5 ? t.substring(0, 5) : t;
}

/// '2026-07-21T09:05:00' -> '2026-07-21 09:05'; null-safe.
String dayTime(String? iso) {
  if (iso == null || iso.isEmpty) return '—';
  final text = iso.replaceFirst('T', ' ');
  return text.length >= 16 ? text.substring(0, 16) : text;
}

List<String> _listOfStrings(dynamic value) =>
    value is List ? value.whereType<String>().toList() : const [];

/// One `/plan` entry: what the scheduler intends to run and when.
class PlanEntry {
  final String eventId;
  final String? plannedStart;
  final String? plannedEnd;
  final int? durationMinutes;
  final double? priority;
  final String? recommendationId;

  PlanEntry.fromJson(Map<String, dynamic> json)
      : eventId = _s(json['event_id']),
        plannedStart = _sOrNull(json['planned_start']),
        plannedEnd = _sOrNull(json['planned_end']),
        durationMinutes = json['duration_minutes'] is num
            ? _i(json['duration_minutes'])
            : null,
        priority = _dOrNull(json['priority']),
        recommendationId = _sOrNull(json['recommendation_id']);

  static List<PlanEntry> listFrom(dynamic payload) =>
      payload is Map<String, dynamic>
          ? _listOfMaps(payload['entries']).map(PlanEntry.fromJson).toList()
          : const [];
}

/// One `/inbox` item: a raw capture awaiting triage.
class InboxItem {
  final String id;
  final String text;
  final String status; // open | converted | archived
  final String? createdAt;
  final String? convertedTo;

  InboxItem.fromJson(Map<String, dynamic> json)
      : id = _s(json['id']),
        text = _s(json['text']),
        status = _s(json['status'], 'open'),
        createdAt = _sOrNull(json['created_at']),
        convertedTo = _sOrNull(json['converted_to']);

  static List<InboxItem> listFrom(dynamic payload) =>
      payload is Map<String, dynamic>
          ? _listOfMaps(payload['items']).map(InboxItem.fromJson).toList()
          : payload is List
              ? payload
                  .whereType<Map<String, dynamic>>()
                  .map(InboxItem.fromJson)
                  .toList()
              : const [];
}

/// The `/events/{id}/metadata` record (all fields optional).
class EventMetadata {
  final List<String> tags;
  final String? deadline;
  final String? energy; // low | medium | high
  final int? estimatedDurationMinutes;
  final List<String> dependsOn;

  EventMetadata.fromJson(Map<String, dynamic> json)
      : tags = _listOfStrings(json['tags']),
        deadline = _sOrNull(json['deadline']),
        energy = _sOrNull(json['energy']),
        estimatedDurationMinutes = json['estimated_duration_minutes'] is num
            ? _i(json['estimated_duration_minutes'])
            : null,
        dependsOn = _listOfStrings(json['depends_on']);

  EventMetadata.empty()
      : tags = const [],
        deadline = null,
        energy = null,
        estimatedDurationMinutes = null,
        dependsOn = const [];
}

/// One assistant proposal from POST /assistant/plan.
class ProposalItem {
  final String text;
  final String kind; // goal | project | event | inbox
  final String title;
  final String? dayScope;
  final String? duplicateOf;
  final String? notes;

  ProposalItem.fromJson(Map<String, dynamic> json)
      : text = _s(json['text']),
        kind = _s(json['kind'], 'inbox'),
        title = _s(json['title'], _s(json['text'])),
        dayScope = _sOrNull(json['day_scope']),
        duplicateOf = _sOrNull(json['duplicate_of']),
        notes = _sOrNull(json['notes']);

  static List<ProposalItem> listFrom(dynamic payload) =>
      payload is Map<String, dynamic>
          ? _listOfMaps(payload['items']).map(ProposalItem.fromJson).toList()
          : const [];
}

/// One explained plan entry from POST /assistant/explain-day.
class DayReason {
  final String eventId;
  final String title;
  final String? plannedStart;
  final int? durationMinutes;
  final String reason;

  DayReason.fromJson(Map<String, dynamic> json)
      : eventId = _s(json['event_id']),
        title = _s(json['title']),
        plannedStart = _sOrNull(json['planned_start']),
        durationMinutes = json['duration_minutes'] is num
            ? _i(json['duration_minutes'])
            : null,
        reason = _s(json['reason']);

  static List<DayReason> listFrom(dynamic payload) =>
      payload is Map<String, dynamic>
          ? _listOfMaps(payload['entries']).map(DayReason.fromJson).toList()
          : const [];
}

class Recommendation {
  final String id;
  final String status;
  final String reason;
  final double? priority;
  final String? expiresAt;

  Recommendation.fromJson(Map<String, dynamic> json)
      : id = _s(json['recommendation_id']),
        status = _s(json['status']),
        reason = _s(json['reason']),
        priority = _dOrNull(json['priority']),
        expiresAt = _sOrNull(json['expires_at']);
}

class EventItem {
  final String id;
  final String description;
  final String category;
  final String status;
  final String? startTime;
  final String? endTime;
  final int? durationMinutes;
  final String? outcome;
  final List<Map<String, dynamic>> transitions;

  EventItem.fromJson(Map<String, dynamic> json)
      : id = _s(json['event_id']),
        description = _s(json['description']),
        category = _s(json['category']),
        status = _s(json['status']),
        startTime = _sOrNull(json['start_time']),
        endTime = _sOrNull(json['end_time']),
        durationMinutes =
            json['duration_minutes'] is num ? _i(json['duration_minutes']) : null,
        outcome = _sOrNull(json['outcome']),
        transitions = _listOfMaps(json['transitions']);
}

class Goal {
  final String id;
  final String name;
  final String description;
  final String status;

  Goal.fromJson(Map<String, dynamic> json)
      : id = _s(json['goal_id']),
        name = _s(json['name']),
        description = _s(json['description']),
        status = _s(json['status']);
}

class Project {
  final String id;
  final String name;
  final String status;
  final double? completion;

  Project.fromJson(Map<String, dynamic> json)
      : id = _s(json['project_id']),
        name = _s(json['name']),
        status = _s(json['status']),
        completion = json['progress'] is Map<String, dynamic>
            ? _dOrNull(
                (json['progress'] as Map<String, dynamic>)['completion_percentage'])
            : null;
}

class ResourceItem {
  final String id;
  final String type;
  final double value;
  final String unit;
  final String? lastUpdated;

  ResourceItem.fromJson(Map<String, dynamic> json)
      : id = _s(json['resource_id']),
        type = _s(json['type']),
        value = _dOrNull(json['current_value']) ?? 0,
        unit = _s(json['unit']),
        lastUpdated = _sOrNull(json['last_updated']);
}

class Reflection {
  final String id;
  final String? createdAt;
  final String? lessonLearned;
  final String? improvement;
  final String? facts;
  final double? confidence;

  Reflection.fromJson(Map<String, dynamic> json)
      : id = _s(json['reflection_id']),
        createdAt = _sOrNull(json['created_at']),
        lessonLearned = _sOrNull(json['lesson_learned']),
        improvement = _sOrNull(json['improvement']),
        facts = _sOrNull(json['facts']),
        confidence = _dOrNull(json['confidence']);
}

class ContextItem {
  final String id;
  final String name;
  final String? location;
  final String? reason;
  final String? environment;

  ContextItem.fromJson(Map<String, dynamic> json)
      : id = _s(json['context_id']),
        name = _s(json['name']),
        location = _sOrNull(json['location']),
        reason = _sOrNull(json['reason']),
        environment = _sOrNull(json['environment']);
}

class Disturber {
  final String id;
  final String type;
  final String severity;
  final String description;
  final String state;

  Disturber.fromJson(Map<String, dynamic> json)
      : id = _s(json['event_disturber_id']),
        type = _s(json['type']),
        severity = _s(json['severity']),
        description = _s(json['description']),
        state = _s(json['state']);
}

class CurrentEvent {
  final String id;
  final String description;
  final String status;
  final String? startedAt;
  final int? elapsedMinutes;
  final int? remainingMinutes;

  CurrentEvent.fromJson(Map<String, dynamic> json)
      : id = _s(json['event_id']),
        description = _s(json['description']),
        status = _s(json['status']),
        startedAt = _sOrNull(json['started_at']),
        elapsedMinutes =
            json['elapsed_minutes'] is num ? _i(json['elapsed_minutes']) : null,
        remainingMinutes = json['remaining_minutes'] is num
            ? _i(json['remaining_minutes'])
            : null;
}

/// The `/dashboard` payload, typed. Every count/grouping arrives from
/// the API; the phone only displays.
class DashboardData {
  final String currentTime;
  final CurrentEvent? currentEvent;
  final String executionContext;
  final String? contextReason;
  final List<Disturber> disturbers;
  final List<Recommendation> recommendations;
  final List<Goal> goals;
  final List<Project> projects;
  final int completedToday;
  final int runningCount;
  final int upcomingCount;
  final List<ResourceItem> healthResources;
  final String? lastStudied;
  final int revisedToday;
  final Map<String, dynamic>? latestInsight;
  final Reflection? latestReflection;
  final String kernel;
  final String scheduler;
  final bool operational;
  final String? snapshotAt;

  DashboardData.fromJson(Map<String, dynamic> json)
      : currentTime = _s(json['current_time']),
        currentEvent = json['current_event'] is Map<String, dynamic>
            ? CurrentEvent.fromJson(
                json['current_event'] as Map<String, dynamic>)
            : null,
        executionContext = json['current_context'] is Map<String, dynamic>
            ? _s((json['current_context']
                as Map<String, dynamic>)['execution_context'])
            : '',
        contextReason = json['current_context'] is Map<String, dynamic>
            ? _sOrNull(
                (json['current_context'] as Map<String, dynamic>)['reason'])
            : null,
        disturbers = _listOfMaps(json['active_disturbers'])
            .map(Disturber.fromJson)
            .toList(),
        recommendations = _listOfMaps(json['recommendations'])
            .map(Recommendation.fromJson)
            .toList(),
        goals = _listOfMaps(json['goals']).map(Goal.fromJson).toList(),
        projects =
            _listOfMaps(json['projects']).map(Project.fromJson).toList(),
        completedToday = json['today'] is Map<String, dynamic>
            ? _listOfMaps((json['today'] as Map<String, dynamic>)['completed'])
                .length
            : 0,
        runningCount = json['today'] is Map<String, dynamic>
            ? _listOfMaps((json['today'] as Map<String, dynamic>)['running'])
                .length
            : 0,
        upcomingCount = json['today'] is Map<String, dynamic>
            ? _listOfMaps((json['today'] as Map<String, dynamic>)['upcoming'])
                .length
            : 0,
        healthResources = json['health'] is Map<String, dynamic>
            ? _listOfMaps((json['health'] as Map<String, dynamic>)['resources'])
                .map(ResourceItem.fromJson)
                .toList()
            : const [],
        lastStudied = json['learning'] is Map<String, dynamic>
            ? _sOrNull(
                (json['learning'] as Map<String, dynamic>)['last_studied'])
            : null,
        revisedToday = json['learning'] is Map<String, dynamic>
            ? _i((json['learning'] as Map<String, dynamic>)['revised_today'])
            : 0,
        latestInsight = json['learning'] is Map<String, dynamic>
            ? ((json['learning'] as Map<String, dynamic>)['latest_insight']
                as Map<String, dynamic>?)
            : null,
        latestReflection = json['learning'] is Map<String, dynamic> &&
                (json['learning'] as Map<String, dynamic>)['latest_reflection']
                    is Map<String, dynamic>
            ? Reflection.fromJson((json['learning']
                as Map<String, dynamic>)['latest_reflection'] as Map<String, dynamic>)
            : null,
        kernel = json['system'] is Map<String, dynamic>
            ? _s((json['system'] as Map<String, dynamic>)['kernel'])
            : '',
        scheduler = json['system'] is Map<String, dynamic>
            ? _s((json['system'] as Map<String, dynamic>)['scheduler'])
            : '',
        operational = json['system'] is Map<String, dynamic> &&
            (json['system'] as Map<String, dynamic>)['operational'] == true,
        snapshotAt = json['system'] is Map<String, dynamic>
            ? _sOrNull((json['system'] as Map<String, dynamic>)['snapshot_at'])
            : null;
}
