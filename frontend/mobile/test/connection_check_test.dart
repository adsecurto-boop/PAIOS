// The staged "Test connection" check: it must name the link that broke
// (desktop / pairing / AI) instead of collapsing every failure into
// "Offline", and the AI stage must run even when the model is slow.
import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/connection_check.dart';

/// A configurable in-process desktop: each stage can be told to succeed,
/// fail, or (the AI) answer deterministically.
class FakeDesktop {
  late HttpServer server;
  bool statusOk = true;
  bool tokenValid = true;
  String aiSource = 'llm';
  int? aiStatus; // when set, the AI route returns this HTTP error

  String get url => 'http://127.0.0.1:${server.port}';

  Future<void> start() async {
    server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    server.listen((request) async {
      final route = '${request.method} ${request.uri.path}';
      final r = request.response;
      r.headers.contentType = ContentType.json;
      if (route == 'GET /status') {
        r.statusCode = statusOk ? 200 : 503;
        r.write(jsonEncode(
            {'state': statusOk ? 'Running' : 'Stopped', 'operational': statusOk}));
      } else if (route == 'POST /mobile/auth') {
        r.statusCode = tokenValid ? 200 : 401;
        r.write(jsonEncode(tokenValid
            ? {'device_id': 'device_1', 'valid': true}
            : {
                'error': {'type': 'ApiError', 'message': 'revoked'}
              }));
      } else if (route == 'POST /mobile/assistant/query') {
        if (aiStatus != null) {
          r.statusCode = aiStatus!;
          r.write(jsonEncode({
            'error': {'type': 'AdapterError', 'message': 'model exploded'}
          }));
        } else {
          r.statusCode = 200;
          r.write(jsonEncode({
            'source': aiSource,
            'answer': aiSource == 'llm' ? 'I am reachable.' : 'Deterministic.',
            'bullets': [],
          }));
        }
      } else {
        r.statusCode = 404;
        r.write(jsonEncode({
          'error': {'type': 'ApiError', 'message': 'no route $route'}
        }));
      }
      await r.close();
    });
  }

  Future<void> stop() => server.close(force: true);
}

void main() {
  late FakeDesktop desktop;

  setUp(() async {
    desktop = FakeDesktop();
    await desktop.start();
  });

  tearDown(() => desktop.stop());

  ApiClient client() =>
      ApiClient(desktop.url, authToken: 'tok', timeout: const Duration(seconds: 5));

  test('all three links green reports connected', () async {
    final c = client();
    final report = await checkConnection(c, deviceToken: 'tok');
    expect(report.connected, isTrue);
    expect(report.steps.map((s) => s.name), ['Desktop', 'Pairing', 'AI']);
    expect(report.firstProblem, isNull);
    c.close();
  });

  test('an unreachable desktop is a Desktop failure, not "Offline"',
      () async {
    final dead = ApiClient('http://127.0.0.1:9',
        authToken: 'tok', timeout: const Duration(seconds: 2));
    final report = await checkConnection(dead, deviceToken: 'tok');
    expect(report.connected, isFalse);
    expect(report.firstProblem!.name, 'Desktop');
    expect(report.summary, isNot(contains('Offline')));
    // The walk stops at the broken link — no false pairing/AI verdicts.
    expect(report.steps, hasLength(1));
    dead.close();
  });

  test('a live desktop with a revoked token blames pairing', () async {
    desktop.tokenValid = false;
    final c = client();
    final report = await checkConnection(c, deviceToken: 'tok');
    expect(report.firstProblem!.name, 'Pairing');
    expect(report.steps.first.ok, isTrue); // desktop was fine
    c.close();
  });

  test('no stored token fails at pairing before any AI call', () async {
    final c = client();
    final report = await checkConnection(c, deviceToken: null);
    expect(report.firstProblem!.name, 'Pairing');
    expect(report.steps.map((s) => s.name), ['Desktop', 'Pairing']);
    c.close();
  });

  test('desktop and pairing fine but no AI is a warning, not a failure',
      () async {
    desktop.aiSource = 'heuristic';
    final c = client();
    final report = await checkConnection(c, deviceToken: 'tok');
    // Heuristic is by design, so the check does not fail — but it is not
    // silent about it either.
    final ai = report.steps.firstWhere((s) => s.name == 'AI');
    expect(ai.status, CheckStatus.warning);
    expect(ai.detail, contains('no AI provider'));
    c.close();
  });

  test('an AI error surfaces the provider error, still not "Offline"',
      () async {
    desktop.aiStatus = 500;
    final c = client();
    final report = await checkConnection(c, deviceToken: 'tok');
    final ai = report.steps.firstWhere((s) => s.name == 'AI');
    expect(ai.status, CheckStatus.failed);
    expect(ai.detail, contains('model exploded'));
    // The earlier links still passed — the desktop is not "offline".
    expect(report.steps.first.ok, isTrue);
    c.close();
  });

  test('a slow model reports an AI timeout, not an unreachable desktop',
      () async {
    // A desktop that answers /status and /mobile/auth immediately but
    // never answers the AI query: the exact shape of a model still
    // loading. Only the AI stage times out.
    final slow = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    slow.listen((request) async {
      final route = '${request.method} ${request.uri.path}';
      final r = request.response;
      r.headers.contentType = ContentType.json;
      if (route == 'GET /status') {
        r.write(jsonEncode({'state': 'Running', 'operational': true}));
        await r.close();
      } else if (route == 'POST /mobile/auth') {
        r.write(jsonEncode({'device_id': 'device_1', 'valid': true}));
        await r.close();
      } // AI route: accepted, never answered
    });
    // A tiny AI deadline stands in for the real 300 s so the test is fast.
    final c = _ShortAiClient('http://127.0.0.1:${slow.port}',
        authToken: 'tok', timeout: const Duration(seconds: 3));
    final report = await checkConnection(c, deviceToken: 'tok');
    expect(report.steps.first.ok, isTrue); // desktop fine
    final ai = report.steps.firstWhere((s) => s.name == 'AI');
    expect(ai.status, CheckStatus.failed);
    expect(ai.detail, contains('still be loading'));
    expect(ai.detail, contains('sent nothing'));
    c.close();
    await slow.close(force: true);
  });
}

/// An ApiClient whose assistant deadline is short, so the slow-model test
/// does not wait the real five minutes. It overrides nothing else.
class _ShortAiClient extends ApiClient {
  _ShortAiClient(super.url, {super.authToken, super.timeout});

  @override
  Future<Map<String, dynamic>> assistantQuery(String text) async {
    // Route through the same transport but with a 500 ms AI deadline.
    // ignore: invalid_use_of_visible_for_testing_member
    return await requestForTest(
        'POST', '/mobile/assistant/query', {'text': text},
        const Duration(milliseconds: 500)) as Map<String, dynamic>;
  }
}
