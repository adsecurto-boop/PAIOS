// Reflections: read-only list, newest first.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import 'rest_list_screen.dart';

class ReflectionsScreen extends RestListScreen {
  const ReflectionsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No reflections yet.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) async =>
      (await client.getReflections()).reversed.toList();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final reflection = Reflection.fromJson(row);
    return ListTile(
      title: Text(reflection.lessonLearned ??
          reflection.facts ??
          '(no text)'),
      subtitle: Text('${dayTime(reflection.createdAt)}'
          '${reflection.improvement == null ? '' : ' · improve: ${reflection.improvement}'}'),
      leading: const Icon(Icons.psychology_outlined),
    );
  }
}
