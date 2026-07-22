// Quick Capture (the inbox): brain dump - capture now, organize later.
// A single Enter captures instantly; the assistant then suggests what
// each open item should become ("Suggested: event") with a one-tap
// convert. Swipe right to archive, swipe left to delete (confirmed),
// tap to convert manually. Every action is exactly one endpoint.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import '../services/settings_service.dart';

class InboxScreen extends StatefulWidget {
  final AppState state;
  const InboxScreen({super.key, required this.state});

  @override
  State<InboxScreen> createState() => _InboxScreenState();
}

class _InboxScreenState extends State<InboxScreen> {
  final TextEditingController _capture = TextEditingController();
  List<InboxItem>? items;
  String? error;
  bool _capturing = false;

  /// item text (lowercased) -> suggested kind, from POST /assistant/plan.
  Map<String, String> _suggestions = {};

  @override
  void initState() {
    super.initState();
    reload();
  }

  @override
  void dispose() {
    _capture.dispose();
    super.dispose();
  }

  Future<void> reload() async {
    try {
      final fetched = await widget.state.client.getInbox();
      if (!mounted) return;
      setState(() {
        items = fetched.map(InboxItem.fromJson).toList();
        error = null;
      });
      await widget.state.cachePayload(SettingsService.keyInboxCache, fetched);
      await _suggest();
    } on ApiUnreachableException catch (e) {
      if (!mounted) return;
      final cached = widget.state.cachedPayload(SettingsService.keyInboxCache);
      if (cached is List) {
        setState(() {
          items = cached
              .whereType<Map<String, dynamic>>()
              .map(InboxItem.fromJson)
              .toList();
          error = null;
        });
      } else {
        setState(() => error = 'Server unreachable: ${e.detail}');
      }
    } on ApiResponseException catch (e) {
      if (!mounted) return;
      setState(() => error = e.message);
    }
  }

  /// Asks the assistant what the open items should become. Suggestions
  /// are decoration: any failure just means no chips.
  Future<void> _suggest() async {
    final open =
        (items ?? []).where((item) => item.status == 'open').toList();
    if (open.isEmpty) {
      if (mounted && _suggestions.isNotEmpty) {
        setState(() => _suggestions = {});
      }
      return;
    }
    try {
      final payload = await widget.state.client
          .assistantPlan(open.map((item) => item.text).join('\n'));
      if (!mounted) return;
      final proposals = ProposalItem.listFrom(payload);
      final map = <String, String>{};
      for (final proposal in proposals) {
        final key = (proposal.text.isEmpty ? proposal.title : proposal.text)
            .trim()
            .toLowerCase();
        if (key.isNotEmpty) map[key] = proposal.kind;
      }
      setState(() => _suggestions = map);
    } catch (_) {} // no suggestions offline; the list still works
  }

  String? _suggestionFor(InboxItem item) =>
      _suggestions[item.text.trim().toLowerCase()];

