"""Builds the Calendar Sync shortcut (docs/calendar-sync.md) as an unsigned XML plist.

    python screens/calendar/shortcut/build.py

Writes "Calendar Sync.shortcut" next to this file. iOS only imports signed shortcuts,
so sign it on a Mac before AirDropping it to the phone:

    shortcuts sign --mode anyone --input "Calendar Sync.shortcut" --output ~/Desktop/"Calendar Sync.shortcut"

The first run asks for LaraPaper's address, the webhook UUID, which calendars to show
and a short label for each, and saves the answers to Shortcuts/trmnl-calendar.json in
iCloud Drive. Later runs read that file; delete it to set up again. Action formats follow Apple-exported shortcuts as documented by
github.com/viticci/shortcuts-playground-plugin.
"""

import plistlib
import uuid
from pathlib import Path

OUT = Path(__file__).with_name("Calendar Sync.shortcut")
OBJ = "￼"  # Shortcuts' placeholder for a variable inside text


def uid(name: str) -> str:
    # Stable across rebuilds, so diffs show real changes.
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"trmnl-screens/calendar-sync/{name}")).upper()


def out(name: str, output: str) -> dict:
    return {"Type": "ActionOutput", "OutputUUID": uid(name), "OutputName": output}


def var(name: str) -> dict:
    return {"Type": "Variable", "VariableName": name}


def attachment(ref: dict) -> dict:
    return {"Value": ref, "WFSerializationType": "WFTextTokenAttachment"}


def text(*parts) -> dict:
    """Text with variables: plain strings and refs, in order."""
    s, ranges = "", {}
    for p in parts:
        if isinstance(p, str):
            s += p
        else:
            ranges[f"{{{len(s)}, 1}}"] = p
            s += OBJ
    return {"Value": {"string": s, "attachmentsByRange": ranges}, "WFSerializationType": "WFTextTokenString"}


def action(identifier: str, name: str | None = None, **params) -> dict:
    if name:
        params["UUID"] = uid(name)
    return {"WFWorkflowActionIdentifier": f"is.workflow.actions.{identifier}", "WFWorkflowActionParameters": params}


def comment(body: str) -> dict:
    return action("comment", WFCommentActionText=body)


def set_var(name: str, ref: dict) -> dict:
    return action("setvariable", WFVariableName=name, WFInput=attachment(ref))


def detail(identifier: str, name: str, prop: str, of: dict) -> dict:
    return action(f"properties.{identifier}", name, WFContentItemPropertyName=prop, WFInput=attachment(of))


def iso(name: str, date: dict) -> dict:
    fmt = "yyyy-MM-dd'T'HH:mm:ssXXXXX"
    # The runtime reads WFDateFormat; the editor shows WFDateFormatString. Without the first it sends RFC 2822.
    return action("format.date", name, WFDateFormatStyle="Custom",
                  WFDateFormat=fmt, WFDateFormatString=fmt, WFDate=text(date))


def dotless(name: str, of: dict) -> dict:
    # Dictionary keys are key paths, so a calendar named a@b.com would be read as a@b -> com.
    return action("text.replace", name, WFInput=text(of), WFReplaceTextFind=".", WFReplaceTextReplace="_",
                  WFReplaceTextRegularExpression=False)


def fields(items: dict) -> dict:
    """A Dictionary action's text fields."""
    return {"Value": {"WFDictionaryFieldValueItems": [
        {"WFItemType": 0, "WFKey": text(k), "WFValue": text(*(v if isinstance(v, tuple) else (v,)))}
        for k, v in items.items()
    ]}, "WFSerializationType": "WFDictionaryFieldValue"}


def block(identifier: str, name: str, note: str, start_params: dict, body: list, otherwise: list | None = None) -> list:
    group = uid(f"{name}-group")
    actions = [comment(f"- {note}"), action(identifier, name, GroupingIdentifier=group, WFControlFlowMode=0, **start_params), *body]
    if otherwise is not None:
        actions += [action(identifier, GroupingIdentifier=group, WFControlFlowMode=1), *otherwise]
    actions.append(action(identifier, f"{name}-end", GroupingIdentifier=group, WFControlFlowMode=2))
    return actions


