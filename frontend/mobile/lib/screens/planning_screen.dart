// Planning: a conversational front door. Type what needs to happen,
// tap "Plan it", review the assistant's proposal cards, Approve.
// The assistant lives on the server (POST /assistant/plan); the phone
// only previews proposals and, on Approve, executes each checked card
// through the ordinary REST endpoints - one call per item.
//
// Extra AI actions: "Explain My Schedule" (POST /assistant/explain-day)
// and "Review Today" (a presentation-only summary computed from the
// cached /dashboard and /events payloads - no endpoint).
import 'dart:async';

import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/settings_service.dart';
import '../widgets/event_progress.dart';
import '../widgets/today_header.dart';

class PlanningScreen extends StatefulWidget {
  final AppState state;

  /// Injectable clock for tests (Review Today does date arithmetic).
  final DateTime Function()? now;

  const PlanningScreen({super.key, required this.state, this.now});

  @override
  State<PlanningScreen> createState() => _PlanningScreenState();
}

/// A proposal plus its local UI state (checked, kind override).
class _Proposal {
  final ProposalItem item;
  String kind;
  bool checked;

  _Proposal(this.item)
      : kind = item.kind,
        checked = item.duplicateOf == null; // duplicates start unchecked
}

/// The Review Today summary (computed locally, purely presentational).
class _Review {
  final List<String> completed;
  final List<String> overdue;
  final List<String> upcoming;
  const _Review(this.completed, this.overdue, this.upcoming);
}

const List<String> _kinds = ['goal', 'project', 'event', 'inbox'];

const Set<String> _terminal = {
  'completed',
  'archived',
  'cancelled',
  'failed',
  'skipped',
};

class _PlanningScreenState extends State<PlanningScreen> {
  final TextEditingController _text = TextEditingController();
  List<_Proposal> _proposals = [];
  List<String> _questions = [];
  String? _answer;
  double? _confidence;
  bool _proposing = false;
  bool _applying = false;
  bool _explaining = false;
  List<DayReason> _dayReasons = [];
  String? _dayAnswer;
  bool _explained = false;
  _Review? _review;
  String? _assistantNote; // provider/fallback, purely informative

  // Today header data: the plan joined with events, plus the
  // scheduler's explanations (all fetched read-only, cached offline).
  List<PlanEntry> _plan = [];
  Map<String, EventItem> _events = {};
  List<DayReason> _headerReasons = [];
  Timer? _ticker;

  DateTime get _now => (widget.now ?? DateTime.now)();

  @override
  void initState() {
    super.initState();
    _loadStatus();
    _loadToday();
    if (widget.now == null) {
      // Display-only tick for the countdown/progress in the header.
      _ticker = Timer.periodic(const Duration(seconds: 30), (_) {
        if (mounted) setState(() {});
      });
    }
  }

  @override
  void dispose() {
    _ticker?.cancel();
    _text.dispose();
    super.dispose();
  }

  /// Fills the Today header: /plan + /events (falling back to the
  /// offline cache), then the explain-day reasons. Never throws.
  Future<void> _loadToday() async {
    try {
      final plan = await widget.state.client.getPlan();
      final events = await widget.state.client.getEvents();
      if (!mounted) return;
      setState(() {
        _plan = PlanEntry.listFrom(plan);
        _events = {
          for (final event in events.map(EventItem.fromJson)) event.id: event
        };
      });
      await widget.state.cachePayload(SettingsService.keyPlanCache, plan);
      await widget.state.cachePayload(SettingsService.keyEventsCache, events);
    } catch (_) {
      final plan = widget.state.cachedPayload(SettingsService.keyPlanCache);
      final events =
          widget.state.cachedPayload(SettingsService.keyEventsCache);
      if (!mounted) return;
      setState(() {
        _plan = PlanEntry.listFrom(plan);
        _events = events is List
            ? {
                for (final event in events
                    .whereType<Map<String, dynamic>>()
                    .map(EventItem.fromJson))
                  event.id: event
              }
            : {};
      });
    }
    try {
      final payload = await widget.state.client.assistantExplainDay();
      if (!mounted) return;
      setState(() => _headerReasons = DayReason.listFrom(payload));
    } catch (_) {} // reasons are decoration; the header still works
  }

