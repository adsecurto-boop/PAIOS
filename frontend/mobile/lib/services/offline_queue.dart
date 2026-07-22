// M21 offline-first capture: a persisted FIFO of POST /mobile/logs
// payloads.
//
// Journal and study captures must never fail: while the desktop is
// unreachable the payload waits here (shared_preferences JSON - sync
// state, not domain state). Every entry carries a generated client_id;
// the server treats a repeated client_id as the original record, so
// flushing the queue twice is harmless by contract.
import 'dart:convert';
import 'dart:math';

import 'api_client.dart';
import 'settings_service.dart';

class OfflineQueue {
  final SettingsService _store;

  OfflineQueue(this._store);

  static final Random _random = Random();

  /// 'mob-<epoch millis>-<random hex>' - unique enough for one device,
  /// no uuid dependency (pubspec stays unchanged).
  static String newClientId(DateTime now) =>
      'mob-${now.millisecondsSinceEpoch}-'
      '${_random.nextInt(0xFFFFFF).toRadixString(16).padLeft(6, '0')}';

  bool get isEmpty => pending().isEmpty;

  /// The queued payloads, oldest first; [] when absent or unreadable
  /// (a corrupt queue is never worth a crash).
  List<Map<String, dynamic>> pending() {
    final raw = _store.readString(SettingsService.keyOfflineQueue);
    if (raw == null) return [];
    try {
      final decoded = jsonDecode(raw);
      return decoded is List
          ? decoded.whereType<Map<String, dynamic>>().toList()
          : [];
    } catch (_) {
      return [];
    }
  }

  Future<void> _save(List<Map<String, dynamic>> entries) => _store.writeString(
      SettingsService.keyOfflineQueue, jsonEncode(entries));

  /// Queues one capture and returns it (with its fresh client_id) so
  /// the screen can render it immediately as "pending sync".
  Future<Map<String, dynamic>> enqueue({
    required String kind,
    required String text,
    String? at,
  }) async {
    final entry = <String, dynamic>{
      'kind': kind,
      'text': text,
      if (at != null) 'at': at,
      'client_id': newClientId(DateTime.now()),
    };
    await _save(pending()..add(entry));
    return entry;
  }

  /// Sends the queue in order; returns how many entries the server
  /// accepted. Stops (keeping the rest) while the server is
  /// unreachable or the device is not paired (401); drops an entry the
  /// server rejects outright so one bad payload can never wedge the
  /// queue - idempotency makes the retry semantics safe either way.
  Future<int> flush(ApiClient client) async {
    var entries = pending();
    var accepted = 0;
    while (entries.isNotEmpty) {
      final entry = entries.first;
      try {
        await client.createMobileLog(
          kind: entry['kind'] as String? ?? 'journal',
          text: entry['text'] as String? ?? '',
          at: entry['at'] as String?,
          clientId: entry['client_id'] as String?,
        );
        accepted += 1;
      } on ApiUnreachableException {
        break; // still offline - the next poll retries
      } on ApiResponseException catch (error) {
        if (error.status == 401) break; // not paired; keep for later
        // Any other refusal is about this payload itself: drop it.
      }
      entries = entries.sublist(1);
      await _save(entries);
    }
    return accepted;
  }
}
