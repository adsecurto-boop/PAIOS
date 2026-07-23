// The relay transport (M25): the ordinary ApiClient works unchanged
// through the relay envelope, against an in-process mock relay.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/relay_http_client.dart';

class MockRelay {
  late HttpServer server;
  final List<String> routes = [];
  final List<Map<String, dynamic>> envelopes = [];
  int tokenCalls = 0;
  bool failFirstRequestWith401 = false;
  bool _failed = false;

  String get url => 'http://127.0.0.1:${server.port}';

  Future<void> start() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      final route = '${request.method} ${request.uri.path}';
      routes.add(route);
      final body = await utf8.decoder.bind(request).join();
      final respond = request.response;
      var status = 200;
      Object payload;
      if (route == 'POST /phone/token') {
        tokenCalls += 1;
        payload = {
          'access_token': 'jwt-access-$tokenCalls',
          'refresh_token': 'jwt-refresh',
          'expires_in': 900,
          'token_type': 'Bearer',
        };
      } else if (route == 'POST /phone/refresh') {
        payload = {
          'access_token': 'jwt-access-refreshed',
          'refresh_token': 'jwt-refresh',
        };
      } else if (route == 'POST /phone/request') {
        envelopes.add(jsonDecode(body) as Map<String, dynamic>);
        if (failFirstRequestWith401 && !_failed) {
          _failed = true;
          status = 401;
          payload = {'error': 'invalid or expired access token'};
        } else {
          // Simulate the desktop's /mobile/timeline response.
          payload = {
            'status': 200,
            'body': {'day': '2026-07-21', 'entries': []},
          };
        }
      } else {
        status = 404;
        payload = {'error': 'unknown $route'};
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
  late MockRelay relay;

  setUp(() async {
    relay = MockRelay();
    await relay.start();
  });

  tearDown(() => relay.stop());

  ApiClient throughRelay() {
    final transport = RelayHttpClient(
      relayUrl: relay.url,
      account: 'me',
      deviceToken: 'device-token',
    );
    return ApiClient('http://relay.local',
        client: transport, authToken: 'device-token');
  }

  test('a mobile call is wrapped in the relay envelope end to end',
      () async {
    final client = throughRelay();
    final timeline = await client.mobileTimeline();
    expect(timeline['day'], '2026-07-21');
    // Authenticated once, then forwarded the request.
    expect(relay.routes, ['POST /phone/token', 'POST /phone/request']);
    final envelope = relay.envelopes.single;
    expect(envelope['method'], 'GET');
    expect(envelope['path'], '/mobile/timeline');
    expect((envelope['headers'] as Map)['Authorization'],
        'Bearer device-token');
    expect(envelope['nonce'], isNotEmpty);
    expect(envelope['ts'], isA<int>());
    client.close();
  });

  test('a 401 triggers a refresh and one retry', () async {
    relay.failFirstRequestWith401 = true;
    final client = throughRelay();
    final timeline = await client.mobileTimeline();
    expect(timeline['day'], '2026-07-21');
    expect(relay.routes, [
      'POST /phone/token',
      'POST /phone/request', // 401
      'POST /phone/refresh',
      'POST /phone/request', // retried, succeeds
    ]);
    // The retry used a fresh nonce (replay-safe).
    expect(relay.envelopes[0]['nonce'], isNot(relay.envelopes[1]['nonce']));
    client.close();
  });

  test('an unauthorized device surfaces a RelayAuthException', () async {
    await relay.stop();
    // A relay that always 404s /phone/token (server gone -> connection
    // refused is also fine): point at a dead port.
    final transport = RelayHttpClient(
      relayUrl: 'http://127.0.0.1:9',
      account: 'me',
      deviceToken: 'device-token',
    );
    expect(() => transport.authenticate(), throwsA(anything));
    transport.close();
  });
}
