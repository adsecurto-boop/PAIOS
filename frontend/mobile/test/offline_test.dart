// Offline behaviour: the app survives disconnection, shows the last
// snapshot (cached across restarts), and recovers on reconnect.
import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fixtures.dart';

ApiClient liveClient(String url) => ApiClient(url,
    client: MockClient((request) async {
      if (request.url.path == '/dashboard') {
        return http.Response(jsonEncode(dashboardJson()), 200);
      }
      if (request.url.path == '/resources') {
        return http.Response(jsonEncode({'resources': resourcesJson()}), 200);
      }
      return http.Response(
          jsonEncode({
            'error': {'type': 'ApiError', 'message': 'unknown'}
          }),
          404);
    }));

ApiClient deadClient(String url) => ApiClient(url,
    client: MockClient((request) async =>
        throw http.ClientException('connection refused')));

Future<SettingsService> freshStore() async {
  final store = SettingsService(await SharedPreferences.getInstance());
  return store;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('disconnection flips offline and keeps the snapshot', () async {
    SharedPreferences.setMockInitialValues({});
    final store = await freshStore();
    var dead = false;
    final state = AppState(store,
        clientFactory: (url) => dead ? deadClient(url) : liveClient(url));

    await state.refresh();
    expect(state.online, isTrue);
    expect(state.dashboard, isNotNull);

    // The server disappears.
    dead = true;
    await state.updateSettings(Settings(
        baseUrl: 'http://10.0.0.99:8765',
        refreshSeconds: state.settings.refreshSeconds,
        darkTheme: true));
    expect(state.online, isFalse);
    // Last snapshot survives for display.
    expect(state.dashboard, isNotNull);
    expect(state.dashboard!.currentTime, '2026-07-21T09:00:00');
    state.dispose();
  });

  test('cached dashboard is restored on a fresh start (offline boot)',
      () async {
    SharedPreferences.setMockInitialValues({
      SettingsService.keyDashboardCache: jsonEncode(dashboardJson()),
    });
    final store = await freshStore();
    final state = AppState(store, clientFactory: deadClient);
    // Before any network activity the cache already renders.
    expect(state.dashboard, isNotNull);
    expect(state.dashboard!.goals.first.name, 'Learn Sanskrit');

    await state.refresh(); // fails; must not throw, must keep snapshot
    expect(state.online, isFalse);
    expect(state.dashboard, isNotNull);
    state.dispose();
  });

  test('reconnect flips back online and records a notification', () async {
    SharedPreferences.setMockInitialValues({});
    final store = await freshStore();
    var dead = true;
    final state = AppState(store,
        clientFactory: (url) => dead ? deadClient(url) : liveClient(url));

    await state.refresh();
    expect(state.online, isFalse);

    dead = false;
    await state.updateSettings(Settings(
        baseUrl: 'http://192.168.1.15:8765',
        refreshSeconds: 10,
        darkTheme: true));
    expect(state.online, isTrue);
    final messages = state.center.entries.map((n) => n.message).toList();
    expect(messages, contains('Connected to PAIOS.'));
    expect(messages, contains('Connection lost.'));
    state.dispose();
  });

  test('notification history persists across app restarts', () async {
    SharedPreferences.setMockInitialValues({});
    final store = await freshStore();
    final state = AppState(store, clientFactory: liveClient);
    await state.refresh();
    await state.refresh();
    await state.markAllRead();
    state.dispose();

    final revived = AppState(store, clientFactory: liveClient);
    expect(revived.center.entries, isNotEmpty);
    expect(revived.center.unreadCount, 0); // read state survived
    revived.dispose();
  });
}
