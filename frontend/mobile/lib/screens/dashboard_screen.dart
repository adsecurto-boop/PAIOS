// The mobile TODAY dashboard: every mission card, filled from the last
// /dashboard snapshot. Pull-to-refresh + the AppState poll timer.
import 'package:flutter/material.dart';

import '../models/models.dart';
import '../services/app_state.dart';
import '../widgets/section_card.dart';

class DashboardScreen extends StatelessWidget {
  final AppState state;

  const DashboardScreen({super.key, required this.state});

  @override
  Widget build(BuildContext context) {
    final dashboard = state.dashboard;
    if (dashboard == null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Text(
            state.online == false
                ? 'No snapshot yet — waiting for ${state.settings.baseUrl}'
                : 'Loading…',
            textAlign: TextAlign.center,
          ),
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: state.refresh,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.symmetric(vertical: 8),
        children: _cards(dashboard),
      ),
    );
  }

  List<Widget> _cards(DashboardData d) {
    final unread = state.center.unreadCount;
    final latestNotices = state.center.entries.take(3).toList();
    return [
      SectionCard(title: 'Time', children: [
        Line('Current time: ${dayTime(d.currentTime)}'),
        Line('Last sync: ${state.lastSync}'),
      ]),
      SectionCard(title: 'Status', children: [
        Line('Kernel: ${d.kernel}   Scheduler: ${d.scheduler}'),
        Line('Operational: ${d.operational ? 'yes' : 'NO'}'),
        Line('Last snapshot: ${dayTime(d.snapshotAt)}'),
      ]),
      SectionCard(title: 'Current Event', children: [
        if (d.currentEvent == null)
          const Line('Idle — no running event.')
        else ...[
          Line('[${d.currentEvent!.status}] ${d.currentEvent!.description}'),
          Line('Started ${clock(d.currentEvent!.startedAt)}'
              ' · elapsed ${d.currentEvent!.elapsedMinutes ?? '—'} min'
              ' · remaining ${d.currentEvent!.remainingMinutes ?? '—'} min'),
        ],
      ]),
      SectionCard(title: 'Current Context', children: [
        Line(d.executionContext.isEmpty
            ? 'No snapshot yet.'
            : d.executionContext +
                (d.contextReason == null ? '' : ' — ${d.contextReason}')),
      ]),
      SectionCard(title: 'Goals', children: [
        if (d.goals.isEmpty) const Line('No goals.'),
        for (final goal in d.goals.take(5))
          Line('[${goal.status}] ${goal.name}'),
      ]),
      SectionCard(title: 'Projects', children: [
        if (d.projects.isEmpty) const Line('No projects.'),
        for (final project in d.projects.take(5))
          Line('[${project.status}] ${project.name}'
              '${project.completion == null ? '' : ' — ${project.completion!.toStringAsFixed(0)}%'}'),
      ]),
      SectionCard(title: 'Recommendations', children: [
        if (d.recommendations.isEmpty)
          const Line('No active recommendations.'),
        for (final rec in d.recommendations.take(5)) Line(rec.reason),
      ]),
      SectionCard(title: 'Health', children: [
        if (d.healthResources.isEmpty)
          const Line('No health resources tracked.'),
        for (final resource in d.healthResources)
          Line('${resource.type}: ${resource.value} ${resource.unit}'),
        Line('Today — completed: ${d.completedToday}'
            '  running: ${d.runningCount}  upcoming: ${d.upcomingCount}'),
      ]),
      SectionCard(title: 'Resources', children: [
        if (state.resources.isEmpty) const Line('No resources.'),
        for (final resource in state.resources.take(7))
          Line('${resource.type}: ${resource.value} ${resource.unit}'
              '  (updated ${dayTime(resource.lastUpdated)})'),
      ]),
      SectionCard(title: 'Learning', children: [
        Line('Last studied: ${dayTime(d.lastStudied)}'),
        Line('Revised today: ${d.revisedToday}'),
        Line(d.latestInsight == null
            ? 'No insights yet.'
            : 'Latest insight: [${d.latestInsight!['category'] ?? '?'}]'),
      ]),
      SectionCard(title: 'Recent Reflection', children: [
        if (d.latestReflection == null)
          const Line('No reflections yet.')
        else
          Line('${dayTime(d.latestReflection!.createdAt)} — '
              '${d.latestReflection!.lessonLearned ?? d.latestReflection!.facts ?? '(no text)'}'),
      ]),
      SectionCard(title: 'Notifications', children: [
        Line(unread == 0 ? 'No unread notifications.' : '$unread unread'),
        for (final notice in latestNotices) Line(notice.message),
      ]),
    ];
  }
}