def condition(ref: dict, code: int, **extra) -> dict:
    return {"WFInput": {"Type": "Variable", "Variable": attachment(ref)}, "WFCondition": code, **extra}


FILTER = {
    "Value": {
        "WFActionParameterFilterPrefix": 1,  # all of:
        "WFContentPredicateBoundedDate": False,
        "WFActionParameterFilterTemplates": [
            {"Operator": 1002, "Property": "Start Date", "Removable": True, "Values": {}},  # is today
            {"Operator": 2, "Property": "End Date", "Removable": True,  # is after now
             "Values": {"Date": attachment({"Type": "CurrentDate"})}},
        ],
    },
    "WFSerializationType": "WFContentPredicateTableTemplate",
}

attendee_loop = block("repeat.each", "attendees-loop", "For each attendee of this event.", {"WFInput": attachment(out("attendees", "Attendees"))}, [
    comment("Pin the attendee first: picking Repeat Index instead of Repeat Item fails with\n"
            "\"couldn't convert from Number to Event Attendee\"."),
    set_var("Attendee", var("Repeat Item 2")),
    detail("eventattendees", "is-me", "Is Me", var("Attendee")),
    *block("conditional", "if-me", "If this attendee is you, keep your reply; otherwise keep their name.", condition(out("is-me", "Is Me"), 2, WFNumberValue="0"), [
        detail("eventattendees", "status", "Status", var("Attendee")),
        set_var("Reply", out("status", "Status")),
    ], otherwise=[
        detail("eventattendees", "attendee-name", "Name", var("Attendee")),
        action("appendvariable", WFVariableName="Others", WFInput=attachment(out("attendee-name", "Name"))),
    ]),
])

event_body = [
    detail("calendarevents", "title", "Title", var("Event")),
    detail("calendarevents", "start", "Start Date", var("Event")),
    detail("calendarevents", "end", "End Date", var("Event")),
    detail("calendarevents", "all-day", "Is All Day", var("Event")),
    detail("calendarevents", "notes", "Notes", var("Event")),
    iso("start-iso", out("start", "Start Date")),
    iso("end-iso", out("end", "End Date")),
    comment("Your reply comes from the attendee marked Is Me; everyone else is listed by name."),
    action("nothing", "nothing"),
    set_var("Reply", out("nothing", "Nothing")),
    set_var("Others", out("nothing", "Nothing")),
    detail("calendarevents", "attendees", "Attendees", var("Event")),
    *attendee_loop,
    action("text.combine", "names", text=attachment(var("Others")),
           WFTextSeparator="Custom", WFTextCustomSeparator=", "),
    action("dictionary", "event", WFItems=fields({
        "title": out("title", "Title"),
        "start": out("start-iso", "Formatted Date"),
        "end": out("end-iso", "Formatted Date"),
        "all_day": out("all-day", "Is All Day"),
        "calendar": out("label", "Dictionary Value"),
        "reply": var("Reply"),
        "attendees": out("names", "Combined Text"),
        "description": out("notes", "Notes"),
    })),
    action("appendvariable", WFVariableName="Events", WFInput=attachment(out("event", "Dictionary"))),
]

CONFIG_FILE = "trmnl-calendar.json"
WEBHOOK_KEY = "_webhook"  # stored beside the calendar labels; no calendar has this name

UPCOMING = {
    "Value": {
        "WFActionParameterFilterPrefix": 1,
        "WFContentPredicateBoundedDate": False,
        "WFActionParameterFilterTemplates": [
            {"Operator": 2, "Property": "Start Date", "Removable": True,
             "Values": {"Date": attachment({"Type": "CurrentDate"})}},
        ],
    },
    "WFSerializationType": "WFContentPredicateTableTemplate",
}


