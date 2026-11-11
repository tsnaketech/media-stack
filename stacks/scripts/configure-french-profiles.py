#!/usr/bin/env python3
"""Provision a persistent French audio policy in Profilarr, Radarr and Sonarr."""
import datetime
import csv
import importlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import time

setup = importlib.import_module("configure-profilarr")
arr = importlib.import_module("configure-download-clients")


def action(client, path, payload):
    result = client.call(path, dict(payload, layer="user"), form=True)
    if result.get("type") not in ("success", "redirect"):
        raise setup.SetupError(f"Profilarr action not confirmed on {path}.")
    return result


def find_named(rows, name):
    matches = [row for row in rows if row["name"] == name]
    if len(matches) > 1:
        raise setup.SetupError("Duplicate policy names found; resolve manually.")
    return matches[0] if matches else None


def ensure_entity(client, kind, dbid, name, description, language=None):
    key = "qualityProfiles" if kind == "quality-profiles" else "customFormats"
    row = find_named(client.page(f"/{kind}/{dbid}")[key], name)
    if not row:
        fields = {"name": name, "description": description, "tags": "[]"}
        if language:
            fields["language"] = language
        action(client, f"/{kind}/{dbid}/new", fields)
        row = find_named(client.page(f"/{kind}/{dbid}")[key], name)
    if not row:
        raise setup.SetupError(f"{kind}: creation not persisted.")
    return row["id"]


def provision(client, dbid, policy):
    cfid = ensure_entity(client, "custom-formats", dbid, policy["custom_format"], policy["description"])
    conditions = [{"name": "French audio", "type": "language", "arrType": "all",
                   "negate": False, "required": True,
                   "languages": [{"name": "French", "except": False}]}]
    action(client, f"/custom-formats/{dbid}/{cfid}/conditions?/update", {"conditions": json.dumps(conditions)})
    pid = ensure_entity(client, "quality-profiles", dbid, policy["name"], policy["description"], "French")
    action(client, f"/quality-profiles/{dbid}/{pid}/general?/update", {
        "name": policy["name"], "description": policy["description"], "tags": "[]", "language": "French"})
    all_qualities = client.page(f"/quality-profiles/{dbid}/{pid}/qualities")["qualities"]["allQualities"]
    enabled = policy["qualities"]
    names = enabled + sorted(q["name"] for q in all_qualities if q["name"] not in enabled)
    ordered = [{"type": "quality", "name": name, "position": i,
                "enabled": name in enabled, "upgradeUntil": i == 0}
               for i, name in enumerate(names)]
    action(client, f"/quality-profiles/{dbid}/{pid}/qualities?/update", {"orderedItems": json.dumps(ordered)})
    scores = [{"customFormatName": policy["custom_format"], "arrType": "all", "score": policy["minimum_score"]}]
    action(client, f"/quality-profiles/{dbid}/{pid}/scoring?/update", {
        "upgradesAllowed": str(policy["upgrades_allowed"]).lower(),
        "minimumScore": policy["minimum_score"], "upgradeUntilScore": policy["minimum_score"],
        "upgradeScoreIncrement": 1, "customFormatScores": json.dumps(scores)})
    return pid


def verify_language(client, dbid, policy):
    releases = []
    expected = {}
    cases = [("FRENCH", True), ("VFF", True), ("VFQ", True), ("VOSTFR", False), ("ENGLISH", False)]
    for media in ("movie", "series"):
        for marker, matches in cases:
            rid = len(releases) + 1
            title = ("Example.Movie.2025" if media == "movie" else "Example.Show.S01E01") + f".{marker}.1080p.WEB-DL.DDP5.1.H264-Test"
            releases.append({"id": rid, "title": title, "type": media})
            expected[rid] = matches
        rid = len(releases) + 1
        releases.append({"id": rid, "title": "Example.MULTI.1080p.WEB-DL.H264-Test", "type": media, "languages": ["English", "French"]})
        expected[rid] = True
    result = client.call(f"/quality-profiles/entity-testing/{dbid}/evaluate", {"releases": releases})
    if not result.get("parserAvailable") or len(result.get("evaluations", [])) != len(releases):
        raise setup.SetupError("French policy parser tests unavailable or incomplete.")
    for evaluation in result["evaluations"]:
        if evaluation.get("cfMatches", {}).get(policy["custom_format"]) is not expected[evaluation["releaseId"]]:
            raise setup.SetupError("French policy parser test failed; not applied to media.")
    print(f"French audio policy: {len(releases)} parser checks passed.")