  // --- Today header view data ----------------------------------------------

  List<String> _reasonsFor(String eventId) {
    for (final reason in _headerReasons) {
      if (reason.eventId == eventId && reason.reason.isNotEmpty) {
        return reason.reason
            .split('; ')
            .map((part) => part.trim())
            .where((part) => part.isNotEmpty)
            .toList();
      }
    }
    return const [];
  }

  String _planTitle(PlanEntry entry) {
    final event = _events[entry.eventId];
    return event == null || event.description.isEmpty
        ? entry.eventId
        : event.description;
  }

  TodayEntryView _plannedView(PlanEntry entry, DateTime start, DateTime now,
          {bool withClock = false}) =>
      TodayEntryView(
        title: _planTitle(entry),
        startsInMinutes: start.difference(now).inMinutes,
        startClock: withClock ? clock(entry.plannedStart) : null,
        reasons: _reasonsFor(entry.eventId),
      );

  Widget _todayHeader(BuildContext context) {
    final now = _now;
    EventItem? running;
    for (final event in _events.values) {
      if (event.status.toLowerCase() == 'running') {
        running = event;
        break;
      }
    }
    // Upcoming plan entries, soonest first, terminal states excluded.
    final upcoming = <(PlanEntry, DateTime)>[];
    for (final entry in _plan) {
      final start = entry.plannedStart == null
          ? null
          : DateTime.tryParse(entry.plannedStart!);
      final status =
          (_events[entry.eventId]?.status ?? '').toLowerCase();
      if (start != null && start.isAfter(now) && !_terminal.contains(status)) {
        upcoming.add((entry, start));
      }
    }
    upcoming.sort((a, b) => a.$2.compareTo(b.$2));

    TodayEntryView? focus;
    TodayEntryView? next;
    if (running != null) {
      PlanEntry? entry;
      for (final candidate in _plan) {
        if (candidate.eventId == running.id) {
          entry = candidate;
          break;
        }
      }
      final duration = entry?.durationMinutes ?? running.durationMinutes;
      focus = TodayEntryView(
        title:
            running.description.isEmpty ? running.id : running.description,
        running: true,
        progress: eventProgress(
            startedIso: running.startTime ?? entry?.plannedStart,
            durationMinutes: duration,
            now: now),
        remainingMinutes: eventRemainingMinutes(
            startedIso: running.startTime ?? entry?.plannedStart,
            durationMinutes: duration,
            now: now),
        reasons: _reasonsFor(running.id),
      );
      if (upcoming.isNotEmpty) {
        next = _plannedView(upcoming.first.$1, upcoming.first.$2, now,
            withClock: true);
      }
    } else if (upcoming.isNotEmpty) {
      focus = _plannedView(upcoming.first.$1, upcoming.first.$2, now);
      if (upcoming.length > 1) {
        next = _plannedView(upcoming[1].$1, upcoming[1].$2, now,
            withClock: true);
      }
    }
    return TodayHeader(now: now, focus: focus, next: next);
  }

  Future<void> _loadStatus() async {
    try {
      final status = await widget.state.client.assistantStatus();
      if (!mounted) return;
      final provider = status['provider'];
      final available = status['available'] == true;
      final fallback = status['fallback'];
      setState(() {
        _assistantNote = available
            ? 'Assistant: $provider'
            : 'Assistant: ${fallback ?? 'heuristic'} (fallback)';
      });
    } catch (_) {} // the note is decoration; silence is fine offline
  }

