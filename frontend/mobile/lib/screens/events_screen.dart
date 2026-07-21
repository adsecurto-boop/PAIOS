// Events: Start / Pause / Resume / Complete / Archive.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import 'rest_list_screen.dart';

class EventsScreen extends RestListScreen {
  const EventsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No events.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getEvents();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final event = EventItem.fromJson(row);
    final client = screenState.widget.state.client;
    return ListTile(
      title: Text(event.description),
      subtitle: Text('${event.category} · ${event.status}'
          '${event.durationMinutes == null ? '' : ' · ${event.durationMinutes} min'}'),
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
            case 'archive':
              await screenState.runAction(
                  () => client.archiveEvent(event.id), 'Event archived');
          }
        },
        itemBuilder: (context) => const [
          PopupMenuItem(value: 'start', child: Text('Start')),
          PopupMenuItem(value: 'pause', child: Text('Pause')),
          PopupMenuItem(value: 'resume', child: Text('Resume')),
          PopupMenuItem(value: 'complete', child: Text('Complete…')),
          PopupMenuItem(value: 'archive', child: Text('Archive')),
        ],
      ),
    );
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
