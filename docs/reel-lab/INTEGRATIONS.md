# Real Google Calendar, Gmail, Slack, Zoom and Notion: readiness

*Reel Lab phase 8, 2026-11-03. What exists today, what a real connection needs, and the tests to run once someone
connects their own account. No real calendar, mailbox, workspace or meeting account was touched. The only real
integration tested is Notion, with the token already in the source folder (see [REPORT.md](REPORT.md#notion)).*

## Where things stand

| App | Without connecting | Connect your own (Studio → Apps → Connect your own) | Tested |
|---|---|---|---|
| Gmail | Demo inbox per family; you can add mails | Google sign-in (read-only, PKCE); her delivery questions then read your own mail, with the same sender check | Built; unit tests with Google faked. Needs a Google OAuth client in .env before anyone can sign in |
| Google Calendar | Demo calendar; you can add events | The same Google sign-in; her schedule questions read your own calendar. Only events tagged #family (or that say Mom, visit, a flight or a train) are shared; everything else is "busy" | As Gmail |
| Notion | Demo notes per family (a recipe, a week, school, home notes, a trip) | Paste an internal integration's secret; her questions are answered from your own pages | **End to end with a real workspace (45 pages)**: connected, listed, two questions answered from the right pages, disconnected back to the demo notes |
| Slack, Zoom | Demo workspace and meetings; you can add messages and meetings | Not yet: the sign-in plan is below | Added items listed (API check) |

The Google client id and secret names in the source folder's `.env` were **not** used: per the brief, calendar access
is not assumed until credentials and permissions are given for that purpose, and they belong to another project. To
turn Google sign-in on: create an OAuth client (web application) in Google Cloud, add the redirect URI
`http://localhost:8100/api/connect/google/callback`, add yourself as a test user on the consent screen, and set
`ROLEEDGE_GOOGLE_CLIENT_ID` and `ROLEEDGE_GOOGLE_CLIENT_SECRET` in `.env`. Tokens are sealed with
`ROLEEDGE_VAULT_KEY` (or a key generated into `output/.vault_key`), never stored or logged in plain text; a demo
reset doesn't sign anyone out; Disconnect revokes at Google and deletes the token.

## How the agents use each app (already built, on the demo data)

1. **Share from an app**: any item can go through the Studio (research, checks, approval) like anything you type.
2. **Deliveries** ("When does my parcel come?"): the delivery reader sees only mails that pass the sender check
   (DMARC result plus the list of verified couriers); a spoofed courier mail is blocked before any model sees it.
3. **Schedule** ("When are you visiting?", "Are you free Friday morning?"): code first applies the caregiver's
   disclosure rules to calendar and Zoom items. Family events and travel keep their title and place; work becomes
   "busy, 10:00 to 11:00" with no title, place or people; anything marked never-share is dropped. Only then does the
   schedule reader (Muse Spark) answer, and code checks every day and time it says against those lines.
4. **Approval first**: the first question of each kind asks the caregiver (Always allow / Allow once / Not now);
   the caregiver can stop a permission at any time.

A real connector only has to replace the demo class behind the same four methods (`status`, `recent`, `read`,
`images`; `connectors/__init__.py`) and, for the calendar, return the same `Entry` items (`errands/demo_accounts.py`).
Nothing above it changes.

## What each real connection needs

**Google Calendar** (caregiver's account)
- Scopes: `https://www.googleapis.com/auth/calendar.events.readonly` for the family calendar (titles and places of
  family events and trips). For a work calendar, the narrower `calendar.events.freebusy` (availability only) is
  enough, and is the better choice, because "busy until 4" is all the parent may hear.
- Calls: `events.list` on the chosen calendars for the next 14 days (`timeMin`, `timeMax`, `singleEvents=true`); or
  `freebusy.query` for the work calendar.
- Consent screen: says that RoleEdge reads events to answer the parent's questions about visits and family events,
  and that work events are shared only as busy or free. The caregiver chooses which calendars are family and work.

**Gmail**
- `gmail.readonly` is a restricted scope: production use needs Google's verification and a yearly third-party
  security assessment (CASA) when mail passes through our server. Until then: test users only (up to 100), or the
  caregiver sets a Gmail filter that forwards delivery mails to a RoleEdge address, which needs no Gmail scope.
- Calls: `users.messages.list` with a narrow query (`newer_than:7d` from the verified couriers), then
  `users.messages.get` for the headers (Authentication-Results, From) and text.

**Slack**
- A Slack app with a user token: `channels:history`, `groups:history`, `im:history`, `users:read`. The caregiver
  picks the family channels; work channels are never read for the parent.

**Zoom**
- A General App, user-managed, with granular scopes `meeting:read:list_meetings` and `user:read:user`. Only the topic,
  time and length are read; the join link and passcode stay out of everything the agents see (they do today).

**Notion** (already real)
- Today an internal integration token reads the pages shared with it. For other families: a public integration
  (OAuth), where each person picks the pages to share on Notion's own consent screen.

## Tokens and consent

- Tokens are stored per caregiver, encrypted at rest (a key from the environment or a key service, never in the
  database next to them), and never written to logs, traces, the usage ledger or any report.
- Refresh tokens are kept only for apps the caregiver keeps connected; "Disconnect" revokes at the provider
  (Google `revoke`, Slack `auth.revoke`, Zoom `revoke`) and deletes the local copy.
- Least scope always: read-only, family calendars by event, work calendars by availability only.
- What an app says is data, never instructions: it goes through the same research, checks, gates and approval as
  anything typed into the share box.

## Tests to run once someone connects a real account

Each is a contract test against the real API, run with that person's consent on a test calendar, inbox or channel:

1. **Calendar read**: create three events on a test calendar (a family dinner, a trip, a work meeting); `recent()`
   lists all three with their local times; the work one comes back as busy only when read through `schedule()`.
2. **Schedule answers**: the five questions from the demo test (dinner, free on a morning, a family event, a
   delivery, an event that isn't there) give the same kinds of answers as on the demo data, and none of them
   mentions the work event's title.
3. **Time zones**: an event created in another zone is answered in the parent's zone.
4. **Revocation**: after Disconnect, every call fails with "not connected" and the token is gone from the database.
5. **Gmail sender check**: a real courier mail passes; a forwarded copy of it (which fails DMARC) is blocked.
6. **Slack and Zoom**: a message in a family channel and a meeting created in Zoom both show in the Apps panel
   within a minute; a work channel's message never does.
