// AppState uses the injected connection resolver to pick LAN/Relay and
// exposes the mode (M25). Tests without a resolver keep mirroring online.
import 'package:flutter_test/flutter_test.dart';
import 'package:paios_mobile/services/api_client.dart';
import 'package:paios_mobile/services/app_state.dart';
import 'package:paios_mobile/services/connection_manager.dart';
import 'package:paios_mobile/services/settings_service.dart';
import 'package:shared_preferences/shared_preferences.dart';

Future<AppState> buildState({
  Future<Connection> Function(Settings)? resolver,
}) async {
  SharedPreferences.setMockInitialValues({});
  final store = await SettingsService.load();
  return AppState(
    store,
    clientFactory: (url) => ApiClient(url),
    connectionResolver: resolver,
  );
}

void main() {
  test('resolveConnection swaps the client and records the mode', () async {
    final remoteClient = ApiClient('http://relay.local');
    final state = await buildState(
      resolver: (_) async =>
          Connection(remoteClient, ConnectionMode.remote),
    );
    await state.resolveConnection();
    expect(state.connectionMode, ConnectionMode.remote);
    expect(identical(state.client, remoteClient), isTrue);
    state.dispose();
  });

  test('updateSettings re-resolves through the resolver', () async {
    var resolveCount = 0;
    final state = await buildState(
      resolver: (settings) async {
        resolveCount += 1;
        return Connection(
            ApiClient(settings.baseUrl), ConnectionMode.remote);
      },
    );
    await state.updateSettings(
        state.settings.copyWith(relayUrl: 'https://r.example.com'));
    // Saving settings re-picks the connection through the resolver (and
    // the trailing poll re-picks again when it can't reach anything).
    expect(resolveCount, greaterThanOrEqualTo(1));
    state.dispose();
  });

  test('without a resolver the mode mirrors offline', () async {
    final state = await buildState();
    expect(state.connectionMode, ConnectionMode.lan);
    // A failed poll (no server) flips to offline.
    await state.refresh();
    expect(state.online, isFalse);
    expect(state.connectionMode, ConnectionMode.offline);
    state.dispose();
  });
}
