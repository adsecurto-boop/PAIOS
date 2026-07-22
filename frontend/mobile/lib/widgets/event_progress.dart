// Shared display-only arithmetic for running events: progress fraction
// and remaining minutes. Used by the Timeline NOW card and the Today
// header - one implementation, no domain logic, pure presentation.

/// Elapsed fraction of a running event, clamped to 0..1; null when the
/// inputs cannot support a bar (no start, no positive duration).
double? eventProgress({
  required String? startedIso,
  required int? durationMinutes,
  required DateTime now,
}) {
  if (startedIso == null || durationMinutes == null || durationMinutes <= 0) {
    return null;
  }
  final started = DateTime.tryParse(startedIso);
  if (started == null) return null;
  return (now.difference(started).inSeconds / (durationMinutes * 60))
      .clamp(0.0, 1.0)
      .toDouble();
}

/// Whole minutes left in a running event, clamped to 0..duration; null
/// when unknown.
int? eventRemainingMinutes({
  required String? startedIso,
  required int? durationMinutes,
  required DateTime now,
}) {
  if (startedIso == null || durationMinutes == null || durationMinutes <= 0) {
    return null;
  }
  final started = DateTime.tryParse(startedIso);
  if (started == null) return null;
  final elapsed = now.difference(started).inMinutes;
  return (durationMinutes - elapsed).clamp(0, durationMinutes).toInt();
}
