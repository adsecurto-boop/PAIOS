// Events: create / edit / duplicate plus the lifecycle actions
// (Start / Pause / Resume / Complete / Archive). Swipe left to archive.
// Archive remains the only "delete" for events.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/settings_service.dart';
import '../widgets/event_form.dart';
import 'rest_list_screen.dart';

class EventsScreen extends RestListScreen {
  const EventsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No events. Tap + to create one.';

  @override
  String? get cacheKey => SettingsService.keyEventsCache;

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getEvents();

  @override
  Widget? buildFab(BuildContext context, RestListScreenState screenState) =>
      FloatingActionButton(
        tooltip: 'New event',
        onPressed: () => _create(context, screenState),
        child: const Icon(Icons.add),
      );

  Future<void> _create(
      BuildContext context, RestListScreenState screenState) async {
    final result = await showEventForm(context);
    if (result == null) return;
    await screenState.runAction(
      () => screenState.widget.state.client.createEvent(
        title: result.title,
        suggestedTime: result.suggestedTime,
        priority: result.priority,
        metadata: result.metadata.isEmpty ? null : result.metadata,
      ),
      'Event created',
    );
  }

  Future<void> _edit(BuildContext context, RestListScreenState screenState,
      EventItem event) async {
    final client = screenState.widget.state.client;
    // Prefill from the event plus its metadata record; a missing or
    // failing metadata endpoint just means an emptier form.
    EventMetadata metadata = EventMetadata.empty();
    try {
      metadata = EventMetadata.fromJson(await client.getEventMetadata(event.id));
    } catch (_) {}
    if (!context.mounted) return;
    final result = await showEventForm(
      context,
      heading: 'Edit event',
      submitLabel: 'Save',
      initialTitle: event.description,
      initialSuggestedTime: event.startTime,
      initialMetadata: metadata,
    );
    if (result == null) return;
    await screenState.runAction(
      () => client.editEvent(
        event.id,
        title: result.title,
        suggestedTime: result.suggestedTime,
        priority: result.priority,
        metadata: result.metadata.isEmpty ? null : result.metadata,
      ),
      'Event updated (rescheduled as a new event)',
    );
  }

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final event = EventItem.fromJson(row);
    final client = screenState.widget.state.client;
    return Dismissible(
      key: ValueKey('event-${event.id}'),
      direction: DismissDirection.endToStart,
      background: Container(
        color: Theme.of(context).colorScheme.errorContainer,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        child: Icon(Icons.archive_outlined,
            color: Theme.of(context).colorScheme.onErrorContainer),
      ),
      confirmDismiss: (_) => _confirmArchive(context, event),
      onDismissed: (_) {
        screenState.removeRow(row);
        screenState.runAction(
            () => client.archiveEvent(event.id), 'Event archived');
      },
      child: ListTile(
        title: Text(event.description),
        subtitle: Text('${event.category} Â· ${event.status}'
            '${event.durationMinutes == null ? '' : ' Â· ${event.durationMinutes} min'}'),
        trailing: PopupMenuButton<String>(
          onSelected: (action) async {
            switch (action) {
              case 'start':
                await screenState.runAction(
                    () => client.startEvent(event.id), 'Event started');
              case 'pause':
                await screenState.runAction(
                    () => client.pauseEvent(event.id), 'Event paused');
              case 'resume':
                await screenState.runAction(
                    () => client.resumeEvent(event.id), 'Event resumed');
              case 'complete':
                await _complete(context, screenState, event.id);
              case 'edit':
                await _edit(context, screenState, event);
              case 'duplicate':
                await screenState.runAction(
                    () => client.duplicateEvent(event.id), 'Event duplicated');
              case 'archive':
                await screenState.runAction(
                    () => client.archiveEvent(event.id), 'Event archived');
            }
          },
          itemBuilder: (context) => const [
            PopupMenuItem(value: 'start', child: Text('Start')),
            PopupMenuItem(value: 'pause', child: Text('Pause')),
            PopupMenuItem(value: 'resume', child: Text('Resume')),
            PopupMenuItem(value: 'complete', child: Text('Completeâ€¦')),
            PopupMenuItem(value: 'edit', child: Text('Editâ€¦')),
            PopupMenuItem(value: 'duplicate', child: Text('Duplicate')),
            PopupMenuItem(value: 'archive', child: Text('Archive')),
          ],
        ),
      ),
    );
  }

  Future<bool> _confirmArchive(BuildContext context, EventItem event) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Archive event?'),
        content: Text(event.description),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Archive')),
        ],
      ),
    );
    return confirmed == true;
  }

  Future<void> _complete(BuildContext context,
      RestListScreenState screenState, String id) async {
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Complete event'),
        content: TextField(
          controller: controller,
          decoration:
              const InputDecoration(labelText: 'Actual outcome (optional)'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Complete')),
        ],
      ),
    );
    if (confirmed != true) return;
    final outcome = controller.text.trim();
    await screenState.runAction(
      () => screenState.widget.state.client.completeEvent(id,
          actualOutcome: outcome.isEmpty ? null : outcome),
      'Event completed',
    );
  }
}
