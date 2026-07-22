// Daily Journal (M21): offline-first capture of journal, mood, energy
// and sleep entries. Every save goes through the OfflineQueue - the
// entry is visible immediately as "pending sync" and reaches the
// desktop on the next successful connection; server-side client_id
// idempotency makes repeated flushes safe. Requires pairing (Settings)
// to sync, but capture itself works fully offline.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/settings_service.dart';

const List<String> journalKinds = ['journal', 'mood', 'energy', 'sleep'];

const Map<String, IconData> logKindIcons = {
  'journal': Icons.menu_book_outlined,
  'mood': Icons.mood_outlined,
  'energy': Icons.bolt_outlined,
  'sleep': Icons.bedtime_outlined,
  'note': Icons.sticky_note_2_outlined,
  'study': Icons.school_outlined,
};

class JournalScreen extends StatefulWidget {
  final AppState state;
  const JournalScreen({super.key, required this.state});

  @override
  State<JournalScreen> createState() => _JournalScreenState();
}

class _JournalScreenState extends State<JournalScreen> {
  final TextEditingController _text = TextEditingController();
  String _kind = 'journal';
  List<LogEntry>? entries;
  String? error;
  bool _saving = false;

  /// The device's local day, matching GET /mobile/logs/{YYYY-MM-DD}.
  static String today() => DateTime.now().toIso8601String().substring(0, 10);

  @override
  void initState() {
    super.initState();
    reload();
  }

  @override
  void dispose() {
    _text.dispose();
    super.dispose();
  }

  Future<void> reload() async {
    try {
      final fetched = await widget.state.client.mobileLogs(day: today());
      if (!mounted) return;
      setState(() {
        entries = fetched.map(LogEntry.fromJson).toList();
        error = null;
      });
      await widget.state
          .cachePayload(SettingsService.keyJournalCache, fetched);
    } on ApiUnreachableException {
      if (!mounted) return;
      final cached =
          widget.state.cachedPayload(SettingsService.keyJournalCache);
      setState(() {
        entries = cached is List
            ? cached
                .whereType<Map<String, dynamic>>()
                .map(LogEntry.fromJson)
                .toList()
            : (entries ?? []);
        error = null; // the offline banner already tells the story
      });
    } on ApiResponseException catch (e) {
      if (!mounted) return;
      setState(() {
        entries ??= [];
        error = e.status == 401
            ? 'Not paired — pair this device in Settings to sync.'
            : e.message;
      });
    }
  }

  /// Queued captures for this screen's kinds the server has not
  /// confirmed yet (dedup by client_id against the fetched entries).
  List<LogEntry> _pendingEntries() {
    final synced = (entries ?? [])
        .map((entry) => entry.clientId)
        .whereType<String>()
        .toSet();
    return widget.state.queue
        .pending()
        .map(LogEntry.fromQueued)
        .where((entry) =>
            journalKinds.contains(entry.kind) &&
            !synced.contains(entry.clientId))
        .toList();
  }

  Future<void> _save() async {
    final text = _text.text.trim();
    if (text.isEmpty || _saving) return;
    setState(() => _saving = true);
    _text.clear();
    await widget.state.queue.enqueue(kind: _kind, text: text);
    if (mounted) setState(() {}); // visible immediately as pending
    await widget.state.flushOfflineQueue(); // no-op while offline
    await reload();
    if (!mounted) return;
    setState(() => _saving = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(widget.state.online == false
          ? 'Saved on this device — will sync when connected'
          : 'Saved'),
      duration: const Duration(seconds: 1),
    ));
  }

  static String _label(String kind) =>
      kind[0].toUpperCase() + kind.substring(1);

  @override
  Widget build(BuildContext context) {
    final pending = _pendingEntries();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              SegmentedButton<String>(
                segments: [
                  for (final kind in journalKinds)
                    ButtonSegment(value: kind, label: Text(_label(kind))),
                ],
                selected: {_kind},
                onSelectionChanged: (selection) =>
                    setState(() => _kind = selection.first),
              ),
              const SizedBox(height: 8),
              TextField(
                controller: _text,
                minLines: 1,
                maxLines: 4,
                textInputAction: TextInputAction.done,
                onSubmitted: (_) => _save(),
                decoration: InputDecoration(
                  hintText: 'Write it down — works offline too…',
                  border: const OutlineInputBorder(),
                  isDense: true,
                  suffixIcon: _saving
                      ? const Padding(
                          padding: EdgeInsets.all(10),
                          child: SizedBox(
                              width: 16,
                              height: 16,
                              child:
                                  CircularProgressIndicator(strokeWidth: 2)),
                        )
                      : IconButton(
                          tooltip: 'Save entry',
                          icon: const Icon(Icons.send),
                          onPressed: _save,
                        ),
                ),
              ),
            ],
          ),
        ),
        Expanded(child: _buildBody(context, pending)),
      ],
    );
  }

  Widget _buildBody(BuildContext context, List<LogEntry> pending) {
    if (entries == null && error == null && pending.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    final theme = Theme.of(context);
    // Pending first (newest capture on top), then today's synced
    // entries newest-first.
    final rows = [
      ...pending.reversed,
      ...(entries ?? []).reversed,
    ];
    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          if (error != null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 4),
              child: Text(error!,
                  style: theme.textTheme.bodySmall
                      ?.copyWith(color: theme.colorScheme.error)),
            ),
          if (rows.isEmpty)
            const Padding(
              padding: EdgeInsets.all(24),
              child: Text('No entries today. Write the first one above.',
                  textAlign: TextAlign.center),
            ),
          for (final entry in rows) _tile(context, entry),
        ],
      ),
    );
  }

  Widget _tile(BuildContext context, LogEntry entry) {
    final scheme = Theme.of(context).colorScheme;
    return ListTile(
      leading: Icon(logKindIcons[entry.kind] ?? Icons.notes_outlined),
      title: Text(entry.text),
      subtitle: Text(entry.pending
          ? '${entry.kind} · pending sync'
          : '${entry.kind} · ${clock(entry.createdAt)}'),
      trailing: entry.pending
          ? Icon(Icons.cloud_upload_outlined, color: scheme.outline)
          : null,
    );
  }
}
