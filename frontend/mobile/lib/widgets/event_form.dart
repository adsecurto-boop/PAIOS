// The create/edit event form (M20). Collects title, optional schedule,
// priority and metadata fields; only fields the user actually set end
// up in the request body - the API keeps every default.
import 'package:flutter/material.dart';

import '../models/models.dart';

class EventFormResult {
  final String title;
  final String? suggestedTime;
  final double? priority;
  final Map<String, dynamic> metadata; // only user-set fields

  EventFormResult({
    required this.title,
    this.suggestedTime,
    this.priority,
    this.metadata = const {},
  });
}

/// Shows the event form dialog; returns null when cancelled.
Future<EventFormResult?> showEventForm(
  BuildContext context, {
  String heading = 'New event',
  String submitLabel = 'Create',
  String? initialTitle,
  String? initialSuggestedTime,
  double? initialPriority,
  EventMetadata? initialMetadata,
}) =>
    showDialog<EventFormResult>(
      context: context,
      builder: (context) => _EventFormDialog(
        heading: heading,
        submitLabel: submitLabel,
        initialTitle: initialTitle,
        initialSuggestedTime: initialSuggestedTime,
        initialPriority: initialPriority,
        initialMetadata: initialMetadata,
      ),
    );

class _EventFormDialog extends StatefulWidget {
  final String heading;
  final String submitLabel;
  final String? initialTitle;
  final String? initialSuggestedTime;
  final double? initialPriority;
  final EventMetadata? initialMetadata;

  const _EventFormDialog({
    required this.heading,
    required this.submitLabel,
    this.initialTitle,
    this.initialSuggestedTime,
    this.initialPriority,
    this.initialMetadata,
  });

  @override
  State<_EventFormDialog> createState() => _EventFormDialogState();
}

class _EventFormDialogState extends State<_EventFormDialog> {
  late final TextEditingController _title;
  late final TextEditingController _priority;
  late final TextEditingController _duration;
  late final TextEditingController _tags;
  DateTime? _date;
  TimeOfDay? _time;
  DateTime? _deadline;
  String _energy = '';

  @override
  void initState() {
    super.initState();
    final meta = widget.initialMetadata;
    _title = TextEditingController(text: widget.initialTitle ?? '');
    _priority = TextEditingController(
        text: widget.initialPriority?.toString() ?? '');
    _duration = TextEditingController(
        text: meta?.estimatedDurationMinutes?.toString() ?? '');
    _tags = TextEditingController(text: meta?.tags.join(', ') ?? '');
    _energy = meta?.energy ?? '';
    final start = _parseIso(widget.initialSuggestedTime);
    if (start != null) {
      _date = DateTime(start.year, start.month, start.day);
      _time = TimeOfDay(hour: start.hour, minute: start.minute);
    }
    _deadline = _parseIso(meta?.deadline);
  }

  static DateTime? _parseIso(String? iso) =>
      iso == null ? null : DateTime.tryParse(iso);

  @override
  void dispose() {
    _title.dispose();
    _priority.dispose();
    _duration.dispose();
    _tags.dispose();
    super.dispose();
  }

  String _two(int value) => value.toString().padLeft(2, '0');

  String? get _suggestedTime {
    if (_date == null) return null;
    final time = _time ?? const TimeOfDay(hour: 9, minute: 0);
    return '${_date!.year}-${_two(_date!.month)}-${_two(_date!.day)}'
        'T${_two(time.hour)}:${_two(time.minute)}:00';
  }

  Map<String, dynamic> get _metadata {
    final tags = _tags.text
        .split(',')
        .map((tag) => tag.trim())
        .where((tag) => tag.isNotEmpty)
        .toList();
    final duration = int.tryParse(_duration.text.trim());
    return {
      if (tags.isNotEmpty) 'tags': tags,
      if (_deadline != null)
        'deadline': '${_deadline!.year}-${_two(_deadline!.month)}'
            '-${_two(_deadline!.day)}T23:59:00',
      if (_energy.isNotEmpty) 'energy': _energy,
      if (duration != null) 'estimated_duration_minutes': duration,
    };
  }

  Future<void> _pickDate() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date ?? now,
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _pickTime() async {
    final picked = await showTimePicker(
      context: context,
      initialTime: _time ?? const TimeOfDay(hour: 9, minute: 0),
    );
    if (picked != null) setState(() => _time = picked);
  }

  Future<void> _pickDeadline() async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _deadline ?? now,
      firstDate: now.subtract(const Duration(days: 1)),
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null) setState(() => _deadline = picked);
  }

  void _submit() {
    final title = _title.text.trim();
    if (title.isEmpty) return; // title is the one required field
    Navigator.pop(
      context,
      EventFormResult(
        title: title,
        suggestedTime: _suggestedTime,
        priority: double.tryParse(_priority.text.trim()),
        metadata: _metadata,
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.heading),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            TextField(
              controller: _title,
              decoration: const InputDecoration(labelText: 'Title'),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickDate,
                    icon: const Icon(Icons.calendar_today, size: 16),
                    label: Text(_date == null
                        ? 'Date'
                        : '${_date!.year}-${_two(_date!.month)}'
                            '-${_two(_date!.day)}'),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton.icon(
                    onPressed: _pickTime,
                    icon: const Icon(Icons.schedule, size: 16),
                    label: Text(_time == null
                        ? 'Time'
                        : '${_two(_time!.hour)}:${_two(_time!.minute)}'),
                  ),
                ),
              ],
            ),
            TextField(
              controller: _priority,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Priority'),
            ),
            TextField(
              controller: _duration,
              keyboardType: TextInputType.number,
              decoration:
                  const InputDecoration(labelText: 'Duration (minutes)'),
            ),
            DropdownButtonFormField<String>(
              // ignore: deprecated_member_use
              value: _energy.isEmpty ? null : _energy,
              decoration: const InputDecoration(labelText: 'Energy'),
              items: const [
                DropdownMenuItem(value: '', child: Text('—')),
                DropdownMenuItem(value: 'low', child: Text('Low')),
                DropdownMenuItem(value: 'medium', child: Text('Medium')),
                DropdownMenuItem(value: 'high', child: Text('High')),
              ],
              onChanged: (value) => setState(() => _energy = value ?? ''),
            ),
            TextField(
              controller: _tags,
              decoration: const InputDecoration(
                  labelText: 'Tags (comma-separated)'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _pickDeadline,
              icon: const Icon(Icons.flag_outlined, size: 16),
              label: Text(_deadline == null
                  ? 'Deadline'
                  : 'Deadline ${_deadline!.year}-${_two(_deadline!.month)}'
                      '-${_two(_deadline!.day)}'),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel')),
        FilledButton(onPressed: _submit, child: Text(widget.submitLabel)),
      ],
    );
  }
}
