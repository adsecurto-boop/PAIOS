// Shared scaffold for the REST list screens: fetch on show,
// pull-to-refresh, graceful error text, never a crash. Subclasses may
// declare a cacheKey (offline fallback) and a floating action button.
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

  /// When set, the last successful fetch is persisted under this key and
  /// restored while the server is unreachable (offline cache, M20).
  String? get cacheKey => null;

  /// Optional floating action button (M20: create flows).
  Widget? buildFab(BuildContext context, RestListScreenState screenState) =>
      null;

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
      final key = widget.cacheKey;
      if (key != null) await widget.state.cachePayload(key, fetched);
    } on ApiUnreachableException catch (e) {
      if (!mounted) return;
      if (!_restoreFromCache()) {
        setState(() => error = 'Server unreachable: ${e.detail}');
      }
    } on ApiResponseException catch (e) {
      if (!mounted) return;
      setState(() => error = e.message);
    }
  }

  /// Offline fallback: render the last cached payload if there is one.
  bool _restoreFromCache() {
    final key = widget.cacheKey;
    if (key == null) return false;
    final cached = widget.state.cachedPayload(key);
    if (cached is! List) return false;
    setState(() {
      rows = cached.whereType<Map<String, dynamic>>().toList();
      error = null;
    });
    return true;
  }

  /// Drops one row immediately (Dismissible contract: the widget must
  /// leave the tree in the same frame); the follow-up reload re-syncs.
  void removeRow(Map<String, dynamic> row) {
    setState(() => rows?.remove(row));
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
    final fab = widget.buildFab(context, this);
    final body = _buildBody(context);
    if (fab == null) return body;
    return Scaffold(
      backgroundColor: Colors.transparent,
      floatingActionButton: fab,
      body: body,
    );
  }

  Widget _buildBody(BuildContext context) {
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
