// Projects: read-only list with progress bars.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import 'rest_list_screen.dart';

class ProjectsScreen extends RestListScreen {
  const ProjectsScreen({super.key, required super.state});

  @override
  String get emptyText => 'No projects.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getProjects();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final project = Project.fromJson(row);
    return ListTile(
      title: Text(project.name),
      subtitle: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(project.status),
          if (project.completion != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: LinearProgressIndicator(
                  value: (project.completion! / 100).clamp(0.0, 1.0)),
            ),
        ],
      ),
      trailing: Text(project.completion == null
          ? 'â€”'
          : '${project.completion!.toStringAsFixed(0)}%'),
    );
  }
}
