// The offline strip: shown whenever the last poll failed. The last
// successful snapshot stays on screen underneath (mission: graceful).
import 'package:flutter/material.dart';

class OfflineBanner extends StatelessWidget {
  final bool visible;
  final int retrySeconds;

  const OfflineBanner(
      {super.key, required this.visible, required this.retrySeconds});

  @override
  Widget build(BuildContext context) {
    if (!visible) return const SizedBox.shrink();
    return Container(
      width: double.infinity,
      color: Theme.of(context).colorScheme.errorContainer,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Text(
        'OFFLINE — showing last snapshot, retrying every ${retrySeconds}s',
        style: TextStyle(
          color: Theme.of(context).colorScheme.onErrorContainer,
          fontWeight: FontWeight.bold,
        ),
      ),
    );
  }
}
