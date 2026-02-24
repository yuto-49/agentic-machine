---
name: vending_alerts
description: Sends vending machine alerts to designated channels
trigger: "Webhook from vending machine API"
---

## Purpose
Relay alerts from the vending machine system to Slack/Discord.

## Alert Types
- LOW_STOCK: Post in #claudius-admin channel
- PRICE_CHANGE: Post in #claudius channel
- DAILY_REPORT: Post in #claudius-admin channel
- RESTOCK_REQUEST: Post in #claudius-admin channel
- SYSTEM_ERROR: Post in #claudius-admin channel

## Format
Use the formatting provided by the API response. Do not modify content.
