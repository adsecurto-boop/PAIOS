// AppState: the phone's presentation state, nothing else.
//
// Holds the settings, the REST client, the last successful dashboard
// snapshot (cached for offline display), the connection flag, and the
// notification center fed by the dashboard watcher. Polling runs on a
// timer with the configured interval; failures flip `online` and keep
// the last snapshot - the retry IS the next poll. Never throws out of
// refresh(): the mission's "never crash".
import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../models/models.dart';
import 'api_client.dart';
import 'connection_manager.dart';
import 'notification_center.dart';
import 'offline_queue.dart';
import 'settings_service.dart';

/// What [AppState.updateSettings] did, in words the UI can show.
///
/// Saving and reaching the desktop are two different outcomes: settings
/// persist even when the laptop is asleep, and the user is entitled to
/// know that the value is stored regardless.
class SettingsSaveResult {
  final bool saved;
  final bool reachable;
  final String message;
  const SettingsSaveResult({
    required this.saved,
    required this.message,
    this.reachable = false,
  });
}

class AppState extends ChangeNotifier {
  final SettingsService _store;
  Settings settings;
  ApiClient client;

  DashboardData? dashboard;
  List<ResourceItem> resources = [];
  bool? online; // null until the first poll answers
  String? lastError;
  String lastSync = '—';

  /// M25: how the phone is currently reaching PAIOS (LAN / remote /
  /// offline). Set by [resolveConnection] when a resolver is wired,
  /// otherwise mirrors the online flag.
  ConnectionMode connectionMode = ConnectionMode.lan;

  final NotificationCenter center = NotificationCenter();
  final DashboardWatcher _watcher = DashboardWatcher();
  Timer? _timer;

  /// Requests this state has on the wire, and the clients waiting to be
  /// closed until they finish (see [_retire]).
  int _inFlight = 0;
  final List<ApiClient> _retired = [];

  /// The dashboard JSON as last written to the cache. Re-encoding an
  /// unchanged payload on every poll is pure main-isolate work, and the
  /// dashboard is by far the biggest payload the phone handles.
  String? _cachedDashboardJson;

  /// The polling pass in flight, so ticks cannot pile up on each other.
  Future<String?>? _refreshing;

  /// M21: queued /mobile/logs captures, flushed on every successful poll.
  final OfflineQueue queue;

  /// M25 (optional): resolves the best connection (LAN -> Relay ->
  /// Offline). Production wires a ConnectionManager here; tests inject a
  /// client factory instead and leave this null, keeping their path.
  final Future<Connection> Function(Settings settings)? connectionResolver;

  AppState(
    this._store, {
    ApiClient Function(String url)? clientFactory,
    this.connectionResolver,
  })  : settings = _store.read(),
        client = (clientFactory ?? ApiClient.new)(_store.read().baseUrl),
        queue = OfflineQueue(_store),
        _clientFactory = clientFactory ?? ApiClient.new {
    client.authToken = settings.deviceToken;
    _restoreCaches();
  }

  final ApiClient Function(String url) _clientFactory;

  /// The theme, published on its own channel.
  ///
  /// MaterialApp only needs this one bit, but it used to be rebuilt from
  /// the whole AppState — so every poll tick (and every notification)
  /// rebuilt the application root and everything under it. A separate
  /// notifier means the root rebuilds when the theme changes and at no
  /// other time; screen data still flows through AppState as before.
  late final ValueNotifier<bool> darkTheme =
      ValueNotifier<bool>(settings.darkTheme);

  /// Pick the best available path and swap the client to it. No-op when
  /// no resolver is wired (the client factory stays in charge).
  Future<void> resolveConnection() async {
    final resolver = connectionResolver;
    if (resolver == null) return;
    try {
      final connection = await resolver(settings);
      final previous = client;
      client = connection.client;
      client.authToken = settings.deviceToken;
      connectionMode = connection.mode;
      // Swap FIRST, retire second: closing an http.Client aborts every
      // request still on it, and an aborted request surfaces as
      // "unreachable" - a false outage caused by our own bookkeeping.
      _retire(previous);
      notifyListeners();
    } catch (_) {
      // A failed resolve leaves the current client; the next poll retries.
    }
  }

  /// Close a superseded client once nothing of ours is still using it.
  void _retire(ApiClient previous) {
    if (identical(previous, client)) return;
    if (_inFlight > 0) {
      _retired.add(previous);
      return;
    }
    previous.close();
  }

  void _closeRetired() {
    for (final old in _retired) {
      old.close();
    }
    _retired.clear();
  }