def verify_profile(api, policy):
    profile = find_named(api.call("api/v3/qualityprofile"), policy["name"])
    if not profile:
        return None
    formats = api.call("api/v3/customformat")
    cf = find_named(formats, policy["custom_format"])
    if not cf:
        raise setup.SetupError("French custom format missing after synchronization.")
    languages = [spec for spec in cf["specifications"] if spec["implementation"] == "LanguageSpecification"]
    fields = {f["name"]: f.get("value") for f in languages[0]["fields"]} if len(languages) == 1 else {}
    if fields.get("value") != 2 or fields.get("exceptLanguage") not in (False, None) or languages[0].get("negate"):
        raise setup.SetupError("French language condition was not exported correctly.")
    scores = {item["format"]: item["score"] for item in profile["formatItems"]}
    if scores.get(cf["id"]) != policy["minimum_score"] or profile["minFormatScore"] != policy["minimum_score"]:
        raise setup.SetupError("French language threshold was not exported correctly.")
    if any(score != 0 for cid, score in scores.items() if cid != cf["id"]):
        raise setup.SetupError("Unexpected positive/negative scores in the managed French profile.")
    enabled = []
    for item in profile["items"]:
        if item["allowed"]:
            enabled += [x["quality"]["name"] for x in item.get("items", [])] if item.get("items") else [item["quality"]["name"]]
    if set(enabled) != set(policy["qualities"]) or profile["upgradeAllowed"] != policy["upgrades_allowed"]:
        raise setup.SetupError("French quality selection was not exported correctly.")
    return profile


def selected_policies(value, directory):
    try:
        names = next(csv.reader([value], skipinitialspace=True, strict=True))
    except (csv.Error, StopIteration):
        raise setup.SetupError('PROFILARR_PROFILES must be a CSV list of quoted names.') from None
    names = [name.strip() for name in names]
    if not names or any(not name for name in names) or len(set(names)) != len(names):
        raise setup.SetupError('PROFILARR_PROFILES must contain unique, non-empty names.')
    available = {}
    for path in sorted(directory.glob('french-*.json')):
        policy = json.loads(path.read_text())
        available[policy['name']] = policy
    if any(name not in available for name in names):
        raise setup.SetupError('Unknown profile in PROFILARR_PROFILES; add its policy file first.')
    return [available[name] for name in names]