  void _snack(String message, {VoidCallback? retry}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(
      content: Text(message),
      action: retry == null
          ? null
          : SnackBarAction(label: 'Retry', onPressed: retry),
    ));
  }

  Future<void> _propose() async {
    final text = _text.text.trim();
    if (text.isEmpty || _proposing) return;
    setState(() => _proposing = true);
    try {
      final payload = await widget.state.client.assistantPlan(text);
      if (!mounted) return;
      setState(() {
        _proposals =
            ProposalItem.listFrom(payload).map(_Proposal.new).toList();
        _questions = payload['questions'] is List
            ? (payload['questions'] as List).whereType<String>().toList()
            : [];
        _answer =
            payload['answer'] is String ? payload['answer'] as String : null;
        _confidence = payload['confidence'] is num
            ? (payload['confidence'] as num).toDouble()
            : null;
      });
    } on ApiUnreachableException catch (e) {
      _snack('Server unreachable: ${e.detail}', retry: _propose);
    } on ApiResponseException catch (e) {
      _snack(e.message, retry: _propose);
    } catch (e) {
      _snack('$e');
    } finally {
      if (mounted) setState(() => _proposing = false);
    }
  }

  /// Approve: executes each checked proposal through its ordinary
  /// endpoint - exactly one REST call per item.
  Future<void> _approve() async {
    final chosen = _proposals.where((p) => p.checked).toList();
    if (chosen.isEmpty || _applying) return;
    setState(() => _applying = true);
    final client = widget.state.client;
    var applied = 0;
    final failedTitles = <String>{};
    String? firstError;
    for (final proposal in chosen) {
      try {
        switch (proposal.kind) {
          case 'goal':
            await client.createGoal(name: proposal.item.title);
          case 'project':
            await client.createProject(name: proposal.item.title);
          case 'event':
            await client.createEvent(title: proposal.item.title);
          default: // inbox
            await client.addInbox(proposal.item.title);
        }
        applied++;
      } catch (e) {
        failedTitles.add(proposal.item.title);
        firstError ??= '$e';
      }
    }
    if (mounted) {
      setState(() {
        _applying = false;
        if (failedTitles.isEmpty) {
          _proposals = [];
          _questions = [];
          _answer = null;
          _text.clear();
        } else {
          // Keep only the failed cards so a retry is one tap away.
          _proposals.removeWhere(
              (p) => p.checked && !failedTitles.contains(p.item.title));
        }
      });
      _snack(failedTitles.isEmpty
          ? 'Planned $applied item${applied == 1 ? '' : 's'}'
          : 'Planned $applied of ${chosen.length} — $firstError');
    }
    await widget.state.refresh();
  }

  Future<void> _explainDay() async {
    if (_explaining) return;
    setState(() => _explaining = true);
    try {
      final payload = await widget.state.client.assistantExplainDay();
      if (!mounted) return;
      setState(() {
        _dayReasons = DayReason.listFrom(payload);
        _dayAnswer =
            payload['answer'] is String ? payload['answer'] as String : null;
        _explained = true;
        _review = null; // one result panel at a time
      });
    } on ApiUnreachableException catch (e) {
      _snack('Server unreachable: ${e.detail}', retry: _explainDay);
    } on ApiResponseException catch (e) {
      _snack(e.message, retry: _explainDay);
    } catch (e) {
      _snack('$e');
    } finally {
      if (mounted) setState(() => _explaining = false);
    }
  }

  /// Review Today: no endpoint, no domain logic - just counts over the
  /// cached /dashboard and /events payloads.
  void _reviewToday() {
    final now = _now;
    final cached =
        widget.state.cachedPayload(SettingsService.keyEventsCache);
    final events = cached is List
        ? cached
            .whereType<Map<String, dynamic>>()
            .map(EventItem.fromJson)
            .toList()
        : <EventItem>[];
    bool sameDay(DateTime a) =>
        a.year == now.year && a.month == now.month && a.day == now.day;
    final completed = <String>[];
    final overdue = <String>[];
    final upcoming = <String>[];
    for (final event in events) {
      final status = event.status.toLowerCase();
      final start = event.startTime == null
          ? null
          : DateTime.tryParse(event.startTime!);
      if (status == 'completed') {
        final end =
            event.endTime == null ? null : DateTime.tryParse(event.endTime!);
        if ((end != null && sameDay(end)) || (start != null && sameDay(start))) {
          completed.add(event.description);
        }
      } else if (!_terminal.contains(status) && start != null) {
        if (start.isBefore(now)) {
          overdue.add(event.description);
        } else {
          upcoming.add(event.description);
        }
      }
    }
    setState(() {
      _review = _Review(completed, overdue, upcoming);
      _explained = false;
      _dayReasons = [];
      _dayAnswer = null;
    });
  }

  void _cycleKind(_Proposal proposal) {
    final index = _kinds.indexOf(proposal.kind);
    setState(() => proposal.kind = _kinds[(index + 1) % _kinds.length]);
  }

  IconData _kindIcon(String kind) {
    switch (kind) {
      case 'goal':
        return Icons.flag_outlined;
      case 'project':
        return Icons.folder_outlined;
      case 'event':
        return Icons.play_circle_outline;
      default:
        return Icons.inbox_outlined;
    }
  }

  /// Ambiguity questions rendered inline under the card they concern
  /// (matched by title words); the rest go to a general list.
  List<String> _questionsFor(_Proposal proposal) {
    final words = proposal.item.title
        .toLowerCase()
        .split(RegExp(r'[^a-z0-9]+'))
        .where((word) => word.length > 3)
        .toSet();
    return _questions.where((question) {
      final lower = question.toLowerCase();
      return words.any(lower.contains);
    }).toList();
  }

  List<String> get _generalQuestions {
    final matched = <String>{};
    for (final proposal in _proposals) {
      matched.addAll(_questionsFor(proposal));
    }
    return _questions.where((q) => !matched.contains(q)).toList();
  }

  Widget _sectionLabel(BuildContext context, String text) => Text(
        text,
        style: Theme.of(context).textTheme.labelMedium?.copyWith(
              color: Theme.of(context).colorScheme.outline,
              fontWeight: FontWeight.bold,
              letterSpacing: 1.2,
            ),
      );

  Widget _busyIcon(bool busy, IconData idle) => busy
      ? const SizedBox(
          width: 16,
          height: 16,
          child: CircularProgressIndicator(strokeWidth: 2))
      : Icon(idle, size: 18);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final checkedCount = _proposals.where((p) => p.checked).length;
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        // --- today header: greeting, focus, up next ------------------------
        _todayHeader(context),
        const SizedBox(height: 4),
        // --- conversational capture ----------------------------------------
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('What needs to happen?',
                    style: theme.textTheme.titleMedium),
                if (_assistantNote != null) ...[
                  const SizedBox(height: 2),
                  Text(_assistantNote!, style: theme.textTheme.bodySmall),
                ],
                const SizedBox(height: 12),
                TextField(
                  controller: _text,
                  minLines: 3,
                  maxLines: 8,
                  textInputAction: TextInputAction.newline,
                  decoration: const InputDecoration(
                    hintText: 'What do you want to accomplish today?',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                SizedBox(
                  width: double.infinity,
                  child: FilledButton.icon(
                    onPressed: _proposing ? null : _propose,
                    icon: _busyIcon(_proposing, Icons.auto_awesome),
                    label: const Text('Plan it'),
                  ),
                ),
              ],
            ),
          ),
        ),
        // --- proposal preview cards -----------------------------------------
        if (_answer != null && _answer!.isNotEmpty)
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 10, 4, 0),
            child: Text(_answer!, style: theme.textTheme.bodyMedium),
          ),
        if (_proposals.isNotEmpty) ...[
          Padding(
            padding: const EdgeInsets.fromLTRB(4, 14, 4, 4),
            child: _sectionLabel(
                context,
                'PROPOSAL'
                '${_confidence == null ? '' : ' · CONFIDENCE ${(_confidence! * 100).round()}%'}'),
          ),
          for (final proposal in _proposals)
            _proposalCard(context, proposal),
          if (_generalQuestions.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(4, 12, 4, 4),
              child: _sectionLabel(context, 'OPEN QUESTIONS'),
            ),
            for (final question in _generalQuestions)
              ListTile(
                dense: true,
                leading: const Icon(Icons.help_outline, size: 18),
                title: Text(question),
              ),
          ],
          const SizedBox(height: 8),
          SizedBox(
            width: double.infinity,
            child: FilledButton.icon(
              onPressed: checkedCount == 0 || _applying ? null : _approve,
              icon: _busyIcon(_applying, Icons.done_all),
              label: Text('Approve ($checkedCount)'),
            ),
          ),
        ],
        // --- AI actions -------------------------------------------------------
        const SizedBox(height: 16),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _sectionLabel(context, 'AI ACTIONS'),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    OutlinedButton.icon(
                      onPressed: _explaining ? null : _explainDay,
                      icon: _busyIcon(_explaining, Icons.wb_sunny_outlined),
                      label: const Text('Explain My Schedule'),
                    ),
                    OutlinedButton.icon(
                      onPressed: _reviewToday,
                      icon: const Icon(Icons.fact_check_outlined, size: 18),
                      label: const Text('Review Today'),
                    ),
                  ],
                ),
                if (_dayAnswer != null && _dayAnswer!.isNotEmpty) ...[
                  const SizedBox(height: 10),
                  Text(_dayAnswer!, style: theme.textTheme.bodyMedium),
                ],
                if (_explained && _dayReasons.isEmpty) ...[
                  const SizedBox(height: 8),
                  const Text('Nothing on the plan yet.'),
                ],
                for (final reason in _dayReasons)
                  Padding(
                    padding: const EdgeInsets.only(top: 10),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        SizedBox(
                          width: 52,
                          child: Text(clock(reason.plannedStart),
                              style: theme.textTheme.titleSmall),
                        ),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(reason.title,
                                  style: theme.textTheme.titleSmall),
                              Text(
                                '${reason.reason}'
                                '${reason.durationMinutes == null ? '' : ' · ${reason.durationMinutes} min'}',
                                style: theme.textTheme.bodySmall,
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                if (_review != null) _reviewPanel(context, _review!),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _proposalCard(BuildContext context, _Proposal proposal) {
    final theme = Theme.of(context);
    final inlineQuestions = _questionsFor(proposal);
    return Card(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          CheckboxListTile(
            value: proposal.checked,
            onChanged: (value) =>
                setState(() => proposal.checked = value == true),
            controlAffinity: ListTileControlAffinity.leading,
            title: Text(proposal.item.title),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (proposal.item.notes != null &&
                    proposal.item.notes!.isNotEmpty)
                  Padding(
                    padding: const EdgeInsets.only(top: 2),
                    child: Text(proposal.item.notes!,
                        style: theme.textTheme.bodySmall),
                  ),
                const SizedBox(height: 4),
                Wrap(
                  spacing: 6,
                  runSpacing: 4,
                  children: [
                    ActionChip(
                      avatar: Icon(_kindIcon(proposal.kind), size: 16),
                      label: Text(proposal.kind),
                      tooltip: 'Tap to change kind',
                      visualDensity: VisualDensity.compact,
                      onPressed: () => _cycleKind(proposal),
                    ),
                    if (proposal.item.dayScope != null)
                      Chip(
                        label: Text(proposal.item.dayScope!),
                        visualDensity: VisualDensity.compact,
                        materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                      ),
                    if (proposal.item.duplicateOf != null)
                      Chip(
                        avatar: const Icon(Icons.copy_all, size: 14),
                        label: const Text('duplicate'),
                        visualDensity: VisualDensity.compact,
                        materialTapTargetSize:
                            MaterialTapTargetSize.shrinkWrap,
                        backgroundColor: theme.colorScheme.errorContainer,
                      ),
                  ],
                ),
              ],
            ),
          ),
          for (final question in inlineQuestions)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
              child: Row(
                children: [
                  const Icon(Icons.help_outline, size: 16),
                  const SizedBox(width: 6),
                  Expanded(
                    child:
                        Text(question, style: theme.textTheme.bodySmall),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _reviewPanel(BuildContext context, _Review review) {
    final theme = Theme.of(context);
    Widget group(String label, List<String> names, IconData icon) => Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, size: 16),
                  const SizedBox(width: 6),
                  Text('$label (${names.length})',
                      style: theme.textTheme.titleSmall),
                ],
              ),
              for (final name in names.take(5))
                Padding(
                  padding: const EdgeInsets.only(left: 22, top: 2),
                  child: Text(name, style: theme.textTheme.bodySmall),
                ),
            ],
          ),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const SizedBox(height: 4),
        if (review.completed.isEmpty &&
            review.overdue.isEmpty &&
            review.upcoming.isEmpty)
          const Padding(
            padding: EdgeInsets.only(top: 10),
            child: Text('No cached events to review yet — '
                'pull to refresh once you are online.'),
          )
        else ...[
          group('Completed today', review.completed,
              Icons.check_circle_outline),
          group('Overdue', review.overdue, Icons.warning_amber_outlined),
          group('Upcoming', review.upcoming, Icons.upcoming_outlined),
        ],
      ],
    );
  }
}
