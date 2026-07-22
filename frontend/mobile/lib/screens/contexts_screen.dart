// Contexts: read-only list.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import 'rest_list_screen.dart';

class ContextsScreen extends RestListScreen {
  const ContextsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No contexts.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getContexts();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final item = ContextItem.fromJson(row);
    final details = [item.location, item.environment, item.reason]
        .whereType<String>()
        .where((text) => text.isNotEmpty)
        .join(' Â· ');
    return ListTile(
      title: Text(item.name),
      subtitle: details.isEmpty ? null : Text(details),
      leading: const Icon(Icons.place_outlined),
    );
  }
}