def main():
    root = Path(__file__).resolve().parent.parent
    env = setup.compose(root, "shared")["services"]["profilarr"]["environment"]
    if str(env.get("PROFILARR_FRENCH_PROFILES_ENABLED", "false")).lower() != "true":
        print("Profilarr: automatic French profiles disabled.")
        return
    policies = selected_policies(env.get("PROFILARR_PROFILES", "1080p Français"), root / "shared/profiles")
    default_name = env.get("PROFILARR_DEFAULT_PROFILE", policies[0]["name"])
    if default_name not in {policy["name"] for policy in policies}:
        raise setup.SetupError("PROFILARR_DEFAULT_PROFILE must be selected in PROFILARR_PROFILES.")
    port = env.get("PORT", "6868")
    # Use the published host port, including custom bind addresses.
    service = setup.compose(root, "shared")["services"]["profilarr"]
    published = next(p for p in service["ports"] if int(p["target"]) == int(port))
    host = published.get("host_ip") or "127.0.0.1"
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    client = setup.Client(f"http://{host}:{published['published']}", env["ORIGIN"])
    client.login(env["PROFILARR_USERNAME"], env["PROFILARR_PASSWORD"])
    db = find_named(client.call("/api/v1/databases"), env.get("PROFILARR_DATABASE_NAME", "Dictionarry"))
    if not db:
        raise setup.SetupError("Link the Dictionarry database before applying the French policy.")
    if db.get("enabled") == 0:
        raise setup.SetupError("The Profilarr policy database is disabled. Enable and synchronize it, or set PROFILARR_FRENCH_PROFILES_ENABLED=false. Existing profiles were not changed.")
    targets = []
    for app, stack, port, kind in (("radarr", "movie", 7878, "movie"), ("sonarr", "tv", 8989, "series")):
        instance = setup.find_instance(client.instances(), app, env[f"PROFILARR_{app.upper()}_URL"])
        if not instance:
            raise setup.SetupError(f"{app}: register its connection first.")
        key = setup.api_key(root, stack, app, env.get(f"PROFILARR_{app.upper()}_API_KEY"))
        # Host addresses are discovered from each application's Compose published port.
        svc = setup.compose(root, stack)["services"][app]
        mapping = next(p for p in svc["ports"] if int(p["target"]) == port)
        host = mapping.get("host_ip") or "127.0.0.1"
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        api = arr.API(f"http://{host}:{mapping['published']}", {"X-Api-Key": key})
        targets.append((app, kind, api, instance))
    backup_root = root / "shared/data/profilarr/backups"
    backup = backup_root / ("french-policy-" + datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    backup.mkdir(mode=0o700, parents=True)
    for app, kind, api, instance in targets:
        snapshot = {"qualityProfiles": api.call("api/v3/qualityprofile"),
                    "customFormats": api.call("api/v3/customformat"),
                    "assignments": [{"id": x["id"], "qualityProfileId": x["qualityProfileId"]} for x in api.call("api/v3/" + kind)]}
        path = backup / (app + ".json")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(snapshot, out)
    with sqlite3.connect(f"file:{root}/shared/data/profilarr/data/profilarr.db?mode=ro", uri=True) as source:
        with sqlite3.connect(backup / "profilarr.db") as dest:
            source.backup(dest)
    (backup / "profilarr.db").chmod(0o600)
    for policy in policies:
        provision(client, db["id"], policy)
    verify_language(client, db["id"], policies[0])
    for app, kind, api, instance in targets:
        route = f"/arr/{instance['id']}/sync"
        action(client, route + "?/saveQualityProfiles", {
            "selections": json.dumps([{"databaseId": db["id"], "profileName": policy["name"]} for policy in policies]),
            "priorities": json.dumps([{"databaseId": db["id"], "priority": 0}]),
            "trigger": "schedule", "cron": "0 5 * * *"})
        action(client, route + "?/syncQualityProfiles", {})
        for attempt in range(40):
            try:
                profiles = [verify_profile(api, policy) for policy in policies]
                if all(profiles):
                    break
            except setup.SetupError:
                if attempt == 39:
                    raise
            time.sleep(2)
        else:
            raise setup.SetupError(f"{app}: synchronization not completed; media assignments unchanged.")
        by_name = {profile["name"]: profile for profile in profiles}
        default_profile = by_name[default_name]
        selected_ids = {profile["id"] for profile in profiles}
        if str(env.get("PROFILARR_FRENCH_APPLY_EXISTING", "false")).lower() == "true":
            items = api.call("api/v3/" + kind)
            ids = [x["id"] for x in items if x["qualityProfileId"] not in selected_ids]
            if ids:
                api.call("api/v3/" + kind + "/editor", "PUT", {kind + "Ids": ids, "qualityProfileId": default_profile["id"]})
            if any(x["qualityProfileId"] not in selected_ids for x in api.call("api/v3/" + kind)):
                raise setup.SetupError(f"{app}: media assignments not confirmed.")
            print(f"{app}: {len(profiles)} French profiles verified; {len(ids)} existing items assigned to the default.")
        else:
            print(f"{app}: {len(profiles)} French profiles synchronized; existing assignments preserved.")
    print(f"Private rollback snapshots: {backup}")


if __name__ == "__main__":
    try:
        main()
    except (setup.SetupError, arr.SetupError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