def set_key(name: str, dictionary: dict, key: tuple, value: tuple) -> dict:
    return action("setvalueforkey", name, WFDictionary=attachment(dictionary),
                  WFDictionaryKey=text(*key), WFDictionaryValue=text(*value))


setup = [
    comment("First run: ask for the webhook and the calendars, then save the answers."),
    action("ask", "host", WFAskActionPrompt="LaraPaper's address as this phone reaches it, "
           "without a trailing slash (for example http://larapaper.example:4567)", WFInputType="URL"),
    action("ask", "uuid", WFAskActionPrompt="The Calendar plugin's webhook UUID (the end of its Webhook URL in LaraPaper)"),
    action("dictionary", "empty", WFItems=fields({})),
    set_key("config-url", out("empty", "Dictionary"), (WEBHOOK_KEY,),
            (out("host", "Provided Input"), "/api/custom_plugins/", out("uuid", "Provided Input"))),
    set_var("Config", out("config-url", "Dictionary")),
    comment("Calendars come from upcoming events, so a calendar with nothing coming up isn't offered."),
    action("filter.calendarevents", "upcoming", WFContentItemFilter=UPCOMING,
           WFContentItemLimitEnabled=True, WFContentItemLimitNumber=300.0),
    comment("Dictionary keys can't dedupe these: a key with dots is read as a key path. Each name is\n"
            "added once by checking the names so far, one per line."),
    *block("repeat.each", "upcoming-loop", "Collect each upcoming event's calendar name once.", {"WFInput": attachment(out("upcoming", "Calendar Events"))}, [
        detail("calendarevents", "upcoming-calendar", "Calendar", var("Repeat Item")),
        action("gettext", "names-so-far", WFTextActionText=text("\n", var("Calendar Names"), "\n")),
        *block("conditional", "if-new", "Only names not seen yet.",
               condition(out("names-so-far", "Text"), 999,
                         WFConditionalActionString=text("\n", out("upcoming-calendar", "Calendar"), "\n")), [
            action("appendvariable", WFVariableName="Calendar Names", WFInput=attachment(out("upcoming-calendar", "Calendar"))),
        ]),
    ]),
    *block("conditional", "if-names", "Stop with a message rather than save a setup with no calendars.",
           condition(var("Calendar Names"), 100), [], otherwise=[
        action("alert", WFAlertActionTitle="No calendars found",
               WFAlertActionMessage="Calendar Sync lists calendars that have upcoming events. Add an event, then run it again.",
               WFAlertActionCancelButtonShown=False),
        action("exit"),
    ]),
    action("choosefromlist", "chosen", WFInput=attachment(var("Calendar Names")),
           WFChooseFromListActionPrompt="Which calendars should the screen show?",
           WFChooseFromListActionSelectMultiple=True),
    *block("repeat.each", "chosen-loop", "Ask for a short label for each chosen calendar.", {"WFInput": attachment(out("chosen", "Chosen Item"))}, [
        action("ask", "label-ask", WFAskActionPrompt=text("Short label for ", var("Repeat Item"),
                                                      " (shown on each event, e.g. Work)"),
               WFAskActionDefaultAnswer=text(var("Repeat Item"))),
        dotless("chosen-key", var("Repeat Item")),
        set_key("config-label", var("Config"), (out("chosen-key", "Updated Text"),), (out("label-ask", "Provided Input"),)),
        set_var("Config", out("config-label", "Dictionary")),
    ]),
    action("setitemname", "config-file", WFInput=attachment(var("Config")), WFName=CONFIG_FILE),
    action("documentpicker.save", "saved", WFInput=attachment(out("config-file", "Renamed Item")),
           WFAskWhereToSave=False, WFFileDestinationPath="/", WFSaveFileOverwrite=True),
    action("notification", WFNotificationActionTitle="Calendar Sync is set up",
           WFNotificationActionBody=f"To change it, delete Shortcuts/{CONFIG_FILE} in iCloud Drive and run it again."),
]

