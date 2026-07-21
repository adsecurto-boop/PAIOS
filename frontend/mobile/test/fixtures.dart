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
