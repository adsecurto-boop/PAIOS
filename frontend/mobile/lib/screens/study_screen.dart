// Study (M21): the desktop's knowledge base plus a quick "log study
// session" capture (kind=study). Reading needs the connection (with an
// offline cache of the last payload); logging a session is
// offline-first via the OfflineQueue, exactly like the journal.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/settings_service.dart';

class StudyScreen extends StatefulWidget {
  final AppState state;
  const StudyScreen({super.key, required this.state});

  @override
  State<StudyScreen> createState() => _StudyScreenState();
}

class _StudyScreenState extends State<StudyScreen> {
  final TextEditingController _text = TextEditingController();
  List<KnowledgeItem>? knowledge;
  List<LogEntry>? studyLogs;
  String? error;
  bool _saving = false;

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

  static List<KnowledgeItem> _parseKnowledge(dynamic value) => value is List
      ? value
          .whereType<Map<String, dynamic>>()
          .map(KnowledgeItem.fromJson)
          .toList()
      : [];

  static List<LogEntry> _parseLogs(dynamic value) => value is List
      ? value
          .whereType<Map<String, dynamic>>()
          .map(LogEntry.fromJson)
          .toList()
      : [];

  Future<void> reload() async {
    try {
      final payload = await widget.state.client.mobileStudy();
      if (!mounted) return;
      setState(() {
        knowledge = _parseKnowledge(payload['knowledge']);
        studyLogs = _parseLogs(payload['study_logs']);
        error = null;
      });
      await widget.state.cachePayload(SettingsService.keyStudyCache, payload);
    } on ApiUnreachableException {
      if (!mounted) return;
      final cached = widget.state.cachedPayload(SettingsService.keyStudyCache);
      setState(() {
        if (cached is Map<String, dynamic>) {
          knowledge = _parseKnowledge(cached['knowledge']);
          studyLogs = _parseLogs(cached['study_logs']);
        } else {
          knowledge ??= [];
          studyLogs ??= [];
        }
        error = null; // the offline banner already tells the story
      });
    } on ApiResponseException catch (e) {
      if (!mounted) return;
      setState(() {
        knowledge ??= [];
        studyLogs ??= [];
        error = e.status == 401
            ? 'Not paired — pair this device in Settings to sync.'
            : e.message;
      });
    }
  }

  /// Queued study captures the server has not confirmed yet.
  List<LogEntry> _pendingEntries() {
    final synced = (studyLogs ?? [])
        .map((entry) => entry.clientId)
        .whereType<String>()
        .toSet();
    return widget.state.queue
        .pending()
        .map(LogEntry.fromQueued)
        .where((entry) =>
            entry.kind == 'study' && !synced.contains(entry.clientId))
        .toList();
  }

  Future<void> _logSession() async {
    final text = _text.text.trim();
    if (text.isEmpty || _saving) return;
    setState(() => _saving = true);
    _text.clear();
    await widget.state.queue.enqueue(kind: 'study', text: text);
    if (mounted) setState(() {}); // visible immediately as pending
    await widget.state.flushOfflineQueue(); // no-op while offline
    await reload();
    if (!mounted) return;
    setState(() => _saving = false);
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(widget.state.online == false
          ? 'Logged on this device — will sync when connected'
          : 'Study session logged'),
      duration: const Duration(seconds: 1),
    ));
  }

  @override
  Widget build(BuildContext context) {
    final pending = _pendingEntries();
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          child: TextField(
            controller: _text,
            minLines: 1,
            maxLines: 3,
            textInputAction: TextInputAction.done,
            onSubmitted: (_) => _logSession(),
            decoration: InputDecoration(
              hintText: 'Log a study session — works offline too…',
              border: const OutlineInputBorder(),
              isDense: true,
              suffixIcon: _saving
                  ? const Padding(
                      padding: EdgeInsets.all(10),
                      child: SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2)),
                    )
                  : IconButton(
                      tooltip: 'Log session',
                      icon: const Icon(Icons.send),
                      onPressed: _logSession,
                    ),
            ),
          ),
        ),
        Expanded(child: _buildBody(context, pending)),
      ],
    );
  }

  Widget _buildBody(BuildContext context, List<LogEntry> pending) {
    if (knowledge == null && error == null && pending.isEmpty) {
      return const Center(child: CircularProgressIndicator());
    }
    final theme = Theme.of(context);
    final logs = [...pending.reversed, ...(studyLogs ?? []).reversed];
    final items = knowledge ?? [];
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
          _header(context, 'Study log'),
          if (logs.isEmpty)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 4, 16, 4),
              child: Text('No study sessions yet. Log one above.'),
            ),
          for (final entry in logs) _logTile(context, entry),
          _header(context, 'Knowledge'),
          if (items.isEmpty)
            const Padding(
              padding: EdgeInsets.fromLTRB(16, 4, 16, 4),
              child: Text('No knowledge tracked yet.'),
            ),
          for (final item in items) _knowledgeTile(context, item),
        ],
      ),
    );
  }

  Widget _header(BuildContext context, String text) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
        child: Text(
          text.toUpperCase(),
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: Theme.of(context).colorScheme.outline,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.2,
              ),
        ),
      );

  Widget _logTile(BuildContext context, LogEntry entry) {
    final scheme = Theme.of(context).colorScheme;
    return ListTile(
      leading: const Icon(Icons.school_outlined),
      title: Text(entry.text),
      subtitle: Text(entry.pending
          ? 'pending sync'
          : dayTime(entry.createdAt)),
      trailing: entry.pending
          ? Icon(Icons.cloud_upload_outlined, color: scheme.outline)
          : null,
    );
  }

  Widget _knowledgeTile(BuildContext context, KnowledgeItem item) => ListTile(
        leading: const Icon(Icons.psychology_outlined),
        title: Text(item.concept.isEmpty
            ? item.topic
            : '${item.topic} — ${item.concept}'),
        subtitle: Text(
          '${item.domain.isEmpty ? 'General' : item.domain}'
          ' · revised ${item.revisionCount}×'
          '${item.difficulty == null ? '' : ' · ${item.difficulty}'}'
          '${item.retentionScore == null ? '' : ' · retention ${item.retentionScore!.toStringAsFixed(2)}'}',
        ),
      );
}
