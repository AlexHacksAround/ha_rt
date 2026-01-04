Below is a **clean, self-contained project description** in **Markdown**, suitable for a repository `README.md` or internal documentation. It reflects exactly what you have built and why, without unnecessary fluff.

---

```markdown
# Home Assistant → Request Tracker (RT) Ticket Integration

## Overview

This project integrates **Home Assistant** with **Request Tracker (RT)** to automatically create and manage operational tickets based on Home Assistant events (e.g. sensors, alerts, device failures).

The integration is implemented entirely using **Home Assistant `rest_command`** actions and **RT REST2**, with **token authentication**, and supports **ticket deduplication** using a custom RT field.

The result is a lightweight, maintainable bridge between home/infra automation and a professional ticketing system.

---

## Goals

- Automatically create RT tickets from Home Assistant
- Avoid duplicate tickets for the same device or condition
- Use RT-native features (queues, custom fields, lifecycles)
- Avoid external middleware unless needed
- Keep configuration declarative and transparent

---

## Architecture

```

Home Assistant
└── Automation / Action
└── rest_command (HTTP)
└── RT REST2 API
└── Ticket in RT queue

```

### Key Design Choices

- **REST2 API** (not legacy RT REST)
- **Token authentication** (service account)
- **Queue-based routing** (`Facility Management`)
- **Custom Field–based deduplication**
- Explicit port/socket binding (no systemd socket activation in RT)

---

## Request Tracker Setup

### Queue

- **Name:** Facility Management
- **ID:** 3

Queue name is used consistently (preferred over numeric ID for clarity and portability).

### Custom Field

A ticket-level custom field is required:

- **Name:** `DeviceId`
- **Type:** Freeform text
- **Purpose:** Unique identifier for the Home Assistant entity/device

This field enables deduplication and correlation between HA entities and RT tickets.

---

## Home Assistant Configuration

### Helpers

Two helpers are used to avoid hardcoding secrets and URLs:

- `input_text.rt_url`  
  Example value:
```

[https://rt.example.com](https://rt.example.com)

````

- `input_text.rt_token`  
Contains the RT REST2 API token

---

### REST Commands

Defined in `configuration.yaml`:

```yaml
rest_command:
rt_search_open_ticket_for_device:
  url: >
    {{ states('input_text.rt_url').rstrip('/') }}/REST/2.0/tickets?query={{ query | urlencode }}
  method: GET
  headers:
    Accept: "application/json"
    Authorization: "token {{ states('input_text.rt_token') }}"

rt_create_ticket_facility_mgmt:
  url: >
    {{ states('input_text.rt_url').rstrip('/') }}/REST/2.0/ticket
  method: POST
  headers:
    Content-Type: "application/json"
    Accept: "application/json"
    Authorization: "token {{ states('input_text.rt_token') }}"
  payload: >
    {
      "Queue": "Facility Management",
      "Subject": "{{ subject }}",
      "Text": "{{ text }}",
      "CustomFields": {
        "DeviceId": "{{ device_id }}"
      }
    }
````

> **Important:** Adding or modifying `rest_command` requires a **full Home Assistant restart**, not just a YAML reload.

---

## Ticket Deduplication Strategy

Before creating a ticket, Home Assistant queries RT using **TicketSQL**:

```sql
Queue = "Facility Management"
AND (Status = "new" OR Status = "open" OR Status = "stalled")
AND CF.{DeviceId} = "<entity_id>"
```

### Logic

* If `count == 0` → create a new ticket
* If `count > 0` → do nothing (or optionally comment on the existing ticket)

This ensures:

* One open ticket per device/condition
* No alert storms from flapping sensors

---

## Manual Testing

### Create a Ticket (Developer Tools → Actions)

```yaml
action: rest_command.rt_create_ticket_facility_mgmt
data:
  subject: "Test ticket from Home Assistant"
  text: "This is a manual test ticket created via rest_command."
  device_id: "manual.test"
```

### Search for Open Tickets

```yaml
action: rest_command.rt_search_open_ticket_for_device
data:
  query: Status="open"
```

---

## Lessons Learned

* `rest_command` entries may not appear until a **full HA restart**
* YAML structure and indentation matter more than section order
* RT socket activation via systemd is **not supported** by `rt-server.fcgi`
* Explicit configuration (URLs, ports, bindings) is more reliable than implicit orchestration
* HA Actions UI does not show HTTP responses unless captured explicitly

---

## Future Enhancements

Planned or optional improvements:

* Comment on existing tickets instead of ignoring repeats
* Auto-close or resolve tickets when conditions clear
* Add severity, location, or category custom fields
* Rate-limit noisy sensors
* Add error notifications when RT API calls fail

---

## Status

**Working and verified end-to-end**

* Home Assistant → RT REST2 connectivity confirmed
* Token authentication verified
* Ticket creation and search functional
* Deduplication logic validated

---

## Maintainer Notes

This integration intentionally avoids:

* Custom HA integrations
* External brokers or middleware
* Over-automation

It favors clarity, debuggability, and alignment with both Home Assistant and RT’s native models.

```

---

If you want, next I can:
- turn this into a **GitHub-ready README** with badges
- add an **example automation file**
- document **auto-close/comment workflows**
- or produce a **runbook / troubleshooting section**
```