  // --- caches (permitted local stores) -----------------------------------

  void _restoreCaches() {
    final cached = _store.readString(SettingsService.keyDashboardCache);
    if (cached != null) {
      try {
        dashboard =
            DashboardData.fromJson(jsonDecode(cached) as Map<String, dynamic>);
      } catch (_) {
        dashboard = null; // a stale/invalid cache is not worth a crash
      }
    }
    final stored = _store.readString(SettingsService.keyNotifications);
    if (stored != null) {
      try {
        center.restore(jsonDecode(stored) as List<dynamic>);
      } catch (_) {}
    }
  }

  Future<void> _persistNotifications() => _store.writeString(
      SettingsService.keyNotifications, jsonEncode(center.toJson()));

  /// Persists the last successful payload of a screen (events, plan,
  /// inbox) so an offline start still renders something.
  Future<void> cachePayload(String key, Object payload) async {
    try {
      await _store.writeString(key, jsonEncode(payload));
    } catch (_) {} // a failed cache write is never worth a crash
  }

  /// The cached payload for [key], or null when absent or unreadable.
  dynamic cachedPayload(String key) {
    final raw = _store.readString(key);
    if (raw == null) return null;
    try {
      return jsonDecode(raw);
    } catch (_) {
      return null;
    }
  }

  // --- polling ------------------------------------------------------------

  /// Pick the path, take one reading, then poll.
  ///
  /// The order matters. Resolving and refreshing used to race: the probe
  /// finished mid-refresh and swapped (and closed) the client the
  /// refresh was using, so a cold start reported "Connection lost" on a
  /// desktop that was answering. Resolve first, then read.
  Future<void> startPolling() async {
    _timer?.cancel();
    await resolveConnection(); // no-op without a resolver
    await refresh();
    _timer = Timer.periodic(
        Duration(seconds: settings.refreshSeconds), (_) => refresh());
  }

  void stopPolling() {
    _timer?.cancel();
    _timer = null;
  }

  /// One polling pass. Returns null when the server answered, otherwise
  /// the failure in the user's words — so a caller that acted on the
  /// user's behalf (Save server) can say what actually happened instead
  /// of leaving the screen silent. Never throws: the mission's "never
  /// crash".
  Future<String?> refresh() {
    // Re-entrancy guard. The poll interval can be shorter than a slow
    // pass (a 5 s tick against two requests that may take 5 s each), and
    // overlapping passes do the same parsing and the same rebuild twice
    // for one screen's worth of data — visible as dropped frames on
    // every tick. A caller arriving mid-pass joins the pass in flight.
    final running = _refreshing;
    if (running != null) return running;
    final pass = _refreshOnce().whenComplete(() => _refreshing = null);
    _refreshing = pass;
    return pass;
  }

  Future<String?> _refreshOnce() async {
    _inFlight++;
    try {
      final raw = await client.getDashboard();
      dashboard = DashboardData.fromJson(raw);
      resources =
          (await client.getResources()).map(ResourceItem.fromJson).toList();
      lastSync = clock(dashboard!.currentTime);
      await _cacheDashboard(raw);
      final fresh = _watcher.observe(dashboard!);
      for (final notification in fresh) {
        center.add(notification);
      }
      if (fresh.isNotEmpty) await _persistNotifications();
      lastError = null;
      _setOnline(true);
      await flushOfflineQueue(); // the server answered; push captures
      return null;
    } on ApiTimeoutException catch (error) {
      lastError = 'the desktop did not answer within'
          ' ${error.waited.inSeconds}s';
      await resolveConnection();
      _setOnline(false);
      return lastError;
    } on ApiUnreachableException catch (error) {
      lastError = error.detail;
      await resolveConnection(); // a dropped LAN may switch to the relay
      _setOnline(false);
      return lastError;
    } on ApiResponseException catch (error) {
      // Server up but refused: keep the snapshot AND keep `online`, the
      // server is demonstrably reachable.
      lastError = '${error.message} (HTTP ${error.status})';
      notifyListeners();
      return lastError;
    } catch (error) {
      lastError = '$error';
      _setOnline(false);
      return lastError;
    } finally {
      _inFlight--;
      if (_inFlight == 0) _closeRetired();
    }
  }

  /// Persist the dashboard snapshot, skipping the encode+write when it
  /// is byte-for-byte what is already stored.
  Future<void> _cacheDashboard(Map<String, dynamic> raw) async {
    final encoded = jsonEncode(raw);
    if (encoded == _cachedDashboardJson) return;
    _cachedDashboardJson = encoded;
    await _store.writeString(SettingsService.keyDashboardCache, encoded);
  }

