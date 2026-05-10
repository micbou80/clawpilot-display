# Display Scenarios

Each scenario changes the display layout, icon, header color, and content. The left pane shows the scenario state with a contextual icon; the right pane shows actionable information.

## Currently Working

### Idle / All Clear
- **Type**: `idle`
- **Icon**: Clawpilot mascot
- **Header**: "ALL CLEAR" (green)
- **Left pane**: Status note (e.g., "Inbox zero. All quiet.")
- **Right pane**: Next meeting info + prep + upcoming calendar
- **Trigger**: Default state, no active notifications

### Meeting Countdown
- **Type**: `meeting`
- **Icon**: Calendar with today's date
- **Header**: "UPCOMING MEETING" (orange)
- **Left pane**: Big countdown timer "4m 39s" + "until start"
- **Right pane**: Meeting title, time, Teams badge, attendee status, prep notes
- **Trigger**: Next meeting within 15 minutes

### Email Alert
- **Type**: `email`
- **Icon**: Orange envelope with red dot
- **Header**: "EMAIL" (orange)
- **Left pane**: Sender name, subject preview
- **Right pane**: Email body preview
- **Trigger**: VIP email or action-required email detected

### Teams Message
- **Type**: `teams`
- **Icon**: Purple Teams logo
- **Header**: "TEAMS" (purple)
- **Left pane**: Sender, chat name
- **Right pane**: Message preview
- **Trigger**: Mention or DM in monitored chat

### Urgent Alert
- **Type**: `urgent`
- **Icon**: Red warning triangle
- **Header**: "URGENT" (red)
- **Left pane**: Severity, time
- **Right pane**: Alert details
- **Trigger**: VIP escalation, system alert, urgent keyword

### Agent Working
- **Type**: `working`
- **Icon**: Gear
- **Header**: "WORKING" (cyan)
- **Left pane**: Task description
- **Right pane**: Progress details
- **Trigger**: Clawpilot actively handling a task

### Task Complete
- **Type**: `done`
- **Icon**: Checkmark
- **Header**: "DONE" (green)
- **Left pane**: Duration, summary
- **Right pane**: What was accomplished
- **Trigger**: Working task completes

### Flight Tracker
- **Type**: `flight`
- **Icon**: Airplane
- **Header**: "FLIGHT" (blue)
- **Left pane**: Route codes (AMS → LIN)
- **Right pane**: Gate, status, times, lounge info
- **Trigger**: Flight in calendar within 24h

## Planned (Not Yet Implemented)

### Night Mode
- Near-black screen, faint clock
- Backlight at 10%
- Notifications queue silently
- Auto 22:00–07:00

### Focus Mode
- Deep work timer with spinning ring
- Notifications paused indicator
- Manual trigger via button or API

### Hydrate / Move Break
- Gentle wellness reminders
- 90-min hydration cycle, 60-min movement cycle
- Auto-dismiss after 6 seconds

### Morning Briefing
- Greeting + weather
- Day's meetings + inbox count
- Key action for the day
- First activity after night mode

### Celebration
- Achievement notification with sparkle overlay
- Inbox zero, deal won, milestone hit
- Auto-dismiss after 8 seconds

### Running Late
- Flashing overdue timer
- Meeting name, attendees waiting
- Join link hint

### Context Switch
- 5 min before topic change
- Current context → next context cards

### Voice Active
- Audio waveform visualization
- PTT button held indicator

### Home Assistant
- Temperature, device grid
- Voice command or button combo trigger

## Notification Lifecycle

Every notification has a TTL (time-to-live):

| State | TTL | Heartbeat |
|-------|-----|-----------|
| working | 10 min | 60s keep-alive |
| stuck | 15 min | — |
| needs-input | 30 min | — |
| done/error | 6 sec | — |
| toast | 8 sec | — |

On expiry → device returns to idle.

The device also runs a firmware watchdog: if no API activity for 15 minutes, return to idle regardless.
