// The Today header: what the phone opens with. A time-of-day greeting,
// Today's Focus (the running event with its progress bar, else the next
// planned entry with a countdown), and the next entry with the
// scheduler's "Recommended because:" bullets. Pure presentation - the
// caller supplies precomputed view data.
import 'package:flutter/material.dart';

/// One entry as the header shows it (focus or up-next).
class TodayEntryView {
  final String title;
  final bool running;
  final double? progress; // running only
  final int? remainingMinutes; // running only
  final int? startsInMinutes; // planned only
  final String? startClock; // 'HH:MM', planned only
  final List<String> reasons; // "Recommended because:" bullets

  const TodayEntryView({
    required this.title,
    this.running = false,
    this.progress,
    this.remainingMinutes,
    this.startsInMinutes,
    this.startClock,
    this.reasons = const [],
  });
}

/// 'Good Morning.' / 'Good Afternoon.' / 'Good Evening.'
String greetingFor(DateTime now) {
  if (now.hour < 12) return 'Good Morning.';
  if (now.hour < 17) return 'Good Afternoon.';
  return 'Good Evening.';
}

/// '<n> min' under an hour, '<h>h <m>m' above.
String startsInLabel(int minutes) => minutes < 60
    ? 'starts in $minutes min'
    : 'starts in ${minutes ~/ 60}h ${minutes % 60}m';

class TodayHeader extends StatelessWidget {
  final DateTime now;
  final TodayEntryView? focus; // null -> friendly empty state
  final TodayEntryView? next;

  const TodayHeader({super.key, required this.now, this.focus, this.next});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(4, 4, 4, 10),
          child: Text(greetingFor(now), style: theme.textTheme.headlineSmall),
        ),
        Card(
          color: theme.colorScheme.primaryContainer,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("TODAY'S FOCUS",
                    style: theme.textTheme.labelMedium?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                      fontWeight: FontWeight.bold,
                      letterSpacing: 1.2,
                    )),
                const SizedBox(height: 6),
                if (focus == null)
                  Text('Nothing scheduled yet — capture what matters below.',
                      style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onPrimaryContainer))
                else
                  _entry(context, focus!,
                      onColor: theme.colorScheme.onPrimaryContainer),
              ],
            ),
          ),
        ),
        if (next != null)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('UP NEXT',
                      style: theme.textTheme.labelMedium?.copyWith(
                        color: theme.colorScheme.outline,
                        fontWeight: FontWeight.bold,
                        letterSpacing: 1.2,
                      )),
                  const SizedBox(height: 6),
                  _entry(context, next!),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _entry(BuildContext context, TodayEntryView view,
      {Color? onColor}) {
    final theme = Theme.of(context);
    final titleStyle = theme.textTheme.titleMedium?.copyWith(color: onColor);
    final bodyStyle = theme.textTheme.bodySmall?.copyWith(color: onColor);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (view.running) ...[
          Text(view.title, style: titleStyle),
          const SizedBox(height: 8),
          LinearProgressIndicator(value: view.progress),
          if (view.remainingMinutes != null) ...[
            const SizedBox(height: 4),
            Text('${view.remainingMinutes} min left', style: bodyStyle),
          ],
        ] else
          Text(
            '${view.title}'
            '${view.startClock == null ? '' : ' · ${view.startClock}'}'
            '${view.startsInMinutes == null ? '' : ' — ${startsInLabel(view.startsInMinutes!)}'}',
            style: titleStyle,
          ),
        if (view.reasons.isNotEmpty) ...[
          const SizedBox(height: 8),
          Text('Recommended because:', style: bodyStyle),
          for (final reason in view.reasons)
            Padding(
              padding: const EdgeInsets.only(left: 8, top: 2),
              child: Text('• $reason', style: bodyStyle),
            ),
        ],
      ],
    );
  }
}