  void _setOnline(bool value) {
    if (online != value) {
      center.add(MobileNotification(
        message: value ? 'Connected to PAIOS.' : 'Connection lost.',
        category: 'App',
        kind: value ? 'ok' : 'error',
      ));
    }
    online = value;
    // Without a resolver the mode mirrors the online flag (LAN/offline);
    // with one, resolveConnection owns the mode (LAN/remote/offline).
    if (connectionResolver == null) {
      connectionMode = value ? ConnectionMode.lan : ConnectionMode.offline;
    } else if (!value) {
      connectionMode = ConnectionMode.offline;
    }
    notifyListeners();
  }

  // --- offline capture queue (M21) ----------------------------------------

  /// Pushes queued /mobile/logs captures to the desktop. Safe to call
  /// any time: a missing token or unreachable server just leaves the
  /// queue for the next poll (server-side client_id idempotency makes
  /// repeat flushes harmless).
  Future<void> flushOfflineQueue() async {
    if (settings.deviceToken == null) return;
    int flushed;
    try {
      flushed = await queue.flush(client);
    } catch (_) {
      return; // a failed flush is never worth a crash
    }
    if (flushed == 0) return;
    center.add(MobileNotification(
      message: 'Synced $flushed offline capture${flushed == 1 ? '' : 's'}.',
      category: 'App',
      kind: 'ok',
    ));
    await _persistNotifications();
    notifyListeners();
  }

  // --- actions ------------------------------------------------------------

  /// Runs one REST action; returns null on success, the error text on
  /// failure. Refreshes afterwards so every screen sees the new truth.
  Future<String?> runAction(
      Future<void> Function() call, String successNotice) async {
    _inFlight++;
    try {
      await call();
    } on ApiTimeoutException catch (error) {
      _setOnline(false);
      return 'The desktop did not answer within'
          ' ${error.waited.inSeconds}s.';
    } on ApiUnreachableException catch (error) {
      _setOnline(false);
      return 'Server unreachable: ${error.detail}';
    } on ApiResponseException catch (error) {
      return '${error.message} (${error.errorType})';
    } catch (error) {
      return '$error';
    } finally {
      _inFlight--;
      if (_inFlight == 0) _closeRetired();
    }
    center.add(MobileNotification(
        message: successNotice, category: 'App', kind: 'ok'));
    await _persistNotifications();
    await refresh();
    return null;
  }

  // --- notification maintenance ------------------------------------------

  Future<void> markAllRead() async {
    center.markAllRead();
    await _persistNotifications();
    notifyListeners();
  }

  Future<void> clearNotifications() async {
    center.clear();
    await _persistNotifications();
    notifyListeners();
  }

  // --- settings -----------------------------------------------------------

  /// Persist settings, rebuild the connection, and re-check it.
  ///
  /// Returns what happened. Persisting is unconditional and comes first:
  /// a typed address must survive even when the desktop is off, and the
  /// caller must be able to say "Saved" the moment it is on disk rather
  /// than staying silent for the length of a network round trip.
  Future<SettingsSaveResult> updateSettings(Settings updated) async {
    final intervalChanged = updated.refreshSeconds != settings.refreshSeconds;
    settings = updated;
    darkTheme.value = updated.darkTheme;
    try {
      await _store.write(updated);
    } catch (error) {
      notifyListeners();
      return SettingsSaveResult(
          saved: false, message: 'Could not save on this device: $error');
    }
    // Always rebuild the client: saving settings is the user's "try
    // again with these" gesture, even when the URL text is unchanged.
    if (connectionResolver != null) {
      await resolveConnection(); // re-pick LAN/relay with the new settings
    } else {
      final previous = client;
      client = _clientFactory(updated.baseUrl);
      client.authToken = updated.deviceToken; // M21: pairing state follows
      _retire(previous);
    }
    if (intervalChanged && _timer != null) startPolling();
    notifyListeners();
    // Saving settings always re-checks the connection — that is the
    // "Save server" button's contract (and how reconnect is noticed).
    final failure = await refresh();
    return SettingsSaveResult(
      saved: true,
      reachable: failure == null,
      message: failure == null
          ? 'Saved — connected to ${client.baseUrl}.'
          : 'Saved, but the desktop did not answer: $failure',
    );
  }

  @override
  void dispose() {
    stopPolling();
    _closeRetired();
    client.close();
    super.dispose();
  }
}
