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
import 'notification_center.dart';
import 'settings_service.dart';

class AppState extends ChangeNotifier {
  final SettingsService _store;
  Settings settings;
  ApiClient client;

  DashboardData? dashboard;
  List<ResourceItem> resources = [];
  bool? online; // null until the first poll answers
  String? lastError;
  String lastSync = '—';

  final NotificationCenter center = NotificationCenter();
  final DashboardWatcher _watcher = DashboardWatcher();
  Timer? _timer;

  AppState(this._store, {ApiClient Function(String url)? clientFactory})
      : settings = _store.read(),
        client = (clientFactory ?? ApiClient.new)(_store.read().baseUrl),
        _clientFactory = clientFactory ?? ApiClient.new {
    _restoreCaches();
  }

  final ApiClient Function(String url) _clientFactory;

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

  void startPolling() {
    _timer?.cancel();
    _timer = Timer.periodic(
        Duration(seconds: settings.refreshSeconds), (_) => refresh());
  }

  void stopPolling() {
    _timer?.cancel();
    _timer = null;
  }

  Future<void> refresh() async {
    try {
      final raw = await client.getDashboard();
      dashboard = DashboardData.fromJson(raw);
      resources =
          (await client.getResources()).map(ResourceItem.fromJson).toList();
      lastSync = clock(dashboard!.currentTime);
      await _store.writeString(
          SettingsService.keyDashboardCache, jsonEncode(raw));
      final fresh = _watcher.observe(dashboard!);
      for (final notification in fresh) {
        center.add(notification);
      }
      if (fresh.isNotEmpty) await _persistNotifications();
      _setOnline(true);
    } on ApiUnreachableException catch (error) {
      lastError = error.detail;
      _setOnline(false);
    } on ApiResponseException catch (error) {
      lastError = error.message; // server up but refused; keep snapshot
      notifyListeners();
    } catch (error) {
      lastError = '$error';
      _setOnline(false);
    }
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
    notifyListeners();
  }

  // --- actions ------------------------------------------------------------

  /// Runs one REST action; returns null on success, the error text on
  /// failure. Refreshes afterwards so every screen sees the new truth.
  Future<String?> runAction(
      Future<void> Function() call, String successNotice) async {
    try {
      await call();
    } on ApiUnreachableException catch (error) {
      _setOnline(false);
      return 'Server unreachable: ${error.detail}';
    } on ApiResponseException catch (error) {
      return '${error.message} (${error.errorType})';
    } catch (error) {
      return '$error';
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

  Future<void> updateSettings(Settings updated) async {
    final urlChanged = updated.baseUrl != settings.baseUrl;
    final intervalChanged = updated.refreshSeconds != settings.refreshSeconds;
    settings = updated;
    await _store.write(updated);
    if (urlChanged) {
      client.close();
      client = _clientFactory(updated.baseUrl);
    }
    if (intervalChanged && _timer != null) startPolling();
    notifyListeners();
    if (urlChanged) await refresh();
  }

  @override
  void dispose() {
    stopPolling();
    client.close();
    super.dispose();
  }
}
