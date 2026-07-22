// Canned REST payloads mirroring the M12 serialization contract.

Map<String, dynamic> dashboardJson({
  List<Map<String, dynamic>>? recommendations,
  List<Map<String, dynamic>>? disturbers,
  Map<String, dynamic>? currentEvent,
  String executionContext = 'IdleExecutionContext',
}) =>
    {
      'current_time': '2026-07-21T09:00:00',
      'current_event': currentEvent,
      'current_context': {
        'execution_context': executionContext,
        'reason': 'Waiting',
        'since': '2026-07-21T08:00:00',
        'context_window': null,
      },
      'active_disturbers': disturbers ?? [],
      'recommendations': recommendations ??
          [
            {
              'recommendation_id': 'r1',
              'status': 'Pending',
              'reason': 'Energy is low (10 points); rest to recover',
              'priority': 8.5,
              'confidence_score': 0.9,
              'expires_at': '2026-07-21T10:00:00',
            }
          ],
      'goals': [
        {
          'goal_id': 'g1',
          'user_id': 'u1',
          'name': 'Learn Sanskrit',
          'description': '',
          'status': 'Active',
        }
      ],
      'projects': [
        {
          'project_id': 'p1',
          'user_id': 'u1',
          'name': 'PAIOS',
          'status': 'Active',
          'created_at': '2026-07-01T08:00:00',
          'progress': {'completion_percentage': 40.0, 'velocity': 1.0},
        }
      ],
      'today': {'completed': [], 'running': [], 'upcoming': []},
      'health': {
        'resources': [
          {
            'resource_id': 'res1',
            'type': 'Energy',
            'current_value': 10,
            'unit': 'points',
            'negative_allowed': false,
            'last_updated': '2026-07-21T08:30:00',
          }
        ],
        'habits': [],
      },
      'learning': {
        'latest_insight': null,
        'latest_reflection': {
          'reflection_id': 'ref1',
          'event_id': 'e0',
          'created_at': '2026-07-20T21:00:00',
          'lesson_learned': 'Breaks work',
          'improvement': null,
          'facts': null,
          'confidence': 0.8,
        },
        'last_studied': null,
        'revised_today': 0,
      },
      'system': {
        'scheduler': 'Idle',
        'decision_engine': 'stateless (ready)',
        'kernel': 'Running',
        'operational': true,
        'snapshot_at': '2026-07-21T09:00:00',
        'daemon': null,
      },
    };

List<Map<String, dynamic>> resourcesJson() => [
      {
        'resource_id': 'res1',
        'type': 'Energy',
        'current_value': 10,
        'unit': 'points',
        'negative_allowed': false,
        'last_updated': '2026-07-21T08:30:00',
      },
      {
        'resource_id': 'res2',
        'type': 'Money',
        'current_value': 250.5,
        'unit': 'EUR',
        'negative_allowed': true,
        'last_updated': '2026-07-21T07:00:00',
      },
    ];

List<Map<String, dynamic>> eventsJson() => [
      {
        'event_id': 'e1',
        'user_id': 'u1',
        'description': 'Deep work',
        'category': 'Work',
        'status': 'Ready',
        'start_time': '2026-07-21T10:00:00',
        'end_time': null,
        'duration_minutes': 60,
        'outcome': null,
        'transitions': [
          {'to_state': 'Ready', 'occurred_at': '2026-07-21T09:00:00', 'actor': 'Runtime'},
        ],
      },
    ];

// --- M20 fixtures ----------------------------------------------------------

/// A wider event list for the timeline join: today upcoming (e1),
/// tomorrow (e2), overdue (e3), completed today (e4), running (e5).
List<Map<String, dynamic>> timelineEventsJson() => [
      ...eventsJson(),
      {
        'event_id': 'e2',
        'description': 'Write report',
        'category': 'Work',
        'status': 'Ready',
        'start_time': '2026-07-22T09:00:00',
        'duration_minutes': 45,
      },
      {
        'event_id': 'e3',
        'description': 'Morning run',
        'category': 'Health',
        'status': 'Ready',
        'start_time': '2026-07-21T07:00:00',
        'duration_minutes': 30,
      },
      {
        'event_id': 'e4',
        'description': 'Journal',
        'category': 'Personal',
        'status': 'Completed',
        'start_time': '2026-07-21T06:00:00',
        'end_time': '2026-07-21T06:30:00',
        'duration_minutes': 30,
      },
      {
        'event_id': 'e5',
        'description': 'Review PRs',
        'category': 'Work',
        'status': 'Running',
        'start_time': '2026-07-21T08:30:00',
        'duration_minutes': 60,
      },
    ];

Map<String, dynamic> planJson() => {
      'created_at': '2026-07-21T08:55:00',
      'entries': [
        {
          'event_id': 'e1',
          'planned_start': '2026-07-21T10:00:00',
          'planned_end': '2026-07-21T11:00:00',
          'duration_minutes': 60,
          'priority': 8.0,
          'recommendation_id': 'r1',
        },
        {
          'event_id': 'e2',
          'planned_start': '2026-07-22T09:00:00',
          'planned_end': '2026-07-22T09:45:00',
          'duration_minutes': 45,
          'priority': 6.0,
          'recommendation_id': null,
        },
        {
          'event_id': 'e3',
          'planned_start': '2026-07-21T07:00:00',
          'planned_end': '2026-07-21T07:30:00',
          'duration_minutes': 30,
          'priority': 5.0,
          'recommendation_id': null,
        },
        {
          'event_id': 'e4',
          'planned_start': '2026-07-21T06:00:00',
          'planned_end': '2026-07-21T06:30:00',
          'duration_minutes': 30,
          'priority': 4.0,
          'recommendation_id': null,
        },
        {
          'event_id': 'e5',
          'planned_start': '2026-07-21T08:30:00',
          'planned_end': '2026-07-21T09:30:00',
          'duration_minutes': 60,
          'priority': 7.0,
          'recommendation_id': null,
        },
      ],
    };

