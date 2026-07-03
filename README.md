# Event Finder Overview

**Event Finder** is a Django webapp that I made for my A-level Computer Science NEA.

**Key Capabilities**
- **Event Discovery and Participation** - Browse a global list of events created by other people. Apply various filters and search by keywords to narrow search.
- **Map Interface** - Interact with an on-screen map to pinpoint event location.
- **Event Creation** - Create custom events at any location, adding descriptions, images, and categories.
- **Per-Event Real-time Chat** - Access an attendee-only live group chat, hosted privately for every event.
- **Secure User Auth** - Create and manage an account which is stored securely. Upload a profile image and give yourself a description.

## Prerequisites

- Python 3
- Docker

## Installation & Running

Clone the repository:

```bash
git clone https://github.com/chromalemon/event-finder Event_Finder
cd Event_Finder
```

Make the scripts executable:

```bash
chmod +x setup.sh run.sh
```

Run the setup script:

```bash
./setup.sh
```

Start the application:

```bash
./run.sh
```

The application will then be available at:

```
http://127.0.0.1:8000
```

## Stopping redis

When you are finished:

```bash
docker stop redis
```