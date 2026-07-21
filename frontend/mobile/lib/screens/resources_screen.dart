// Resources: read-only list.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/api_client.dart';
import '../services/app_state.dart';
import 'rest_list_screen.dart';

class ResourcesScreen extends RestListScreen {
  const ResourcesScreen({super.key, required super.state});

  @override
  String get emptyText => 'No resources.';

  @override
  Future<List<Map<String, dynamic>>> fetch(ApiClient client) =>
      client.getResources();

  @override
  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState) {
    final resource = ResourceItem.fromJson(row);
    return ListTile(
      title: Text('${resource.type}: ${resource.value} ${resource.unit}'),
      subtitle: Text('updated ${dayTime(resource.lastUpdated)}'),
      leading: const Icon(Icons.battery_charging_full_outlined),
    );
  }
}
