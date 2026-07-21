// Recommendations: Accept / Reject (one endpoint per button).
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import 'rest_list_screen.dart';

class RecommendationsScreen extends RestListScreen {
  const RecommendationsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No active recommendations.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getRecommendations();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final recommendation = Recommendation.fromJson(row);
    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(recommendation.reason),
            const SizedBox(height: 4),
            Text(
              'priority ${recommendation.priority?.toStringAsFixed(2) ?? '—'}'
              ' · expires ${clock(recommendation.expiresAt)}',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                TextButton(
                  onPressed: () => _reject(context, screenState,
                      recommendation.id),
                  child: const Text('Reject'),
                ),
                const SizedBox(width: 8),
                FilledButton(
                  onPressed: () => screenState.runAction(
                    () => screenState.widget.state.client
                        .acceptRecommendation(recommendation.id),
                    'Recommendation accepted',
                  ),
                  child: const Text('Accept'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _reject(BuildContext context,
      RestListScreenState screenState, String id) async {
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Reject recommendation'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(labelText: 'Reason (optional)'),
        ),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Cancel')),
          FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Reject')),
        ],
      ),
    );
    if (confirmed != true) return;
    final reason = controller.text.trim();
    await screenState.runAction(
      () => screenState.widget.state.client
          .rejectRecommendation(id, reason: reason.isEmpty ? null : reason),
      'Recommendation rejected',
    );
  }
}
