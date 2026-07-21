// The M14 notification center on the phone: history, unread markers,
// mark read, clear. Local presentation state (permitted store).
import 'package:flutter/material.dart';

import '../services/app_state.dart';

class NotificationsScreen extends StatelessWidget {
  final AppState state;

  const NotificationsScreen({super.key, required this.state});

  IconData _icon(String kind) => switch (kind) {
        'error' => Icons.error_outline,
        'warn' => Icons.warning_amber_outlined,
        'ok' => Icons.check_circle_outline,
        _ => Icons.info_outline,
      };

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: state,
      builder: (context, _) {
        final entries = state.center.entries;
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              child: Row(
                children: [
                  Text('${state.center.unreadCount} unread'),
                  const Spacer(),
                  TextButton(
                    onPressed: state.markAllRead,
                    child: const Text('Mark all read'),
                  ),
                  TextButton(
                    onPressed: state.clearNotifications,
                    child: const Text('Clear'),
                  ),
                ],
              ),
            ),
            Expanded(
              child: entries.isEmpty
                  ? const Center(child: Text('No notifications.'))
                  : ListView.builder(
                      itemCount: entries.length,
                      itemBuilder: (context, index) {
                        final notice = entries[index];
                        return ListTile(
                          dense: true,
                          leading: Icon(_icon(notice.kind)),
                          title: Text(
                            notice.message,
                            style: TextStyle(
                              fontWeight: notice.read
                                  ? FontWeight.normal
                                  : FontWeight.bold,
                            ),
                          ),
                          subtitle: Text(
                              '${notice.category}'
                              '${notice.occurredAt.isEmpty ? '' : ' · ${notice.occurredAt}'}'),
                          trailing: notice.read
                              ? null
                              : const Icon(Icons.circle, size: 10),
                        );
                      },
                    ),
            ),
          ],
        );
      },
    );
  }
}
