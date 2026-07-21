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

  String get url => 'http://127.0.0.1:${server.port}';

  Future<void> start() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      requests.add('${request.method} ${request.uri.path}');
      final respond = request.response;
      Object payload;
      var status = 200;
      final path = request.uri.path;
      if (path == '/dashboard') {
        payload = dashboardJson();
      } else if (path == '/resources') {
        payload = {'resources': resourcesJson()};
      } else if (path == '/events') {
        payload = {'events': eventsJson()};
      } else if (path == '/events/e1/archive' ||
          path == '/events/e1/start' ||
          path == '/events/e1/pause' ||
          path == '/events/e1/resume' ||
          path == '/events/e1/complete') {
        payload = {'result': path.split('/').last};
      } else if (path == '/recommendations/r1/accept') {
        payload = {'result': 'accepted'};
      } else if (path == '/recommendations/r1/reject') {
        final body = jsonDecode(await utf8.decoder.bind(request).join());
        payload = {'result': 'rejected', 'echo': body};
      } else if (path == '/events/missing/start') {
        status = 404;
        payload = {
          'error': {'type': 'EntityNotFound', 'message': 'missing not found'}
        };
      } else {
        status = 404;
        payload = {
          'error': {'type': 'ApiError', 'message': 'Unknown route: $path'}
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
  });
}
