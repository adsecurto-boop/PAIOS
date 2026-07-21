// Shared scaffold for the read-only list screens: fetch on show,
// pull-to-refresh, graceful error text, never a crash.
import 'package:flutter/material.dart';

import '../services/api_client.dart';
import '../services/app_state.dart';

abstract class RestListScreen extends StatefulWidget {
  final AppState state;
  const RestListScreen({super.key, required this.state});

  Future<List<Map<String, dynamic>>> fetch(ApiClient client);

  Widget buildTile(BuildContext context, Map<String, dynamic> row,
      RestListScreenState screenState);

  String get emptyText => 'Nothing here yet.';

  @override
  State<RestListScreen> createState() => RestListScreenState();
}

class RestListScreenState extends State<RestListScreen> {
  List<Map<String, dynamic>>? rows;
  String? error;

  @override
  void initState() {
    super.initState();
    reload();
  }

  Future<void> reload() async {
    try {
      final fetched = await widget.fetch(widget.state.client);
      if (!mounted) return;
      setState(() {
        rows = fetched;
        error = null;
      });
    } on ApiUnreachableException catch (e) {
      if (!mounted) return;
      setState(() => error = 'Server unreachable: ${e.detail}');
    } on ApiResponseException catch (e) {
      if (!mounted) return;
      setState(() => error = e.message);
    }
  }

  /// Run one REST action, snackbar the outcome, reload the list.
  Future<void> runAction(
      Future<void> Function() call, String successNotice) async {
    final failure = await widget.state.runAction(call, successNotice);
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(failure ?? successNotice)),
    );
    await reload();
  }

  @override
  Widget build(BuildContext context) {
    if (rows == null && error == null) {
      return const Center(child: CircularProgressIndicator());
    }
    if (rows == null) {
      return Center(
          child: Padding(
        padding: const EdgeInsets.all(24),
        child: Text(error!, textAlign: TextAlign.center),
      ));
    }
    return RefreshIndicator(
      onRefresh: reload,
      child: rows!.isEmpty
          ? ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              children: [
                Padding(
                  padding: const EdgeInsets.all(24),
                  child:
                      Text(widget.emptyText, textAlign: TextAlign.center),
                ),
              ],
            )
          : ListView.builder(
              physics: const AlwaysScrollableScrollPhysics(),
              itemCount: rows!.length,
              itemBuilder: (context, index) =>
                  widget.buildTile(context, rows![index], this),
            ),
    );
  }
}
