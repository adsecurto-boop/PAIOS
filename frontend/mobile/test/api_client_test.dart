// REST client tests against a real in-process mock server (dart:io
// HttpServer): request routing, JSON decoding, error mapping, and the
// unreachable path.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/api_client.dart';

import 'fixtures.dart';

class MockPaios {
  late HttpServer server;
  final List<String> requests = [];
  final List<String> bodies = [];
  final List<String?> authHeaders = []; // Authorization value per request

  String get url => 'http://127.0.0.1:${server.port}';

  Future<void> start() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      authHeaders.add(request.headers.value('authorization'));
      final body = await utf8.decoder.bind(request).join();
      bodies.add(body);
      final respond = request.response;
      Object payload;
      var status = 200;
      final path = request.uri.path;
      final route = '${request.method} $path';
      if (route == 'GET /dashboard') {
        payload = dashboardJson();
      } else if (route == 'GET /resources') {
        payload = {'resources': resourcesJson()};
      } else if (route == 'GET /events') {
        payload = {'events': eventsJson()};
      } else if (route == 'POST /events/e1/archive' ||
          route == 'POST /events/e1/start' ||
          route == 'POST /events/e1/pause' ||
          route == 'POST /events/e1/resume' ||
          route == 'POST /events/e1/complete') {
        payload = {'result': path.split('/').last};
      } else if (route == 'POST /recommendations/r1/accept') {
        payload = {'result': 'accepted'};
      } else if (route == 'POST /recommendations/r1/reject') {
        payload = {'result': 'rejected', 'echo': jsonDecode(body)};
      } else if (route == 'POST /events/missing/start') {
        status = 404;
        payload = {
          'error': {'type': 'EntityNotFound', 'message': 'missing not found'}
        };
      }
      // --- M20 routes -----------------------------------------------------
      else if (route == 'POST /events') {
        status = 201;
        payload = createEventResponseJson();
      } else if (route == 'PUT /events/e1') {
        payload = createEventResponseJson(eventId: 'e10');
      } else if (route == 'POST /events/e1/duplicate') {
        status = 201;
        payload = createEventResponseJson(eventId: 'e11');
      } else if (route == 'GET /events/e1/metadata') {
        payload = eventMetadataJson();
      } else if (route == 'PUT /events/e1/metadata') {
        payload = {...eventMetadataJson(), ...jsonDecode(body) as Map};
      } else if (route == 'GET /plan') {
        payload = planJson();
      } else if (route == 'GET /inbox') {
        payload = inboxJson();
      } else if (route == 'POST /inbox') {
        status = 201;
        payload = {
          'id': 'i3',
          'text': (jsonDecode(body) as Map)['text'],
          'status': 'open',
        };
      } else if (route == 'POST /inbox/i1/convert') {
        payload = {
          'item': {'id': 'i1', 'status': 'converted'},
          'created': {'event_id': 'e12'},
        };
      } else if (route == 'POST /inbox/i1/archive') {
        payload = {'result': 'archived'};
      } else if (route == 'DELETE /inbox/i1') {
        payload = {'result': 'deleted'};
      } else if (route == 'GET /templates') {
        payload = templatesJson();
      } else if (route == 'POST /templates/t1/instantiate') {
        status = 201;
        payload = createEventResponseJson(eventId: 'e13');
      } else if (route == 'GET /assistant/status') {
        payload = assistantStatusJson();
      } else if (route == 'POST /assistant/plan') {
        payload = assistantPlanJson();
      } else if (route == 'POST /assistant/explain-day') {
        payload = assistantExplainJson();
      } else if (route == 'POST /goals') {
        status = 201;
        payload = {'goal_id': 'g9', 'echo': jsonDecode(body)};
      } else if (route == 'POST /projects') {
        status = 201;
        payload = {'project_id': 'p9', 'echo': jsonDecode(body)};
      }
      // --- M21 mobile companion routes ------------------------------------
      else if (route == 'POST /mobile/pair') {
        final parsed = jsonDecode(body) as Map<String, dynamic>;
        if (parsed['code'] == '123456') {
          status = 201;
          payload = mobilePairJson();
        } else {
          status = 401;
          payload = {
            'error': {'type': 'ApiError', 'message': 'Wrong pairing code.'}
          };
        }
      } else if (route == 'POST /mobile/auth') {
        final parsed = jsonDecode(body) as Map<String, dynamic>;
        if (parsed['token'] == 'tok-secret-once') {
          payload = {'device_id': 'device_abc123', 'valid': true};
        } else {
          status = 401;
          payload = {
            'error': {'type': 'ApiError', 'message': 'Invalid or revoked token'}
          };
        }
      } else if (path.startsWith('/mobile/') &&
          request.headers.value('authorization') != 'Bearer tok-secret-once') {
        status = 401;
        payload = {
          'error': {
            'type': 'ApiError',
            'message': 'Not paired — pair this device from PAIOS on the desktop'
          }
        };
      } else if (route == 'GET /mobile/timeline') {
        payload = mobileTimelineJson();
      } else if (route == 'GET /mobile/tasks') {
        payload = {'server_time': '2026-07-21T09:00:00', 'events': eventsJson()};
      } else if (route == 'POST /mobile/tasks') {
        status = 201;
        payload = createEventResponseJson(eventId: 'e14');
      } else if (route == 'GET /mobile/logs' ||
          route == 'GET /mobile/logs/2026-07-21') {
        payload = {'entries': mobileLogsJson()};
      } else if (route == 'POST /mobile/logs') {
        status = 201;
        final parsed = jsonDecode(body) as Map<String, dynamic>;
        payload = {
          'id': 'log9',
          'kind': parsed['kind'],
          'text': parsed['text'],
          'created_at': '2026-07-21T09:00:00',
          'day': '2026-07-21',
          'client_id': parsed['client_id'],
        };
      } else if (route == 'GET /mobile/study') {
        payload = mobileStudyJson();
      } else if (route == 'POST /mobile/assistant/query') {
        payload = assistantQueryJson();
      } else {
        status = 404;
        payload = {
          'error': {'type': 'ApiError', 'message': 'Unknown route: $route'}
        };
      }
      respond.statusCode = status;
      respond.headers.contentType = ContentType.json;
      respond.write(jsonEncode(payload));
      await respond.close();
    });
  }

  Future<void> stop() => server.close(force: true);
}