actions = [
    comment("Calendar Sync for the TRMNL Calendar screen (docs/calendar-sync.md).\n"
            "Pushes the rest of today's events to the screen's LaraPaper webhook."),
    comment("- First run asks for the webhook and the calendars, and saves them to Shortcuts/trmnl-calendar.json\n"
            "- Delete that file to set up again\n"
            "- Run it from automations: closing Calendar, joining home Wi-Fi, hourly in the workday"),
    action("documentpicker.open", "stored", WFGetFilePath=CONFIG_FILE, WFShowFilePicker=False, WFFileErrorIfNotFound=False),
    *block("conditional", "if-stored", "If the settings file exists, read it; otherwise set up.", condition(out("stored", "File"), 100), [
        action("detect.dictionary", "stored-config", WFInput=attachment(out("stored", "File"))),
        set_var("Config", out("stored-config", "Dictionary")),
    ], otherwise=setup),
    action("getvalueforkey", "url", WFGetDictionaryValueType="Value", WFInput=attachment(var("Config")),
           WFDictionaryKey=text(WEBHOOK_KEY)),
    action("date", "now", WFDateActionMode="Current Date"),
    iso("synced-at", out("now", "Date")),
    action("filter.calendarevents", "events", WFContentItemFilter=FILTER),
    action("count", "found", WFCountType="Items", WFInput=attachment(out("events", "Calendar Events")),
           Input=attachment(out("events", "Calendar Events"))),
    *block("repeat.each", "events-loop", "For each event left today.", {"WFInput": attachment(out("events", "Calendar Events"))}, [
        set_var("Event", var("Repeat Item")),
        detail("calendarevents", "calendar", "Calendar", var("Event")),
        dotless("calendar-key", out("calendar", "Calendar")),
        action("getvalueforkey", "label", WFGetDictionaryValueType="Value",
               WFInput=attachment(var("Config")), WFDictionaryKey=text(out("calendar-key", "Updated Text"))),
        *block("conditional", "if-listed", "Only calendars chosen at setup; the label is what the screen shows.", condition(out("label", "Dictionary Value"), 100), event_body),
    ]),
    comment("Each event becomes JSON when combined as text, so titles and notes are escaped for us."),
    action("text.combine", "events-json", text=attachment(var("Events")),
           WFTextSeparator="Custom", WFTextCustomSeparator=","),
    action("gettext", "body", WFTextActionText=text(
        '{"merge_variables":{"synced_at":"', out("synced-at", "Formatted Date"),
        '","found":', out("found", "Count"), ',"events":[', out("events-json", "Combined Text"), "]}}")),
    action("downloadurl", "post", WFURL=text(out("url", "Dictionary Value")), WFHTTPMethod="POST", WFHTTPBodyType="File",
           WFRequestVariable=attachment(out("body", "Text")),
           WFFormValues={"Value": {"WFDictionaryFieldValueItems": []}, "WFSerializationType": "WFDictionaryFieldValue"},
           WFHTTPHeaders=fields({"Content-Type": "application/json"}), ShowHeaders=False),
]

workflow = {
    "WFWorkflowName": "Calendar Sync",
    "WFWorkflowActions": actions,
    "WFWorkflowClientVersion": "2700.0.4",
    "WFWorkflowHasOutputFallback": False,
    "WFWorkflowIcon": {"WFWorkflowIconGlyphNumber": 59681, "WFWorkflowIconStartColor": 431817727},
    "WFWorkflowImportQuestions": [],
    "WFWorkflowInputContentItemClasses": [],
    "WFWorkflowMinimumClientVersion": 900,
    "WFWorkflowMinimumClientVersionString": "900",
    "WFWorkflowOutputContentItemClasses": [],
    "WFWorkflowTypes": [],
}

if __name__ == "__main__":
    OUT.write_bytes(plistlib.dumps(workflow, fmt=plistlib.FMT_XML, sort_keys=False))
    print(f"wrote {OUT}")
