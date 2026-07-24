// Auto-selects how the phone reaches PAIOS (M25): LAN -> Relay -> Offline,
// with no user intervention.
//
// On the same Wi-Fi the LAN path is fastest, so it is tried first with a
// short probe. If the laptop is not on this network, remote access (the
// relay) is used when configured. If neither answers, the app goes into
// offline mode (cached data + the offline queue). The chosen mode is
// exposed so the UI can show a calm, non-technical indicator.
import 'package:http/http.dart' as http;

import 'api_client.dart';
import 'relay_http_client.dart';

enum ConnectionMode { lan, remote, offline }

extension ConnectionModeLabel on ConnectionMode {
  /// Plain language for the status pill — never a technical term.
  String get label => switch (this) {
        ConnectionMode.lan => 'On your Wi-Fi',
        ConnectionMode.remote => 'Connected from anywhere',
        ConnectionMode.offline => 'Offline',
      };
}

class Connection {
  final ApiClient client;
  final ConnectionMode mode;
  const Connection(this.client, this.mode);
}

class ConnectionManager {
  final String? lanUrl;
  final String? relayUrl;
  final String account;
  final String? deviceToken;
  final Duration lanProbeTimeout;

  /// Injectable so tests drive the whole selection with no real network.
  final http.Client Function()? httpFactory;

  ConnectionManager({
    this.lanUrl,
    this.relayUrl,
    this.account = 'default',
    this.deviceToken,
    this.lanProbeTimeout = const Duration(seconds: 2),
    this.httpFactory,
  });

  bool get _hasLan => lanUrl != null && lanUrl!.trim().isNotEmpty;

  /// The probe must speak the same dialect as [ApiClient]: the settings
  /// field holds whatever the user typed ("192.168.1.15:8765",
  /// "http://host:8765/"), and probing that text verbatim built an
  /// unusable URI - so a desktop the ApiClient could reach perfectly
  /// well was reported unreachable and the phone fell through to
  /// "Offline".
  String get _probeBase => ApiClient.normalizeUrl(lanUrl!);
  bool get _hasRelay =>
      relayUrl != null &&
      relayUrl!.isNotEmpty &&
      deviceToken != null &&
      deviceToken!.isNotEmpty;

  http.Client _newHttp() => httpFactory?.call() ?? http.Client();

  /// Resolve the best available connection. Never throws — an
  /// unreachable desktop resolves to an offline (cache-backed) client.
  Future<Connection> resolve() async {
    if (_hasLan && await _lanReachable()) {
      return Connection(
        ApiClient(lanUrl!, client: _newHttp(), authToken: deviceToken),
        ConnectionMode.lan,
      );
    }
    if (_hasRelay) {
      try {
        final transport = RelayHttpClient(
          relayUrl: relayUrl!,
          account: account,
          deviceToken: deviceToken!,
          inner: _newHttp(),
        );
        await transport.authenticate();
        return Connection(
          // baseUrl is unused by the relay transport, but ApiClient still
          // builds "<baseUrl><path>" — a harmless placeholder host keeps
          // the paths intact for the envelope to read.
          ApiClient('http://relay.local',
              client: transport, authToken: deviceToken),
          ConnectionMode.remote,
        );
      } on RelayAuthException {
        // Fall through to offline.
      }
    }
    // Offline: an ApiClient pointed at the LAN URL still exists so the UI
    // can retry, but callers rely on the cache while mode == offline.
    return Connection(
      ApiClient(lanUrl ?? 'http://127.0.0.1:8765',
          client: _newHttp(), authToken: deviceToken),
      ConnectionMode.offline,
    );
  }

  Future<bool> _lanReachable() async {
    final http.Client probe = _newHttp();
    try {
      final response = await probe
          .get(Uri.parse('$_probeBase/status'))
          .timeout(lanProbeTimeout);
      return response.statusCode == 200;
    } catch (_) {
      return false;
    } finally {
      probe.close();
    }
  }
}