void main() {
  late MockPaios mock;
  late ApiClient client;

  setUp(() async {
    mock = MockPaios();
    await mock.start();
    client = ApiClient(mock.url);
  });

  tearDown(() async {
    client.close();
    await mock.stop();
  });

  group('reads', () {
    test('getDashboard returns the payload', () async {
      final dashboard = await client.getDashboard();
      expect(dashboard['current_time'], '2026-07-21T09:00:00');
      expect(mock.requests, contains('GET /dashboard'));
    });

    test('list endpoints unwrap their envelope key', () async {
      expect(await client.getResources(), hasLength(2));
      expect(await client.getEvents(), hasLength(1));
    });
  });

  group('actions call exactly one endpoint each', () {
    test('event lifecycle including archive (M15 endpoint)', () async {
      await client.startEvent('e1');
      await client.pauseEvent('e1');
      await client.resumeEvent('e1');
      await client.completeEvent('e1', actualOutcome: 'done');
      await client.archiveEvent('e1');
      expect(
          mock.requests,
          containsAllInOrder([
            'POST /events/e1/start',
            'POST /events/e1/pause',
            'POST /events/e1/resume',
            'POST /events/e1/complete',
            'POST /events/e1/archive',
          ]));
      expect(mock.requests, hasLength(5));
    });

    test('accept and reject with reason', () async {
      await client.acceptRecommendation('r1');
      await client.rejectRecommendation('r1', reason: 'busy');
      expect(mock.requests, [
        'POST /recommendations/r1/accept',
        'POST /recommendations/r1/reject',
      ]);
    });
  });

  group('M20 event creation and editing', () {
    test('createEvent posts only the fields that were set', () async {
      final result = await client.createEvent(title: 'Write tests');
      expect(result['materialized'], isTrue);
      expect(result['event_id'], 'e9');
      expect(mock.requests, ['POST /events']);
      final body = jsonDecode(mock.bodies.last) as Map<String, dynamic>;
      expect(body, {'title': 'Write tests'});
    });

    test('createEvent forwards metadata when present', () async {
      await client.createEvent(
        title: 'Write tests',
        mode: 'planned',
        suggestedTime: '2026-07-22T09:00:00',
        priority: 7.5,
        metadata: {
          'tags': ['work'],
          'energy': 'high',
          'estimated_duration_minutes': 45,
        },
      );
      final body = jsonDecode(mock.bodies.last) as Map<String, dynamic>;
      expect(body['mode'], 'planned');
      expect(body['suggested_time'], '2026-07-22T09:00:00');
      expect(body['priority'], 7.5);
      expect(body['metadata'],
          {'tags': ['work'], 'energy': 'high', 'estimated_duration_minutes': 45});
    });

    test('editEvent uses PUT and returns the new event id', () async {
      final result = await client.editEvent('e1', title: 'Deep work v2');
      expect(result['event_id'], 'e10');
      expect(mock.requests, ['PUT /events/e1']);
    });

    test('duplicateEvent posts with optional suggested_time', () async {
      await client.duplicateEvent('e1');
      await client.duplicateEvent('e1',
          suggestedTime: '2026-07-23T10:00:00');
      expect(mock.requests, [
        'POST /events/e1/duplicate',
        'POST /events/e1/duplicate',
      ]);
      expect(jsonDecode(mock.bodies[0]), {});
      expect(jsonDecode(mock.bodies[1]),
          {'suggested_time': '2026-07-23T10:00:00'});
    });

    test('metadata endpoints route GET and PUT', () async {
      final record = await client.getEventMetadata('e1');
      expect(record['energy'], 'high');
      final updated =
          await client.setEventMetadata('e1', {'energy': 'low'});
      expect(updated['energy'], 'low');
      expect(mock.requests, [
        'GET /events/e1/metadata',
        'PUT /events/e1/metadata',
      ]);
    });
  });

  group('M20 plan, inbox, templates', () {
    test('getPlan returns the payload with entries', () async {
      final plan = await client.getPlan();
      expect(plan['entries'], hasLength(5));
      expect(mock.requests, ['GET /plan']);
    });

    test('inbox lifecycle: list, add, convert, archive, delete', () async {
      expect(await client.getInbox(), hasLength(2));
      await client.addInbox('Buy oat milk');
      await client.convertInbox('i1', to: 'event', title: 'Buy milk');
      await client.archiveInbox('i1');
      await client.deleteInbox('i1');
      expect(mock.requests, [
        'GET /inbox',
        'POST /inbox',
        'POST /inbox/i1/convert',
        'POST /inbox/i1/archive',
        'DELETE /inbox/i1',
      ]);
      expect(jsonDecode(mock.bodies[1]), {'text': 'Buy oat milk'});
      expect(jsonDecode(mock.bodies[2]),
          {'to': 'event', 'title': 'Buy milk'});
    });

    test('templates list and instantiate', () async {
      expect(await client.getTemplates(), hasLength(1));
      await client.instantiateTemplate('t1',
          suggestedTime: '2026-07-22T07:00:00');
      expect(mock.requests, [
        'GET /templates',
        'POST /templates/t1/instantiate',
      ]);
      expect(jsonDecode(mock.bodies.last),
          {'suggested_time': '2026-07-22T07:00:00'});
    });

    test('createGoal and createProject post to their collections',
        () async {
      await client.createGoal(name: 'Learn piano');
      await client.createProject(name: 'PAIOS', description: 'v2');
      expect(mock.requests, ['POST /goals', 'POST /projects']);
      expect(jsonDecode(mock.bodies[0]), {'name': 'Learn piano'});
      expect(jsonDecode(mock.bodies[1]),
          {'name': 'PAIOS', 'description': 'v2'});
    });
  });

  group('M20 assistant', () {
    test('status, plan and explain-day route correctly', () async {
      final status = await client.assistantStatus();
      expect(status['provider'], 'ollama');
      final plan = await client.assistantPlan('sort my day');
      expect(plan['items'], hasLength(3));
      final day = await client.assistantExplainDay();
      expect(day['entries'], hasLength(1));
      expect(mock.requests, [
        'GET /assistant/status',
        'POST /assistant/plan',
        'POST /assistant/explain-day',
      ]);
      expect(jsonDecode(mock.bodies[1]), {'text': 'sort my day'});
    });
  });

  group('M21 mobile companion', () {
    test('pairDevice posts the code and device name', () async {
      final result = await client.pairDevice('123456', 'Pixel 9');
      expect(result['device_id'], 'device_abc123');
      expect(result['token'], 'tok-secret-once');
      expect(mock.requests, ['POST /mobile/pair']);
      expect(jsonDecode(mock.bodies.last),
          {'code': '123456', 'device_name': 'Pixel 9'});
    });

    test('a wrong code surfaces the 401 message', () async {
      try {
        await client.pairDevice('000000', 'Pixel 9');
        fail('expected ApiResponseException');
      } on ApiResponseException catch (error) {
        expect(error.status, 401);
        expect(error.message, contains('Wrong pairing code'));
      }
    });

    test('validateToken posts the stored token', () async {
      final result = await client.validateToken('tok-secret-once');
      expect(result['valid'], isTrue);
      expect(mock.requests, ['POST /mobile/auth']);
      expect(jsonDecode(mock.bodies.last), {'token': 'tok-secret-once'});
    });

    test('mobile calls carry the bearer token; legacy calls do not',
        () async {
      final paired = ApiClient(mock.url, authToken: 'tok-secret-once');
      await paired.mobileTimeline();
      await paired.getEvents();
      paired.close();
      expect(mock.requests, ['GET /mobile/timeline', 'GET /events']);
      expect(mock.authHeaders, ['Bearer tok-secret-once', null]);
    });

    test('a missing token on a guarded endpoint is a 401', () async {
      expect(
        () => client.mobileTimeline(),
        throwsA(isA<ApiResponseException>()
            .having((e) => e.status, 'status', 401)),
      );
    });

    test('timeline, tasks and study parse their envelopes', () async {
      final paired = ApiClient(mock.url, authToken: 'tok-secret-once');
      final timeline = await paired.mobileTimeline();
      expect(timeline['day'], '2026-07-21');
      expect(timeline['entries'], hasLength(1));
      final tasks = await paired.mobileTasks();
      expect(tasks['events'], hasLength(1));
      final study = await paired.mobileStudy();
      expect(study['knowledge'], hasLength(1));
      expect(study['study_logs'], hasLength(1));
      paired.close();
    });

    test('createMobileTask posts only the fields that were set', () async {
      final paired = ApiClient(mock.url, authToken: 'tok-secret-once');
      final created = await paired.createMobileTask(title: 'Pack bags');
      expect(created['event_id'], 'e14');
      expect(jsonDecode(mock.bodies.last), {'title': 'Pack bags'});
      await paired.createMobileTask(title: 'Pack bags', priority: 7.0);
      expect(jsonDecode(mock.bodies.last),
          {'title': 'Pack bags', 'priority': 7.0});
      paired.close();
    });

    test('mobileLogs routes the optional day segment', () async {
      final paired = ApiClient(mock.url, authToken: 'tok-secret-once');
      expect(await paired.mobileLogs(), hasLength(2));
      expect(await paired.mobileLogs(day: '2026-07-21'), hasLength(2));
      expect(mock.requests,
          ['GET /mobile/logs', 'GET /mobile/logs/2026-07-21']);
      paired.close();
    });

    test('createMobileLog forwards kind, text and client_id', () async {
      final paired = ApiClient(mock.url, authToken: 'tok-secret-once');
      final record = await paired.createMobileLog(
          kind: 'journal', text: 'Good focus', clientId: 'mob-1-abc');
      expect(record['id'], 'log9');
      expect(record['client_id'], 'mob-1-abc');
      expect(jsonDecode(mock.bodies.last),
          {'kind': 'journal', 'text': 'Good focus', 'client_id': 'mob-1-abc'});
      paired.close();
    });

    test('assistantQuery parses source and answer', () async {
      final paired = ApiClient(mock.url, authToken: 'tok-secret-once');
      final answer = await paired.assistantQuery('what first?');
      expect(answer['source'], 'llm');
      expect(answer['answer'], contains('report'));
      expect(answer['bullets'], hasLength(2));
      expect(mock.requests, ['POST /mobile/assistant/query']);
      expect(jsonDecode(mock.bodies.last), {'text': 'what first?'});
      paired.close();
    });
  });

  group('errors', () {
    test('API error payload becomes ApiResponseException', () async {
      try {
        await client.startEvent('missing');
        fail('expected ApiResponseException');
      } on ApiResponseException catch (error) {
        expect(error.status, 404);
        expect(error.errorType, 'EntityNotFound');
        expect(error.message, contains('missing not found'));
      }
    });

    test('unknown route is surfaced with the API message', () async {
      expect(
        () => client.getGoals(),
        throwsA(isA<ApiResponseException>()
            .having((e) => e.status, 'status', 404)),
      );
    });

    test('unreachable server becomes ApiUnreachableException', () async {
      final dead = ApiClient('http://127.0.0.1:9',
          timeout: const Duration(seconds: 2));
      expect(() => dead.getDashboard(),
          throwsA(isA<ApiUnreachableException>()));
      dead.close();
    });

    test('bare host gets an http scheme', () {
      final bare = ApiClient('192.168.1.15:8765');
      expect(bare.baseUrl, 'http://192.168.1.15:8765');
      bare.close();
    });

    test('a timed-out request is ApiTimeout, a subtype of unreachable',
        () async {
      // A server that accepts the connection but never answers is a
      // different fact from an unreachable one — and the fact an AI
      // round trip produces. It must still satisfy the offline path.
      final slow = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      slow.listen((_) {}); // accept, never respond
      final client = ApiClient('http://127.0.0.1:${slow.port}',
          timeout: const Duration(milliseconds: 200));
      try {
        await client.getDashboard();
        fail('expected a timeout');
      } on ApiTimeoutException catch (error) {
        expect(error, isA<ApiUnreachableException>());
        expect(error.waited, const Duration(milliseconds: 200));
      }
      client.close();
      await slow.close(force: true);
    });

    test('normalizeUrl trims, drops trailing slashes and adds the scheme',
        () {
      expect(ApiClient.normalizeUrl('  192.168.1.15:8765/  '),
          'http://192.168.1.15:8765');
      expect(ApiClient.normalizeUrl('https://relay.example.com/'),
          'https://relay.example.com');
    });
  });
}
