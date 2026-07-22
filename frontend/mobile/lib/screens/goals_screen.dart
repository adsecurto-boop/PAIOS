// Goals: read-only list (creation stays on the desktop/CLI).
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import 'rest_list_screen.dart';

class GoalsScreen extends RestListScreen {
  const GoalsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No goals.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getGoals();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final goal = Goal.fromJson(row);
    return ListTile(
      title: Text(goal.name),
      subtitle: Text(goal.description.isEmpty
          ? goal.status
          : '${goal.status} Â· ${goal.description}'),
      leading: Icon(
        goal.status == 'Active' ? Icons.flag : Icons.outlined_flag,
      ),
    );
  }
}