Map<String, dynamic> inboxJson() => {
      'items': [
        {
          'id': 'i1',
          'text': 'Buy milk',
          'status': 'open',
          'created_at': '2026-07-21T08:00:00',
          'converted_to': null,
        },
        {
          'id': 'i2',
          'text': 'Plan the summer trip',
          'status': 'converted',
          'created_at': '2026-07-20T19:00:00',
          'converted_to': 'goal:g9',
        },
      ],
    };

Map<String, dynamic> assistantStatusJson() => {
      'provider': 'ollama',
      'available': true,
      'fallback': 'heuristic',
    };

Map<String, dynamic> assistantPlanJson() => {
      'source': 'ollama',
      'answer': 'Sorted your notes into three items.',
      'items': [
        {
          'text': 'finish the quarterly report',
          'kind': 'event',
          'title': 'Finish quarterly report',
          'day_scope': 'today',
          'duplicate_of': null,
          'notes': null,
        },
        {
          'text': 'learn piano someday',
          'kind': 'goal',
          'title': 'Learn piano',
          'day_scope': null,
          'duplicate_of': null,
          'notes': 'Long-term aspiration',
        },
        {
          'text': 'deep work session',
          'kind': 'event',
          'title': 'Deep work',
          'day_scope': 'today',
          'duplicate_of': 'e1',
          'notes': 'Already scheduled',
        },
      ],
      'questions': ['When is the report due?'],
      'confidence': 0.8,
    };

Map<String, dynamic> assistantExplainJson() => {
      'source': 'heuristic',
      'answer': 'A focused morning, then admin.',
      'entries': [
        {
          'event_id': 'e1',
          'title': 'Deep work',
          'planned_start': '2026-07-21T10:00:00',
          'duration_minutes': 60,
          'reason': 'Highest priority; energy is fresh',
        },
      ],
    };

Map<String, dynamic> templatesJson() => {
      'templates': [
        {'template_id': 't1', 'title': 'Morning routine'},
      ],
    };

Map<String, dynamic> eventMetadataJson() => {
      'event_id': 'e1',
      'tags': ['work', 'focus'],
      'deadline': '2026-07-25T23:59:00',
      'energy': 'high',
      'estimated_duration_minutes': 60,
      'depends_on': <String>[],
    };

// --- M21 mobile companion fixtures -----------------------------------------

Map<String, dynamic> mobilePairJson() => {
      'device_id': 'device_abc123',
      'token': 'tok-secret-once',
    };

Map<String, dynamic> mobileTimelineJson() => {
      'server_time': '2026-07-21T09:00:00',
      'day': '2026-07-21',
      'entries': [
        {
          'event_id': 'e1',
          'title': 'Deep work',
          'planned_start': '2026-07-21T10:00:00',
          'duration_minutes': 60,
          'reason': 'Highest priority; energy is fresh',
        },
      ],
    };

List<Map<String, dynamic>> mobileLogsJson() => [
      {
        'id': 'log1',
        'kind': 'journal',
        'text': 'Slept well, good focus',
        'created_at': '2026-07-21T08:00:00',
        'day': '2026-07-21',
        'client_id': null,
      },
      {
        'id': 'log2',
        'kind': 'mood',
        'text': 'Calm',
        'created_at': '2026-07-21T08:05:00',
        'day': '2026-07-21',
        'client_id': 'mob-1-abc',
      },
    ];

Map<String, dynamic> mobileStudyJson() => {
      'knowledge': [
        {
          'knowledge_id': 'k1',
          'user_id': 'u1',
          'domain': 'Languages',
          'topic': 'Sanskrit',
          'concept': 'Sandhi rules',
          'project_id': null,
          'difficulty': 'medium',
          'confidence': 0.6,
          'revision_count': 3,
          'last_revision': '2026-07-20T18:00:00',
          'source': 'book',
          'applied': false,
          'retention_score': 0.7,
        },
      ],
      'study_logs': [
        {
          'id': 'log3',
          'kind': 'study',
          'text': 'Revised sandhi rules for 30 minutes',
          'created_at': '2026-07-20T18:00:00',
          'day': '2026-07-20',
          'client_id': null,
        },
      ],
    };

Map<String, dynamic> assistantQueryJson() => {
      'source': 'llm',
      'adapter': 'ollama',
      'answer': 'Focus on the report first.',
      'bullets': ['Deep work at 10:00', 'Energy is low — schedule a break'],
      'confidence': 0.7,
    };

Map<String, dynamic> createEventResponseJson({String eventId = 'e9'}) => {
      'recommendation': {
        'recommendation_id': 'r9',
        'status': 'Pending',
        'reason': 'Scheduled by request',
        'priority': 5.0,
      },
      'event_id': eventId,
      'materialized': true,
    };