  Future<void> _runAction(
      Future<void> Function() call, String successNotice) async {
    final failure = await widget.state.runAction(call, successNotice);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(failure ?? successNotice)),
    );
    await reload();
  }

  Future<void> _captureNow([String? submitted]) async {
    final text = (submitted ?? _capture.text).trim();
    if (text.isEmpty || _capturing) return;
    setState(() => _capturing = true);
    _capture.clear();
    try {
      await widget.state.client.addInbox(text);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Captured'), duration: Duration(seconds: 1)));
      }
      await reload();
    } on ApiUnreachableException catch (e) {
      _capture.text = text; // give the words back
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Server unreachable: ${e.detail}')));
      }
    } on ApiResponseException catch (e) {
      _capture.text = text;
      if (mounted) {
        ScaffoldMessenger.of(context)
            .showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _capturing = false);
    }
  }

  Future<void> _addViaDialog() async {
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Quick capture'),
        content: TextField(
          controller: controller,
          autofocus: true,
          maxLines: 3,
          minLines: 1,
          decoration:
              const InputDecoration(labelText: 'What is on your mind?'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Capture')),
        ],
      ),
    );
    final text = controller.text.trim();
    if (confirmed != true || text.isEmpty) return;
    await _captureNow(text);
  }

  Future<bool> _confirmDelete(InboxItem item) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete captured item?'),
        content: Text(item.text),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Delete')),
        ],
      ),
    );
    return confirmed == true;
  }

  Future<void> _convertAsSuggested(InboxItem item, String kind) =>
      _runAction(
        () => widget.state.client.convertInbox(item.id, to: kind),
        'Converted to $kind',
      );

  Future<void> _convert(InboxItem item) async {
    final titleController = TextEditingController(text: item.text);
    String kind = _suggestionFor(item) ?? 'event';
    if (kind == 'inbox') kind = 'event';
    final confirmed = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (context) => StatefulBuilder(
        builder: (context, setSheetState) => Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 16,
            bottom: MediaQuery.of(context).viewInsets.bottom + 16,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Convert to…',
                  style: Theme.of(context).textTheme.titleMedium),
              const SizedBox(height: 12),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                      value: 'goal',
                      label: Text('Goal'),
                      icon: Icon(Icons.flag_outlined)),
                  ButtonSegment(
                      value: 'project',
                      label: Text('Project'),
                      icon: Icon(Icons.folder_outlined)),
                  ButtonSegment(
                      value: 'event',
                      label: Text('Event'),
                      icon: Icon(Icons.play_circle_outline)),
                ],
                selected: {kind},
                onSelectionChanged: (selection) =>
                    setSheetState(() => kind = selection.first),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: titleController,
                decoration:
                    const InputDecoration(labelText: 'Title (optional edit)'),
              ),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                      onPressed: () => Navigator.pop(context, false),
                      child: const Text('Cancel')),
                  const SizedBox(width: 8),
                  FilledButton(
                      onPressed: () => Navigator.pop(context, true),
                      child: const Text('Convert')),
                ],
              ),
            ],
          ),
        ),
      ),
    );
    if (confirmed != true) return;
    final title = titleController.text.trim();
    await _runAction(
      () => widget.state.client.convertInbox(item.id,
          to: kind, title: title.isEmpty ? null : title),
      'Converted to $kind',
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: FloatingActionButton(
        tooltip: 'Quick capture',
        onPressed: _addViaDialog,
        child: const Icon(Icons.add),
      ),
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(12, 12, 12, 0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Brain dump — capture now, organize later',
                    style: theme.textTheme.bodySmall
                        ?.copyWith(color: theme.colorScheme.outline)),
                const SizedBox(height: 8),
                TextField(
                  controller: _capture,
                  autofocus: true, // one tap on "Capture" and you type
                  textInputAction: TextInputAction.done,
                  onSubmitted: _captureNow,
                  decoration: InputDecoration(
                    hintText: 'Type and press Enter to capture…',
                    border: const OutlineInputBorder(),
                    isDense: true,
                    suffixIcon: _capturing
                        ? const Padding(
                            padding: EdgeInsets.all(10),
                            child: SizedBox(
                                width: 16,
                                height: 16,
                                child: CircularProgressIndicator(
                                    strokeWidth: 2)),
                          )
                        : IconButton(
                            tooltip: 'Capture',
                            icon: const Icon(Icons.send),
                            onPressed: _captureNow,
                          ),
                  ),
                ),
              ],
            ),
          ),
          Expanded(child: _buildBody(context)),
        ],
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (items == null && error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (items == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(error!, textAlign: TextAlign.center),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: reload,
      child: items!.isEmpty
          ? ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: const [
                Padding(
                  padding: EdgeInsets.all(24),
                  child: Text(
                      'Inbox zero. Type above to capture a thought.',
                      textAlign: TextAlign.center),
                ),
              ],
            )
          : ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: items!.length,
              itemBuilder: (context, index) =>
                  _buildTile(context, items![index]),
            ),
    );
  }

  Widget _buildTile(BuildContext context, InboxItem item) {
    final scheme = Theme.of(context).colorScheme;
    final suggestion = item.status == 'open' ? _suggestionFor(item) : null;
    final convertible =
        suggestion != null && suggestion != 'inbox' && suggestion.isNotEmpty;
    return Dismissible(
      key: ValueKey('inbox-${item.id}'),
      background: Container(
        color: scheme.secondaryContainer,
        alignment: Alignment.centerLeft,
        padding: const EdgeInsets.only(left: 20),
        child:
            Icon(Icons.archive_outlined, color: scheme.onSecondaryContainer),
      ),
      secondaryBackground: Container(
        color: scheme.errorContainer,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: Icon(Icons.delete_outline, color: scheme.onErrorContainer),
      ),
      confirmDismiss: (direction) async =>
          direction == DismissDirection.endToStart
              ? await _confirmDelete(item)
              : true,
      onDismissed: (direction) {
        setState(() => items?.remove(item));
        if (direction == DismissDirection.endToStart) {
          _runAction(
              () => widget.state.client.deleteInbox(item.id), 'Item deleted');
        } else {
          _runAction(() => widget.state.client.archiveInbox(item.id),
              'Item archived');
        }
      },
      child: ListTile(
        leading: Icon(
          item.status == 'converted'
              ? Icons.check_circle_outline
              : item.status == 'archived'
                  ? Icons.archive_outlined
                  : Icons.inbox_outlined,
        ),
        title: Text(item.text),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${item.status}'
              '${item.convertedTo == null ? '' : ' → ${item.convertedTo}'}'
              ' · ${dayTime(item.createdAt)}',
            ),
            if (convertible)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Wrap(
                  spacing: 6,
                  children: [
                    Chip(
                      label: Text('Suggested: $suggestion'),
                      visualDensity: VisualDensity.compact,
                      materialTapTargetSize:
                          MaterialTapTargetSize.shrinkWrap,
                    ),
                    ActionChip(
                      avatar: const Icon(Icons.bolt, size: 16),
                      label: const Text('Convert as suggested'),
                      visualDensity: VisualDensity.compact,
                      onPressed: () =>
                          _convertAsSuggested(item, suggestion),
                    ),
                  ],
                ),
              ),
          ],
        ),
        onTap: item.status == 'open' ? () => _convert(item) : null,
      ),
    );
  }
}
