// The offline capture queue (M21): enqueue while disconnected, flush
// in order on reconnect. Server-side client_id idempotency makes
// repeated flushes safe, so the queue only has to be conservative:
// keep entries while unreachable or unpaired, never wedge on a bad
// payload. SharedPreferences is mocked (the standard pattern).
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/offline_queue.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fixtures.dart';

/// Records every POST body; answers 201 (or [status] when >= 400).
ApiClient recordingClient(List<String> posts, {int status = 201}) =>
    ApiClient('http://127.0.0.1:1',
        client: MockClient((request) async {
          posts.add(request.body);
          if (status >= 400) {
            return http.Response(
                jsonEncode({
                  'error': {'type': 'ApiError', 'message': 'refused'}
                }),
                status);
          }
          return http.Response(
              jsonEncode({
                ...jsonDecode(request.body) as Map<String, dynamic>,
                'id': 'log9',
              }),
              status);
        }));

ApiClient unreachableClient() => ApiClient('http://127.0.0.1:1',
    client: MockClient((request) async =>
        throw http.ClientException('connection refused')));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  Future<SettingsService> freshStore() async =>
      SettingsService(await SharedPreferences.getInstance());

  test('enqueue persists entries with unique client ids', () async {
    final queue = OfflineQueue(await freshStore());
    final first = await queue.enqueue(kind: 'journal', text: 'one');
    final second = await queue.enqueue(kind: 'study', text: 'two');
    expect(first['client_id'], isA<String>());
    expect(first['client_id'], isNot(second['client_id']));

    // A fresh service over the same prefs still sees the queue.
    final revived = OfflineQueue(await freshStore());
    expect(revived.pending(), hasLength(2));
    expect(revived.pending().first['text'], 'one');
  });

  test('flush posts in order and empties the queue', () async {
    final queue = OfflineQueue(await freshStore());
    await queue.enqueue(kind: 'journal', text: 'one');
    await queue.enqueue(kind: 'study', text: 'two');

    final posts = <String>[];
    final client = recordingClient(posts);
    expect(await queue.flush(client), 2);
    client.close();

    expect(queue.pending(), isEmpty);
    expect(posts, hasLength(2));
    final bodies =
        posts.map((body) => jsonDecode(body) as Map<String, dynamic>);
    expect(bodies.map((body) => body['text']).toList(), ['one', 'two']);
    expect(bodies.map((body) => body['client_id']),
        everyElement(isA<String>()));
  });

  test('an unreachable server keeps every entry', () async {
    final queue = OfflineQueue(await freshStore());
    await queue.enqueue(kind: 'journal', text: 'one');

    final client = unreachableClient();
    expect(await queue.flush(client), 0);
    client.close();
    expect(queue.pending(), hasLength(1));
  });

  test('a 401 keeps entries for after re-pairing', () async {
    final queue = OfflineQueue(await freshStore());
    await queue.enqueue(kind: 'journal', text: 'one');

    final posts = <String>[];
    final client = recordingClient(posts, status: 401);
    expect(await queue.flush(client), 0);
    client.close();
    expect(queue.pending(), hasLength(1)); // waits for a new pairing
  });

  test('a rejected payload is dropped so the queue never wedges',
      () async {
    final queue = OfflineQueue(await freshStore());
    await queue.enqueue(kind: 'journal', text: 'one');
    await queue.enqueue(kind: 'journal', text: 'two');

    final posts = <String>[];
    final client = recordingClient(posts, status: 400);
    expect(await queue.flush(client), 0);
    client.close();
    expect(posts, hasLength(2)); // both were attempted...
    expect(queue.pending(), isEmpty); // ...and both dropped
  });

  test('AppState.refresh flushes the queue after a successful poll',
      () async {
    SharedPreferences.setMockInitialValues({
      'device_token': 'tok-secret-once', // SettingsService's token key
    });
    final store = await freshStore();
    final posted = <String>[];
    final auths = <String?>[];
    ApiClient factory(String url) => ApiClient(url,
        client: MockClient((request) async {
          if (request.url.path == '/dashboard') {
            return http.Response(jsonEncode(dashboardJson()), 200);
          }
          if (request.url.path == '/resources') {
            return http.Response(
                jsonEncode({'resources': resourcesJson()}), 200);
          }
          if (request.url.path == '/mobile/logs' &&
              request.method == 'POST') {
            posted.add(request.body);
            auths.add(request.headers['Authorization']);
            return http.Response(
                jsonEncode({
                  ...jsonDecode(request.body) as Map<String, dynamic>,
                  'id': 'log9',
                }),
                201);
          }
          return http.Response(
              jsonEncode({
                'error': {'type': 'ApiError', 'message': 'unknown'}
              }),
              404);
        }));

    final state = AppState(store, clientFactory: factory);
    await state.queue.enqueue(kind: 'journal', text: 'offline note');
    await state.queue.enqueue(kind: 'study', text: 'sandhi 20 min');
    expect(state.queue.pending(), hasLength(2));

    await state.refresh();
    expect(state.online, isTrue);
    expect(state.queue.pending(), isEmpty);
    expect(posted, hasLength(2));
    expect((jsonDecode(posted.first) as Map)['text'], 'offline note');
    expect(auths, everyElement('Bearer tok-secret-once'));
    final messages = state.center.entries.map((n) => n.message).toList();
    expect(messages, contains('Synced 2 offline captures.'));
    state.dispose();
  });
}
