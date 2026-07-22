// Timeline: the /plan entries joined with /events, bucketed into
// Today / Tomorrow / Week / Agenda. Pure presentation - the plan is
// computed on the server; the phone only renders it (plus a ticking
// progress bar for the running event, display only).
import 'dart:async';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/settings_service.dart';
import '../widgets/event_progress.dart';

const Set<String> _terminalStatuses = {
  'completed',
  'archived',
  'cancelled',
  'failed',
  'skipped',
};

class TimelineScreen extends StatefulWidget {
  final AppState state;

  /// Injectable clock for tests; when set, the periodic display tick is
  /// disabled and this function is the single source of "now".
  final DateTime Function()? now;

  const TimelineScreen({super.key, required this.state, this.now});

  @override
  State<TimelineScreen> createState() => _TimelineScreenState();
}

class _TimelineScreenState extends State<TimelineScreen> {
  List<PlanEntry>? entries;
  Map<String, EventItem> eventsById = {};
  String? error;
  String _bucket = 'today';
  Timer? _ticker;

  DateTime get _now => (widget.now ?? DateTime.now)();

  @override
  void initState() {
    super.initState();
    reload();
    if (widget.now == null) {
      // Display-only tick: refresh progress bars and countdowns.
      _ticker = Timer.periodic(const Duration(seconds: 30), (_) {
        if (mounted) setState(() {});
      });
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  Future<void> reload() async {
    try {
      final plan = await widget.state.client.getPlan();
      final events = await widget.state.client.getEvents();
      if (!mounted) return;
      setState(() {
        entries = PlanEntry.listFrom(plan);
        eventsById = {
          for (final event in events.map(EventItem.fromJson)) event.id: event
        };
        error = null;
      });
      await widget.state.cachePayload(SettingsService.keyPlanCache, plan);
      await widget.state.cachePayload(SettingsService.keyEventsCache, events);
    } on ApiUnreachableException catch (e) {
      if (!mounted) return;
      if (!_restoreFromCache()) {
        setState(() => error = 'Server unreachable: ${e.detail}');
      }
    } on ApiResponseException catch (e) {
      if (!mounted) return;
      setState(() => error = e.message);
    }
  }

  bool _restoreFromCache() {
    final plan = widget.state.cachedPayload(SettingsService.keyPlanCache);
    final events = widget.state.cachedPayload(SettingsService.keyEventsCache);
    if (plan is! Map<String, dynamic>) return false;
    setState(() {
      entries = PlanEntry.listFrom(plan);
      eventsById = events is List
          ? {
              for (final event in events
                  .whereType<Map<String, dynamic>>()
                  .map(EventItem.fromJson))
                event.id: event
            }
          : {};
      error = null;
    });
    return true;
  }

  // --- bucketing (pure date arithmetic, no domain logic) ------------------

  DateTime? _start(PlanEntry entry) =>
      entry.plannedStart == null ? null : DateTime.tryParse(entry.plannedStart!);

  DateTime? _end(PlanEntry entry) =>
      entry.plannedEnd == null ? null : DateTime.tryParse(entry.plannedEnd!);

  bool _sameDay(DateTime a, DateTime b) =>
      a.year == b.year && a.month == b.month && a.day == b.day;

  String _statusOf(PlanEntry entry) =>
      eventsById[entry.eventId]?.status ?? '';

  bool _isTerminal(PlanEntry entry) =>
      _terminalStatuses.contains(_statusOf(entry).toLowerCase());

  bool _isOverdue(PlanEntry entry) {
    final end = _end(entry);
    return end != null && end.isBefore(_now) && !_isTerminal(entry);
  }

  bool _isCompletedToday(PlanEntry entry) {
    final start = _start(entry);
    return _statusOf(entry).toLowerCase() == 'completed' &&
        start != null &&
        _sameDay(start, _now);
  }

  bool _inBucket(PlanEntry entry) {
    final start = _start(entry);
    if (start == null) return _bucket == 'agenda';
    final now = _now;
    final today = DateTime(now.year, now.month, now.day);
    switch (_bucket) {
      case 'today':
        return _sameDay(start, now);
      case 'tomorrow':
        return _sameDay(start, today.add(const Duration(days: 1)));
      case 'week':
        return !start.isBefore(today) &&
            start.isBefore(today.add(const Duration(days: 7)));
      default: // agenda: everything, sorted
        return true;
    }
  }

  List<PlanEntry> _sorted(Iterable<PlanEntry> source) {
    final list = source.toList();
    list.sort((a, b) =>
        (a.plannedStart ?? '').compareTo(b.plannedStart ?? ''));
    return list;
  }

  PlanEntry? _nextUpcoming() {
    final upcoming = _sorted((entries ?? []).where((entry) {
      final start = _start(entry);
      return start != null && start.isAfter(_now) && !_isTerminal(entry);
    }));
    return upcoming.isEmpty ? null : upcoming.first;
  }

  String _countdown(PlanEntry entry) {
    final start = _start(entry);
    if (start == null) return '';
    final delta = start.difference(_now);
    final hours = delta.inHours;
    final minutes = delta.inMinutes % 60;
    return hours > 0 ? 'in ${hours}h ${minutes}m' : 'in ${minutes}m';
  }

  // --- rendering ------------------------------------------------------------

  @override
  Widget build(BuildContext context) {
    if (entries == null && error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (entries == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(error!, textAlign: TextAlign.center),
        ),
      );
    }
    final all = entries!;
    final running = _sorted(all.where(
        (entry) => _statusOf(entry).toLowerCase() == 'running'));
    final nowEntry = running.isEmpty ? null : running.first;
    final overdue = _sorted(all.where(
        (entry) => _isOverdue(entry) && entry != nowEntry));
    final completed = _sorted(all.where(_isCompletedToday));
    final main = _sorted(all.where((entry) =>
        _inBucket(entry) &&
        entry != nowEntry &&
        !_isOverdue(entry) &&
        !_isCompletedToday(entry)));
    final next = _nextUpcoming();

    return RefreshIndicator(
      onRefresh: reload,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12),
            child: SegmentedButton<String>(
              segments: const [
                ButtonSegment(value: 'today', label: Text('Today')),
                ButtonSegment(value: 'tomorrow', label: Text('Tomorrow')),
                ButtonSegment(value: 'week', label: Text('Week')),
                ButtonSegment(value: 'agenda', label: Text('Agenda')),
              ],
              selected: {_bucket},
              onSelectionChanged: (selection) =>
                  setState(() => _bucket = selection.first),
            ),
          ),
          if (nowEntry != null) _nowCard(context, nowEntry),
          if (next != null) ...[
            _sectionHeader(context, 'NEXT'),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 0),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Chip(
                  avatar: const Icon(Icons.timer_outlined, size: 16),
                  label: Text(
                      '${_titleOf(next)} — ${_countdown(next)}'),
                ),
              ),
            ),
          ],
          if (main.isEmpty && nowEntry == null)
            Padding(
              padding: const EdgeInsets.all(24),
              child: Text(_emptyText(), textAlign: TextAlign.center),
            )
          else if (main.isNotEmpty) ...[
            _sectionHeader(context, 'UPCOMING'),
            for (final entry in main) _entryCard(context, entry),
          ],
          if (overdue.isNotEmpty) ...[
            _sectionHeader(context, 'OVERDUE'),
            for (final entry in overdue) _entryCard(context, entry),
          ],
          if (completed.isNotEmpty) ...[
            _sectionHeader(context, 'COMPLETED TODAY'),
            for (final entry in completed) _entryCard(context, entry),
          ],
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
            child: Text(
              'Schedule is controlled by the PAIOS Scheduler',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.outline,
                  ),
            ),
          ),
        ],
      ),
    );
  }

  /// The large NOW card: the running event with a live progress bar and
  /// remaining-time countdown (display only; the tick is cosmetic).
  Widget _nowCard(BuildContext context, PlanEntry entry) {
    final theme = Theme.of(context);
    final scheme = theme.colorScheme;
    final event = eventsById[entry.eventId];
    final startedIso = event?.startTime ?? entry.plannedStart;
    final progress = eventProgress(
        startedIso: startedIso,
        durationMinutes: entry.durationMinutes,
        now: _now);
    final remaining = eventRemainingMinutes(
        startedIso: startedIso,
        durationMinutes: entry.durationMinutes,
        now: _now);
    return Card(
      margin: const EdgeInsets.fromLTRB(12, 10, 12, 5),
      color: scheme.primaryContainer,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('NOW',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: scheme.onPrimaryContainer,
                  fontWeight: FontWeight.bold,
                  letterSpacing: 1.2,
                )),
            const SizedBox(height: 4),
            Text(_titleOf(entry),
                style: theme.textTheme.titleLarge
                    ?.copyWith(color: scheme.onPrimaryContainer)),
            const SizedBox(height: 4),
            Text(
              '${clock(entry.plannedStart)}–${clock(entry.plannedEnd)}'
              '${remaining == null ? '' : ' · $remaining min left'}',
              style: theme.textTheme.bodyMedium
                  ?.copyWith(color: scheme.onPrimaryContainer),
            ),
            if (progress != null) ...[
              const SizedBox(height: 10),
              LinearProgressIndicator(value: progress),
            ],
          ],
        ),
      ),
    );
  }

  String _emptyText() {
    switch (_bucket) {
      case 'today':
        return 'Nothing planned for today.';
      case 'tomorrow':
        return 'Nothing planned for tomorrow.';
      case 'week':
        return 'Nothing planned this week.';
      default:
        return 'The plan is empty.';
    }
  }

  Widget _sectionHeader(BuildContext context, String text) => Padding(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 4),
        child: Text(
          text,
          style: Theme.of(context).textTheme.labelMedium?.copyWith(
                color: Theme.of(context).colorScheme.outline,
                fontWeight: FontWeight.bold,
                letterSpacing: 1.2,
              ),
        ),
      );

  String _titleOf(PlanEntry entry) {
    final event = eventsById[entry.eventId];
    return event == null || event.description.isEmpty
        ? entry.eventId
        : event.description;
  }

  Widget _entryCard(BuildContext context, PlanEntry entry) {
    final event = eventsById[entry.eventId];
    final status = _statusOf(entry);
    final running = status.toLowerCase() == 'running';
    final progress = running
        ? eventProgress(
            startedIso: event?.startTime ?? entry.plannedStart,
            durationMinutes: entry.durationMinutes,
            now: _now)
        : null;
    final range = _bucket == 'today' || _bucket == 'tomorrow'
        ? '${clock(entry.plannedStart)}–${clock(entry.plannedEnd)}'
        : '${dayTime(entry.plannedStart)} – ${clock(entry.plannedEnd)}';
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(_titleOf(entry),
                      style: Theme.of(context).textTheme.titleSmall),
                ),
                if (status.isNotEmpty)
                  Chip(
                    label: Text(status),
                    visualDensity: VisualDensity.compact,
                    materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                  ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '$range'
              '${entry.durationMinutes == null ? '' : ' · ${entry.durationMinutes} min'}'
              '${entry.priority == null ? '' : ' · priority ${entry.priority!.toStringAsFixed(1)}'}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            if (progress != null) ...[
              const SizedBox(height: 8),
              LinearProgressIndicator(value: progress),
            ],
          ],
        ),
      ),
    );
  }
}
